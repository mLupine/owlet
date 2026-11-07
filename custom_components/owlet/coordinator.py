"""Polling, credential persistence and source-specific freshness."""

import logging
import math
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACTIVATION_INTERVAL,
    CONF_BODY_POSITION,
    CONF_STALE_THRESHOLD,
    DEFAULT_ACTIVATION_INTERVAL,
    DEFAULT_STALE_THRESHOLD,
    DOMAIN,
    integer_option,
    polling_interval,
)
from .owletapi.const import PROPERTIES
from .owletapi.exceptions import (
    OwletAuthenticationError,
    OwletCredentialsError,
    OwletError,
)
from .owletapi.sock import Sock

_LOGGER = logging.getLogger(__name__)
EVENT_KEYS = frozenset(PROPERTIES[bool])


def store_tokens(hass: HomeAssistant, entry: ConfigEntry, tokens: dict) -> None:
    """Merge valid snapshots, including rotations followed by failed discovery."""
    valid = {
        key: value
        for key, value in tokens.items()
        if (key in ("api_token", "refresh") and isinstance(value, str) and value)
        or (key == "expiry" and type(value) in (float, int) and math.isfinite(value))
    }
    if any(entry.data.get(key) != value for key, value in valid.items()):
        hass.config_entries.async_update_entry(entry, data={**entry.data, **valid})


