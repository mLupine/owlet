"""Allowlisted operational diagnostics without account or device identifiers."""

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
                "readings_expected": coordinator.readings_expected,
                "capabilities": sorted(coordinator.sock.capabilities),
                "freshness": {
                    key: coordinator.reading_status(key)
                    for key in coordinator.sock.capabilities
                },
                "body_position_enabled": coordinator.body_position_enabled,
            }
        )
    return {"entry_version": entry.version, "devices": devices}
