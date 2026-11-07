"""Support for Owlet binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OwletCoordinator
from .entity import OwletBaseEntity, discover_entities


@dataclass(frozen=True, kw_only=True)
class OwletBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Represent the owlet binary sensor entity description."""

    available_during_charging: bool


SENSORS: tuple[OwletBinarySensorEntityDescription, ...] = (
    OwletBinarySensorEntityDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        available_during_charging=True,
    ),
    OwletBinarySensorEntityDescription(
        key="high_heart_rate_alert",
        translation_key="high_hr_alrt",
        device_class=BinarySensorDeviceClass.SOUND,
        available_during_charging=True,
    ),
    OwletBinarySensorEntityDescription(
        key="low_heart_rate_alert",
        translation_key="low_hr_alrt",
        device_class=BinarySensorDeviceClass.SOUND,
        available_during_charging=True,
    ),
    OwletBinarySensorEntityDescription(
        key="high_oxygen_alert",
        translation_key="high_ox_alrt",
        device_class=BinarySensorDeviceClass.SOUND,
        available_during_charging=True,
    ),
    OwletBinarySensorEntityDescription(
        key="low_oxygen_alert",
        translation_key="low_ox_alrt",
        device_class=BinarySensorDeviceClass.SOUND,
        available_during_charging=True,
    ),
    OwletBinarySensorEntityDescription(
        key="critical_oxygen_alert",
        translation_key="crit_ox_alrt",
        device_class=BinarySensorDeviceClass.SOUND,
        available_during_charging=True,
    ),
    OwletBinarySensorEntityDescription(
        key="low_battery_alert",
        translation_key="low_batt_alrt",
        device_class=BinarySensorDeviceClass.SOUND,
        available_during_charging=True,
    ),
    OwletBinarySensorEntityDescription(
        key="critical_battery_alert",
        translation_key="crit_batt_alrt",
        device_class=BinarySensorDeviceClass.SOUND,
        available_during_charging=True,
    ),
    OwletBinarySensorEntityDescription(
        key="lost_power_alert",
        translation_key="lost_pwr_alrt",
        device_class=BinarySensorDeviceClass.SOUND,
        available_during_charging=True,
    ),
    OwletBinarySensorEntityDescription(
        key="sock_disconnected",
        translation_key="sock_discon_alrt",
        device_class=BinarySensorDeviceClass.SOUND,
        available_during_charging=True,
    ),
    OwletBinarySensorEntityDescription(
        key="sock_off",
        translation_key="sock_off",
        device_class=BinarySensorDeviceClass.POWER,
        available_during_charging=True,
    ),
)

SENSORS += tuple(
    OwletBinarySensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=BinarySensorDeviceClass.PROBLEM,
        available_during_charging=True,
    )
    for key in (
        "discomfort_alert",
        "low_integrity_reading",
        "preview_high_priority_alarm",
        "preview_medium_priority_alarm",
        "preview_low_priority_alarm",
        "preview_drm_priority_alarm",
    )
)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the owlet sensors from config entry."""

    for coordinator in hass.data[DOMAIN][config_entry.entry_id].values():
        factories = {
            description.key: lambda description=description, coordinator=coordinator: (
                OwletBinarySensor(coordinator, description)
            )
            for description in SENSORS
        }
        factories["sleep_state"] = lambda coordinator=coordinator: OwletAwakeSensor(
            coordinator
        )
        discover_entities(config_entry, coordinator, async_add_entities, factories)
        async_add_entities([OwletStaleSensor(coordinator)])


class OwletBinarySensor(OwletBaseEntity, BinarySensorEntity):
    """Representation of an Owlet binary sensor."""

    def __init__(
        self,
        coordinator: OwletCoordinator,
        description: OwletBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.sock.serial}-{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.reading_available(self.entity_description.key)
            and (
                self.sock.properties.get("charging") is False
                or self.entity_description.available_during_charging
            )
        )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""

        return self.sock.properties.get(self.entity_description.key)


class OwletAwakeSensor(OwletBinarySensor):
    """Representation of an Owlet sleep sensor."""

    entity_description = OwletBinarySensorEntityDescription(
        key="sleep_state",
        translation_key="awake",
        icon="mdi:sleep",
        available_during_charging=False,
    )

    def __init__(
        self,
        coordinator: OwletCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, self.entity_description)

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        value = self.sock.properties.get(self.entity_description.key)
        return value == 1 if type(value) is int and value in (1, 8, 15) else None


class OwletStaleSensor(OwletBinarySensor):
    """Flag stale or unknown expected measurements, independently of poll success."""

    def __init__(self, coordinator):
        from homeassistant.const import EntityCategory

        super().__init__(
            coordinator,
            OwletBinarySensorEntityDescription(
                key="data_stale",
                translation_key="data_stale",
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
                available_during_charging=True,
            ),
        )

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.coordinator.is_stale

    @property
    def extra_state_attributes(self):
        return {
            "affected_readings": self.coordinator.affected_vitals,
            "readings_expected": self.coordinator.readings_expected,
            "poll_success": self.coordinator.last_update_success,
            "freshness": {
                key: self.coordinator.reading_status(key)
                for key in ("heart_rate", "oxygen_saturation")
            },
        }
