"""Support for Owlet sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, SLEEP_STATES
from .coordinator import OwletCoordinator
from .entity import OwletBaseEntity, discover_entities


@dataclass(frozen=True, kw_only=True)
class OwletSensorEntityDescription(SensorEntityDescription):
    """Represent the owlet sensor entity description."""

    available_during_charging: bool


SENSORS: tuple[OwletSensorEntityDescription, ...] = (
    OwletSensorEntityDescription(
        key="battery_percentage",
        translation_key="batterypercent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        available_during_charging=True,
    ),
    OwletSensorEntityDescription(
        key="oxygen_saturation",
        translation_key="o2saturation",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:leaf",
        available_during_charging=False,
    ),
    OwletSensorEntityDescription(
        key="heart_rate",
        translation_key="heartrate",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        available_during_charging=False,
    ),
    OwletSensorEntityDescription(
        key="battery_minutes",
        translation_key="batterymin",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        available_during_charging=False,
    ),
    OwletSensorEntityDescription(
        key="signal_strength",
        translation_key="signalstrength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        available_during_charging=True,
    ),
    OwletSensorEntityDescription(
        key="skin_temperature",
        translation_key="skintemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        available_during_charging=False,
    ),
    OwletSensorEntityDescription(
        key="movement",
        translation_key="movement",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cursor-move",
        entity_registry_enabled_default=False,
        available_during_charging=False,
    ),
    OwletSensorEntityDescription(
        key="movement_bucket",
        translation_key="movementbucket",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:bucket-outline",
        entity_registry_enabled_default=False,
        available_during_charging=False,
    ),
)

SENSORS += tuple(
    OwletSensorEntityDescription(
        key=key, translation_key=key, available_during_charging=True
    )
    for key in ("alerts_mask", "base_monitoring_status", "battery_status")
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
                OwletSensor(coordinator, description)
            )
            for description in SENSORS
        }
        factories["sleep_state"] = lambda coordinator=coordinator: OwletSleepSensor(
            coordinator
        )
        factories["oxygen_10_av"] = lambda coordinator=coordinator: (
            OwletOxygenAverageSensor(coordinator)
        )
        factories["red_alert_updated_at"] = lambda coordinator=coordinator: (
            OwletTimestampSensor(coordinator, "red_alert_updated_at")
        )
        from .sleep_data import BodyPositionSensor

        factories["body_position"] = lambda coordinator=coordinator: BodyPositionSensor(
            coordinator
        )
        discover_entities(config_entry, coordinator, async_add_entities, factories)
        async_add_entities([OwletTimestampSensor(coordinator, "last_updated")])


class OwletSensor(OwletBaseEntity, SensorEntity):
    """Representation of an Owlet sensor."""

    def __init__(
        self,
        coordinator: OwletCoordinator,
        description: OwletSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description: OwletSensorEntityDescription = description
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
    def native_value(self) -> StateType:
        """Return sensor value."""

        return self.sock.properties.get(self.entity_description.key)


class OwletSleepSensor(OwletSensor):
    """Representation of an Owlet sleep sensor."""

    _attr_options = list(SLEEP_STATES.values())
    entity_description = OwletSensorEntityDescription(
        key="sleep_state",
        translation_key="sleepstate",
        device_class=SensorDeviceClass.ENUM,
        available_during_charging=False,
    )

    def __init__(
        self,
        coordinator: OwletCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, self.entity_description)

    @property
    def native_value(self) -> StateType:
        """Return sensor value."""
        return SLEEP_STATES.get(self.sock.properties.get("sleep_state"), "unknown")


class OwletOxygenAverageSensor(OwletSensor):
    """Representation of an Owlet sleep sensor."""

    entity_description = OwletSensorEntityDescription(
        key="oxygen_10_av",
        translation_key="o2saturation10a",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:leaf",
        available_during_charging=False,
        state_class=SensorStateClass.MEASUREMENT,
    )

    def __init__(
        self,
        coordinator: OwletCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, self.entity_description)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        value = self.native_value
        return super().available and value is not None and 0 <= value <= 100


class OwletTimestampSensor(OwletSensor):
    """Expose source observation times without asserting current freshness."""

    def __init__(self, coordinator, key):
        from homeassistant.const import EntityCategory

        super().__init__(
            coordinator,
            OwletSensorEntityDescription(
                key=key,
                translation_key=key,
                device_class=SensorDeviceClass.TIMESTAMP,
                entity_category=EntityCategory.DIAGNOSTIC,
                available_during_charging=True,
            ),
        )

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        if self.entity_description.key == "last_updated":
            return self.coordinator.last_updated
        return self.sock.properties.get(self.entity_description.key)
