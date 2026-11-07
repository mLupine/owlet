"""Regressions for discovery token rotation and dashboard controls."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from custom_components.owlet.config_flow import authenticate_account


async def test_discovery_rotated_tokens_are_authoritative(hass):
    initial = {"api_token": "old", "refresh": "old-refresh", "expiry": 100}
    rotated = {"api_token": "new", "refresh": "new-refresh", "expiry": 200}
    with patch("custom_components.owlet.config_flow.OwletAPI") as factory:
        api = factory.return_value
        api.tokens = initial.copy()
        api.authenticate = AsyncMock(return_value=initial)
        api.close = AsyncMock()

        async def discover(versions):
            api.tokens = rotated.copy()
            return []

        api.get_devices = AsyncMock(side_effect=discover)
        tokens, errors = await authenticate_account(hass, "world", "user", "password")
    assert not errors
    assert tokens == rotated


def test_dashboard_base_station_controls_use_switch_domain():
    for name, key in [
        ("owlet.yaml", "base_station_on"),
        ("owlet_nl.yaml", "basisstation_aan"),
    ]:
        content = (Path("dashboards") / name).read_text()
        assert f"entity: switch.owlet_sock_serial_number_{key}" in content
        assert f"entity: binary_sensor.owlet_sock_serial_number_{key}" not in content
