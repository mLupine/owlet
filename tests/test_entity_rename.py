"""Registry rename lifecycle and legacy polling regressions."""

from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.owlet.const import DOMAIN
from custom_components.owlet.owletapi.api import OwletAPI

from .test_body_position import document, service
from .test_superintegration import cloud as cloud
from .test_superintegration import create_entry, setup_entry


async def test_registry_rename_retains_switch_commands(hass, cloud):
    entry = create_entry(hass)
    await setup_entry(hass, entry)
    registry = er.async_get(hass)
    original = registry.async_get_entity_id(
        "switch", DOMAIN, "unit-one-base_station_on"
    )
    renamed = "switch.renamed_owlet_base"
    registry.async_update_entity(original, new_entity_id=renamed)
    await hass.async_block_till_done()
    with patch.object(OwletAPI, "post_command") as post:
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": renamed}, blocking=True
        )
        await hass.async_block_till_done()
        post.assert_awaited_once()
    assert hass.states.get(original) is None
    assert hass.states.get(renamed).attributes["command_status"] == "pending"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_registry_rename_resubscribes_body_position(hass, cloud):
    entry = create_entry(hass, options={"body_position": True})
    now = dt_util.utcnow()
    with (
        patch(
            "custom_components.owlet.sleep_data.BodyPositionCoordinator._query",
            side_effect=[
                [document("device", dsn="unit-one", accountKey="account")],
                [service("baby-one")],
            ],
        ),
        patch(
            "custom_components.owlet.sleep_data.BodyPositionCoordinator._request",
            return_value={
                "data": {"positionTimes": [now.timestamp()], "bodyPositions": [4]},
            },
        ) as request,
        patch.object(OwletAPI, "firebase_identity", return_value=("id", "uid")),
    ):
        primary = await setup_entry(hass, entry)
        body = primary.body_position
        await body.async_refresh()
        registry = er.async_get(hass)
        original = registry.async_get_entity_id(
            "sensor", DOMAIN, "unit-one-body_position"
        )
        renamed = "sensor.renamed_owlet_position"
        registry.async_update_entity(original, new_entity_id=renamed)
        await hass.async_block_till_done()
        assert len(body._listeners) == 1
        request.return_value = {
            "data": {"positionTimes": [now.timestamp()], "bodyPositions": [6]}
        }
        await body.async_refresh()
        assert hass.states.get(renamed).state == "on_side"
        assert hass.states.get(original) is None
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert not body._listeners
        assert body._cancel_expiry is None


async def test_legacy_long_interval_survives_setup_and_options(hass, cloud):
    entry = create_entry(hass, options={"scan_interval": 7200, "custom": "kept"})
    primary = await setup_entry(hass, entry)
    assert primary.update_interval.total_seconds() == 7200
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    validated = flow["data_schema"](
        {
            "scan_interval": 7200,
            "stale_threshold": 0,
            "activation_interval": 30,
            "body_position": False,
        }
    )
    assert validated["scan_interval"] == 7200
    assert entry.options["custom"] == "kept"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_historical_http_failure_invalidates_profile_cache(hass, cloud):
    from unittest.mock import AsyncMock

    import pytest
    from homeassistant.helpers.update_coordinator import UpdateFailed

    from custom_components.owlet.sleep_data import BodyPositionCoordinator

    entry = create_entry(hass, options={"body_position": False})
    primary = await setup_entry(hass, entry)
    body = BodyPositionCoordinator(hass, primary.sock, entry)
    body._profile = object()
    body._profile_expiry = float("inf")
    response = AsyncMock()
    response.status = 503
    response.__aenter__.return_value = response
    with patch.object(primary.sock.api.session, "request", return_value=response):
        with pytest.raises(UpdateFailed):
            await body._request("GET", "https://example.invalid/sleep", "token")
    assert body._profile is None
    assert body._profile_expiry == 0
    await body.async_close()
    assert await hass.config_entries.async_unload(entry.entry_id)