class OwletCoordinator(DataUpdateCoordinator[None]):
    """One sock's telemetry, expiry timers and optional historical coordinator."""

    def __init__(self, hass: HomeAssistant, sock: Sock, entry: ConfigEntry) -> None:
        self.sock = sock
        self.entry = entry
        self._cancel_expiry = None
        self._failure_count = 0
        self._options = None
        self._unknown_since: dict[str, datetime] = {}
        self.body_position = None
        self.body_position_enabled = False
        self._body_task = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=polling_interval(entry.options)),
        )
        self._set_options()

    def _set_options(self) -> None:
        self._options = dict(self.entry.options)
        self.base_interval = polling_interval(self.entry.options)
        self.stale_seconds = (
            integer_option(
                self.entry.options,
                CONF_STALE_THRESHOLD,
                DEFAULT_STALE_THRESHOLD,
                0,
                120,
            )
            * 60
        )
        self.sock.api._activation_interval = integer_option(
            self.entry.options,
            CONF_ACTIVATION_INTERVAL,
            DEFAULT_ACTIVATION_INTERVAL,
            10,
            600,
        )
        self.update_interval = timedelta(seconds=self.base_interval)

    async def async_apply_options(self) -> None:
        if self._options == dict(self.entry.options):
            return
        self._set_options()
        self._schedule_expiry()
        self.configure_body_position()
        await self.async_request_refresh()

    @property
    def last_updated(self) -> datetime | None:
        return self.sock.last_updated_at

    def reading_status(self, key: str) -> str:
        if key in self.sock.expected_vitals and self.sock.properties.get(key) is None:
            return "unknown"
        if key in EVENT_KEYS or key == "red_alert_updated_at":
            return "event"
        if self.sock.property_tracks_changes_only(key):
            return "state"
        timestamp = self.sock.property_timestamp(key)
        if timestamp is None:
            return "unknown"
        if (
            self.stale_seconds
            and (dt_util.utcnow() - timestamp).total_seconds() >= self.stale_seconds
        ):
            return "stale"
        return "fresh"

    def reading_available(self, key: str) -> bool:
        return not self.stale_seconds or self.reading_status(key) in (
            "fresh",
            "event",
            "state",
        )

    @property
    def readings_expected(self) -> bool:
        for key, idle_value in (("charging", True), ("base_station_on", False)):
            if self.sock.properties.get(key) is idle_value and self.reading_status(
                key
            ) in ("fresh", "state"):
                return False
        return True

    @property
    def affected_vitals(self) -> list[str]:
        return [
            key
            for key in self.sock.expected_vitals
            if self.reading_status(key) in ("unknown", "stale")
        ]

    @property
    def is_stale(self) -> bool:
        return bool(
            self.stale_seconds and self.readings_expected and self.affected_vitals
        )

    @property
    def issue_id(self) -> str:
        return f"stale_data_{self.entry.entry_id}_{self.sock.serial}"

    def _update_repair(self) -> None:
        for key in self.sock.expected_vitals:
            if self.reading_status(key) == "unknown":
                self._unknown_since.setdefault(key, dt_util.utcnow())
            else:
                self._unknown_since.pop(key, None)
        oldest = min(
            (
                self._unknown_since.get(key) or self.sock.property_timestamp(key)
                for key in self.affected_vitals
            ),
            default=dt_util.utcnow(),
        )
        if self.is_stale and (dt_util.utcnow() - oldest).total_seconds() >= 3600:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self.issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="stale_data",
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)

    def _schedule_expiry(self) -> None:
        if self._cancel_expiry:
            self._cancel_expiry()
            self._cancel_expiry = None
        if not self.stale_seconds:
            return
        now = dt_util.utcnow()
        deadlines = []
        for key in self.sock.capabilities - EVENT_KEYS:
            if self.sock.property_tracks_changes_only(key):
                continue
            timestamp = self.sock.property_timestamp(key)
            if timestamp:
                deadlines.extend(
                    [
                        timestamp + timedelta(seconds=self.stale_seconds),
                        timestamp + timedelta(hours=1),
                    ]
                )
        deadlines.extend(
            since + timedelta(hours=1) for since in self._unknown_since.values()
        )
        future = [deadline for deadline in deadlines if deadline > now]
        if future:
            self._cancel_expiry = async_track_point_in_utc_time(
                self.hass, self._expire_readings, min(future)
            )

    @callback
    def _expire_readings(self, now: datetime) -> None:
        self._cancel_expiry = None
        self._update_repair()
        self.async_update_listeners()
        self._schedule_expiry()

    async def _async_update_data(self) -> None:
        try:
            await self.sock.update_properties()
        except (OwletAuthenticationError, OwletCredentialsError):
            raise ConfigEntryAuthFailed(
                "Owlet authentication expired; sign in again"
            ) from None
        except (OwletError, TimeoutError) as err:
            self._failure_count += 1
            delay = max(
                self.base_interval,
                min(self.base_interval * 2 ** min(self._failure_count, 8), 300),
                getattr(err, "retry_after", None) or 0,
            )
            self.update_interval = timedelta(seconds=delay)
            raise UpdateFailed("Unable to update Owlet readings") from None
        finally:
            store_tokens(self.hass, self.entry, self.sock.api.tokens)
        self._failure_count = 0
        enabled = (
            self.entry.options.get(CONF_BODY_POSITION) is True
            and self.sock.version == 3
        )
        if enabled != self.body_position_enabled:
            self.configure_body_position()
        self.update_interval = timedelta(seconds=self.base_interval)
        self._update_repair()
        self._schedule_expiry()

    def configure_body_position(self) -> None:
        enabled = (
            self.entry.options.get(CONF_BODY_POSITION) is True
            and self.sock.version == 3
        )
        self.body_position_enabled = enabled
        if enabled:
            self.sock.capabilities.add("body_position")
        if enabled and self.body_position is None:
            from .sleep_data import BodyPositionCoordinator

            self.body_position = BodyPositionCoordinator(
                self.hass, self.sock, self.entry
            )
            self._body_task = self.hass.async_create_task(
                self.body_position.async_refresh()
            )
        elif not enabled and self.body_position is not None:
            self.body_position.stop()
            if self._body_task:
                self._body_task.cancel()
            self.body_position = None
        self.async_update_listeners()

    async def async_stop_body_position(self) -> None:
        if self.body_position:
            await self.body_position.async_close()
        if self._body_task:
            self._body_task.cancel()
            import asyncio

            await asyncio.gather(self._body_task, return_exceptions=True)

    @callback
    def shutdown(self) -> None:
        if self._cancel_expiry:
            self._cancel_expiry()
            self._cancel_expiry = None
        ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
