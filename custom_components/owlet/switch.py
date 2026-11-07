"""Established base-station control with bounded cloud confirmation."""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import OwletBaseEntity
from .owletapi.exceptions import OwletError

PARALLEL_UPDATES = 1
COMMAND_CONFIRMATION_SECONDS = 30
COMMAND_READBACK_SECONDS = 2
_LOGGER = logging.getLogger(__name__)


class CommandStatus(StrEnum):
    """Acceptance and cloud confirmation are distinct from physical state."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    async_add_entities(
        [
            OwletBaseSwitch(coordinator)
            for coordinator in hass.data[DOMAIN][config_entry.entry_id].values()
        ]
    )


class OwletBaseSwitch(OwletBaseEntity, SwitchEntity):
    """Keep serial-base_station_on identity and observe requested state."""

    entity_description = SwitchEntityDescription(
        key="base_station_on", translation_key="base_on"
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.sock.serial}-base_station_on"
        self._command_lock = asyncio.Lock()
        self._command_task: asyncio.Task | None = None
        self._command_status: CommandStatus | None = None
        self._requested_state: bool | None = None
        self._confirmation_after_poll = 0
        self._cancel_readback = None
        self._cancel_deadline = None
        self._readback_task: asyncio.Task | None = None
        self._removed = False

    async def async_added_to_hass(self) -> None:
        self._removed = False
        await super().async_added_to_hass()

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.sock.properties.get("charging") is False
            and type(self.is_on) is bool
            and self.coordinator.reading_available("base_station_on")
        )

    @property
    def is_on(self) -> bool | None:
        return self.sock.properties.get("base_station_on")

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "command_status": self._command_status,
            "requested_state": self._requested_state,
        }

    @callback
    def _cancel_confirmation(self) -> None:
        for cancel in (self._cancel_readback, self._cancel_deadline):
            if cancel:
                cancel()
        self._cancel_readback = self._cancel_deadline = None
        if self._readback_task and not self._readback_task.done():
            self._readback_task.cancel()

    async def _async_join_readback(self) -> None:
        if self._readback_task:
            await asyncio.gather(self._readback_task, return_exceptions=True)
            self._readback_task = None

    @callback
    def _handle_coordinator_update(self) -> None:
        if (
            self._command_status in (CommandStatus.PENDING, CommandStatus.UNCONFIRMED)
            and self.coordinator.last_update_success
            and self.coordinator.successful_polls > self._confirmation_after_poll
            and self.is_on is self._requested_state
        ):
            self._command_status = CommandStatus.CONFIRMED
            if self._cancel_readback:
                self._cancel_readback()
                self._cancel_readback = None
            if self._cancel_deadline:
                self._cancel_deadline()
                self._cancel_deadline = None
        super()._handle_coordinator_update()

    @callback
    def _confirmation_expired(self, now: datetime) -> None:
        self._cancel_deadline = None
        self._cancel_confirmation()
        self._command_status = CommandStatus.UNCONFIRMED
        _LOGGER.warning(
            "Owlet base-station command accepted but cloud state remains unconfirmed"
        )
        self.async_write_ha_state()

    @callback
    def _start_readback(self, now: datetime) -> None:
        self._cancel_readback = None
        if self._command_status == CommandStatus.PENDING and not self._removed:
            self._readback_task = self.hass.async_create_task(self._async_readback())

    async def _async_readback(self) -> None:
        try:
            await self.coordinator.async_refresh()
        finally:
            if (
                self._command_status == CommandStatus.PENDING
                and not self._removed
                and not asyncio.current_task().cancelling()
            ):
                self._cancel_readback = async_track_point_in_utc_time(
                    self.hass,
                    self._start_readback,
                    dt_util.utcnow() + timedelta(seconds=COMMAND_READBACK_SECONDS),
                )

    async def _async_set(self, state: bool) -> None:
        async with self._command_lock:
            if self._removed:
                raise HomeAssistantError("Owlet switch has been unloaded")
            try:
                self._command_task = self.hass.async_create_task(
                    self.sock.control_base_station(state)
                )
                await self._command_task
            except (OwletError, TimeoutError):
                raise HomeAssistantError("Owlet base-station command failed") from None
            finally:
                self._command_task = None
            self._cancel_confirmation()
            await self._async_join_readback()
            if self._removed:
                return
            self._requested_state = state
            self._confirmation_after_poll = self.coordinator.successful_polls
            self._command_status = CommandStatus.PENDING
            self.async_write_ha_state()
            self._cancel_deadline = async_track_point_in_utc_time(
                self.hass,
                self._confirmation_expired,
                dt_util.utcnow() + timedelta(seconds=COMMAND_CONFIRMATION_SECONDS),
            )
            self._start_readback(dt_util.utcnow())

    async def async_will_remove_from_hass(self) -> None:
        self._removed = True
        self._cancel_confirmation()
        if self._command_task:
            self._command_task.cancel()
            await asyncio.gather(self._command_task, return_exceptions=True)
        await self._async_join_readback()
        await super().async_will_remove_from_hass()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
