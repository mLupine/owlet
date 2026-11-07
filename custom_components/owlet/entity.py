"""Shared identity, metadata and late capability discovery."""

import re

from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import OwletCoordinator


def valid_mac(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = format_mac(value)
    if not re.fullmatch(r"[0-9a-f]{2}(?::[0-9a-f]{2}){5}", value):
        return None
    if value == "00:00:00:00:00:00" or int(value[:2], 16) & 1:
        return None
    return value


def discover_entities(entry, coordinator, async_add_entities, factories) -> None:
    """Add capabilities when observed, once per platform session."""
    added = set()

    def discover():
        entities = []
        for key, factory in factories.items():
            if key not in added and key in coordinator.sock.capabilities:
                added.add(key)
                entities.append(factory())
        if entities:
            async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class OwletBaseEntity(CoordinatorEntity[OwletCoordinator], Entity):
    """Preserve established serial-based device and entity registry bindings."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OwletCoordinator) -> None:
        super().__init__(coordinator)
        self.sock = coordinator.sock

    @property
    def device_info(self) -> DeviceInfo:
        mac = valid_mac(self.sock.mac)
        hardware = self.sock.properties.get("hardware_version")
        return DeviceInfo(
            identifiers={(DOMAIN, self.sock.serial)},
            name=f"Owlet Sock {self.sock.serial}",
            connections={("mac", mac)} if mac else set(),
            suggested_area="Nursery",
            configuration_url="https://my.owletcare.com/",
            manufacturer=MANUFACTURER,
            model=self.sock.oem_model or self.sock.model,
            sw_version=self.sock.sw_version,
            hw_version=hardware
            if isinstance(hardware, str) and hardware.strip()
            else self.sock.revision,
        )
