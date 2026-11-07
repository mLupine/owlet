"""Test Owlet Sensor."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import async_init_integration
from .test_superintegration import entity_state


async def test_sensors_asleep(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(
        hass, properties_fixture="update_properties_asleep.json"
    )

    assert len(hass.states.async_all("sensor")) == 11

    assert (
        entity_state(hass, "sensor", "battery_percentage", "SERIAL_NUMBER").state
        == "50.0"
    )
    assert (
        entity_state(hass, "sensor", "battery_minutes", "SERIAL_NUMBER").state
        == "400.0"
    )
    assert entity_state(hass, "sensor", "heart_rate", "SERIAL_NUMBER").state == "97.0"
    assert (
        entity_state(hass, "sensor", "oxygen_saturation", "SERIAL_NUMBER").state
        == "99.0"
    )
    assert entity_state(hass, "sensor", "oxygen_10_av", "SERIAL_NUMBER").state == "97.0"

    assert (
        entity_state(hass, "sensor", "signal_strength", "SERIAL_NUMBER").state == "30.0"
    )
    assert (
        entity_state(hass, "sensor", "skin_temperature", "SERIAL_NUMBER").state == "34"
    )
    assert (
        entity_state(hass, "sensor", "sleep_state", "SERIAL_NUMBER").state
        == "light_sleep"
    )


async def test_sensors_awake(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(
        hass, properties_fixture="update_properties_awake.json"
    )

    assert len(hass.states.async_all("sensor")) == 11

    assert (
        entity_state(hass, "sensor", "battery_percentage", "SERIAL_NUMBER").state
        == "80.0"
    )
    assert (
        entity_state(hass, "sensor", "battery_minutes", "SERIAL_NUMBER").state
        == "600.0"
    )
    assert entity_state(hass, "sensor", "heart_rate", "SERIAL_NUMBER").state == "110.0"
    assert (
        entity_state(hass, "sensor", "oxygen_saturation", "SERIAL_NUMBER").state
        == "98.0"
    )
    assert entity_state(hass, "sensor", "oxygen_10_av", "SERIAL_NUMBER").state == "98.0"
    assert (
        entity_state(hass, "sensor", "signal_strength", "SERIAL_NUMBER").state == "34.0"
    )
    assert (
        entity_state(hass, "sensor", "skin_temperature", "SERIAL_NUMBER").state == "35"
    )
    assert entity_state(hass, "sensor", "sleep_state", "SERIAL_NUMBER").state == "awake"


async def test_sensors_charging(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(
        hass, properties_fixture="update_properties_charging.json"
    )

    assert len(hass.states.async_all("sensor")) == 11

    assert (
        entity_state(hass, "sensor", "battery_percentage", "SERIAL_NUMBER").state
        == "100.0"
    )
    assert (
        entity_state(hass, "sensor", "battery_minutes", "SERIAL_NUMBER").state
        == "unavailable"
    )
    assert (
        entity_state(hass, "sensor", "heart_rate", "SERIAL_NUMBER").state
        == "unavailable"
    )
    assert (
        entity_state(hass, "sensor", "oxygen_saturation", "SERIAL_NUMBER").state
        == "unavailable"
    )
    assert (
        entity_state(hass, "sensor", "oxygen_10_av", "SERIAL_NUMBER").state
        == "unavailable"
    )

    assert (
        entity_state(hass, "sensor", "signal_strength", "SERIAL_NUMBER").state == "34.0"
    )
    assert (
        entity_state(hass, "sensor", "skin_temperature", "SERIAL_NUMBER").state
        == "unavailable"
    )
    assert (
        entity_state(hass, "sensor", "sleep_state", "SERIAL_NUMBER").state
        == "unavailable"
    )


async def test_sensors_v2(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(hass, properties_fixture="update_properties_v2.json")
    assert len(hass.states.async_all("sensor")) == 5

    assert (
        entity_state(hass, "sensor", "battery_percentage", "SERIAL_NUMBER").state
        == "29"
    )
    assert entity_state(hass, "sensor", "heart_rate", "SERIAL_NUMBER").state == "145"
    assert (
        entity_state(hass, "sensor", "oxygen_saturation", "SERIAL_NUMBER").state == "99"
    )

    assert (
        entity_state(hass, "sensor", "signal_strength", "SERIAL_NUMBER").state == "98.0"
    )
