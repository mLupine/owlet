"""Established base-station control with matching cloud readback."""

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import OwletBaseEntity
from .owletapi.exceptions import OwletError

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    async_add_entities(
        [
            OwletBaseSwitch(coordinator)
            for coordinator in hass.data[DOMAIN][config_entry.entry_id].values()
        ]
    )


class OwletBaseSwitch(OwletBaseEntity, SwitchEntity):
    """Keep serial-base_station_on identity and verify requested state."""

    entity_description = SwitchEntityDescription(
        key="base_station_on", translation_key="base_on"
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.sock.serial}-base_station_on"

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

    async def _async_set(self, state: bool) -> None:
        try:
            await self.sock.control_base_station(state)
            await self.coordinator.async_refresh()
        except OwletError:
            raise HomeAssistantError("Owlet base-station command failed") from None
        if not self.coordinator.last_update_success or self.is_on is not state:
            raise HomeAssistantError(
                "Owlet did not confirm the requested base-station state"
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
