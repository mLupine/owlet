"""Allowlisted operational diagnostics without account or device identifiers."""

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.loader import async_get_integration

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry) -> dict:
    devices = []
    for coordinator in hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).values():
        devices.append(
            {
                "generation": coordinator.sock.version,
                "poll_success": coordinator.last_update_success,
                "poll_seconds": coordinator.base_interval,
                "stale_threshold_seconds": coordinator.stale_seconds,
                "freshness_options_compatible": coordinator.freshness_options_compatible,
                "readings_expected": coordinator.readings_expected,
                "capabilities": sorted(coordinator.sock.capabilities),
                "freshness": {
                    key: coordinator.reading_status(key)
                    for key in coordinator.sock.capabilities
                },
                "body_position_enabled": coordinator.body_position_enabled,
            }
        )
    integration = await async_get_integration(hass, DOMAIN)
    return {
        "entry_version": entry.version,
        "integration_version": integration.version,
        "homeassistant_version": HA_VERSION,
        "devices": devices,
    }
