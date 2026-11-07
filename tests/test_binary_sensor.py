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

    assert len(hass.states.async_all("binary_sensor")) == 17

    assert (
        entity_state(hass, "binary_sensor", "charging", "SERIAL_NUMBER").state == "off"
    )
    assert (
        entity_state(
            hass, "binary_sensor", "high_heart_rate_alert", "SERIAL_NUMBER"
        ).state
        == "off"
    )
    assert (
        entity_state(
            hass, "binary_sensor", "low_heart_rate_alert", "SERIAL_NUMBER"
        ).state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "high_oxygen_alert", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "low_oxygen_alert", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "low_battery_alert", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "lost_power_alert", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "sock_disconnected", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "sock_off", "SERIAL_NUMBER").state == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "sleep_state", "SERIAL_NUMBER").state
        == "off"
    )


async def test_sensors_awake(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(
        hass, properties_fixture="update_properties_awake.json"
    )

    assert len(hass.states.async_all("binary_sensor")) == 17

    assert (
        entity_state(hass, "binary_sensor", "charging", "SERIAL_NUMBER").state == "off"
    )
    assert (
        entity_state(
            hass, "binary_sensor", "high_heart_rate_alert", "SERIAL_NUMBER"
        ).state
        == "on"
    )
    assert (
        entity_state(
            hass, "binary_sensor", "low_heart_rate_alert", "SERIAL_NUMBER"
        ).state
        == "on"
    )
    assert (
        entity_state(hass, "binary_sensor", "high_oxygen_alert", "SERIAL_NUMBER").state
        == "on"
    )
    assert (
        entity_state(hass, "binary_sensor", "low_oxygen_alert", "SERIAL_NUMBER").state
        == "on"
    )
    assert (
        entity_state(hass, "binary_sensor", "low_battery_alert", "SERIAL_NUMBER").state
        == "on"
    )
    assert (
        entity_state(hass, "binary_sensor", "lost_power_alert", "SERIAL_NUMBER").state
        == "on"
    )
    assert (
        entity_state(hass, "binary_sensor", "sock_disconnected", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "sock_off", "SERIAL_NUMBER").state == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "sleep_state", "SERIAL_NUMBER").state
        == "on"
    )


async def test_sensors_charging(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(
        hass, properties_fixture="update_properties_charging.json"
    )

    assert len(hass.states.async_all("binary_sensor")) == 17

    assert (
        entity_state(hass, "binary_sensor", "charging", "SERIAL_NUMBER").state == "on"
    )
    assert (
        entity_state(
            hass, "binary_sensor", "high_heart_rate_alert", "SERIAL_NUMBER"
        ).state
        == "off"
    )
    assert (
        entity_state(
            hass, "binary_sensor", "low_heart_rate_alert", "SERIAL_NUMBER"
        ).state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "high_oxygen_alert", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "low_oxygen_alert", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "low_battery_alert", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "lost_power_alert", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "sock_disconnected", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "sock_off", "SERIAL_NUMBER").state == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "sleep_state", "SERIAL_NUMBER").state
        == "unavailable"
    )


async def test_sensors_v2(hass: HomeAssistant) -> None:
    """Test sensor values."""
    await async_init_integration(hass, properties_fixture="update_properties_v2.json")
    assert len(hass.states.async_all("binary_sensor")) == 11

    assert (
        entity_state(hass, "binary_sensor", "charging", "SERIAL_NUMBER").state == "off"
    )
    assert (
        entity_state(
            hass, "binary_sensor", "high_heart_rate_alert", "SERIAL_NUMBER"
        ).state
        == "off"
    )
    assert (
        entity_state(
            hass, "binary_sensor", "low_heart_rate_alert", "SERIAL_NUMBER"
        ).state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "low_oxygen_alert", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "low_battery_alert", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(
            hass, "binary_sensor", "critical_battery_alert", "SERIAL_NUMBER"
        ).state
        == "off"
    )
    assert (
        entity_state(
            hass, "binary_sensor", "critical_oxygen_alert", "SERIAL_NUMBER"
        ).state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "sock_disconnected", "SERIAL_NUMBER").state
        == "off"
    )
    assert (
        entity_state(hass, "binary_sensor", "sock_off", "SERIAL_NUMBER").state == "off"
    )
