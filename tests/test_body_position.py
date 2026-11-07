"""Opt-in historical mapping, timestamps and isolation regressions."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.owlet.owletapi.exceptions import OwletConnectionError
from custom_components.owlet.sleep_data import BodyPositionCoordinator, latest_position

from .test_superintegration import cloud as cloud
from .test_superintegration import create_entry, entity_state, setup_entry


def document(name, **strings):
    return {
        "name": f"documents/{name}",
        "fields": {key: {"stringValue": value} for key, value in strings.items()},
    }


def service(*profiles):
    result = document("service", deviceKey="device")
    result["fields"]["serviceUserKeys"] = {
        "mapValue": {"fields": {key: {"booleanValue": True} for key in profiles}}
    }
    return result


@pytest.mark.parametrize(
    "code,expected",
    [
        (0, "no_data"),
        (1, "moving"),
        (2, "undetected"),
        (3, "no_data"),
        (4, "on_back"),
        (5, "on_back"),
        (6, "on_side"),
        (9, "on_side"),
        (10, None),
        (-1, None),
        (99, None),
        (True, None),
        ("bad", None),
    ],
)
def test_bounded_decoder_never_invents_tummy(code, expected):
    now = dt_util.utcnow()
    sample = latest_position(
        {"data": {"positionTimes": [now.timestamp()], "bodyPositions": [code]}}, now
    )
    assert sample.position == expected


@pytest.mark.parametrize("age", [-1, 301, 14400])
def test_stale_and_future_samples_rejected(age):
    now = dt_util.utcnow()
    assert (
        latest_position(
            {
                "data": {
                    "positionTimes": [(now - timedelta(seconds=age)).timestamp()],
                    "bodyPositions": [4],
                }
            },
            now,
        )
        is None
    )


def test_latest_timestamp_selected_without_assuming_sort_order():
    now = dt_util.utcnow()
    sample = latest_position(
        {
            "data": {
                "positionTimes": [
                    now.timestamp(),
                    (now - timedelta(seconds=20)).timestamp(),
                ],
                "bodyPositions": [6, 4],
            }
        },
        now,
    )
    assert sample.position == "on_side"
    assert (
        latest_position(
            {"data": {"positionTimes": [now.timestamp()], "bodyPositions": [4, 5]}}, now
        )
        is None
    )


@pytest.mark.parametrize("profiles", [[], ["baby-one", "baby-two"]])
async def test_ambiguous_mapping_never_uses_first_baby(hass, cloud, profiles):
    entry = create_entry(hass)
    primary = await setup_entry(hass, entry)
    body = BodyPositionCoordinator(hass, primary.sock, entry)
    with patch.object(
        body,
        "_query",
        side_effect=[
            [document("device", dsn="unit-one", accountKey="account")],
            [service(*profiles)],
        ],
    ) as query:
        assert await body._resolve_profile("token") is None
        assert query.await_count == 2
        assert all(call.args[1] != "serviceUsers" for call in query.await_args_list)


async def test_explicit_sock_mapping_required(hass, cloud):
    entry = create_entry(hass)
    primary = await setup_entry(hass, entry)
    body = BodyPositionCoordinator(hass, primary.sock, entry)
    for devices in [
        [],
        [document("device", dsn="other", accountKey="account")],
        [
            document("a", dsn="unit-one", accountKey="account"),
            document("b", dsn="unit-one", accountKey="account"),
        ],
    ]:
        with patch.object(body, "_query", return_value=devices):
            assert await body._resolve_profile("token") is None


async def test_profile_and_identity_cached_configured_timezone_used(hass, cloud):
    entry = create_entry(hass, options={"scan_interval": 5, "body_position": True})
    now = dt_util.utcnow()
    with (
        patch(
            "custom_components.owlet.sleep_data.BodyPositionCoordinator._query",
            side_effect=[
                [document("device", dsn="unit-one", accountKey="account")],
                [service("baby-one")],
            ],
        ) as query,
        patch(
            "custom_components.owlet.sleep_data.BodyPositionCoordinator._request",
            return_value={
                "data": {"positionTimes": [now.timestamp()], "bodyPositions": [4]}
            },
        ) as request,
        patch(
            "custom_components.owlet.owletapi.api.OwletAPI.firebase_identity",
            return_value=("id", "uid"),
        ),
    ):
        primary = await setup_entry(hass, entry)
        body = primary.body_position
        await body.async_refresh()
        assert query.await_count == 2
        assert entity_state(hass, "sensor", "body_position").state == "on_back"
        assert request.call_args.kwargs["params"]["timeZone"] == hass.config.time_zone
        assert "/accounts/account/profiles/baby-one/sleep" in request.call_args.args[1]
        assert body.update_interval == timedelta(seconds=60)
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert body._cancel_expiry is None


async def test_opt_in_can_change_live_without_reload_and_expires(hass, cloud, freezer):
    entry = create_entry(hass)
    primary = await setup_entry(hass, entry)
    assert primary.body_position is None
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
                "data": {"positionTimes": [now.timestamp()], "bodyPositions": [4]}
            },
        ),
        patch.object(primary.sock.api, "firebase_identity", return_value=("id", "uid")),
        patch.object(
            hass.config_entries, "async_reload", new_callable=AsyncMock
        ) as reload,
    ):
        hass.config_entries.async_update_entry(
            entry, options={"scan_interval": 5, "body_position": True}
        )
        await hass.async_block_till_done()
        assert entity_state(hass, "sensor", "body_position").state == "on_back"
        freezer.tick(301)
        from pytest_homeassistant_custom_component.common import async_fire_time_changed

        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert entity_state(hass, "sensor", "body_position").state == "unavailable"
        hass.config_entries.async_update_entry(
            entry, options={"scan_interval": 5, "body_position": False}
        )
        await hass.async_block_till_done()
        assert primary.body_position is None
        reload.assert_not_called()
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_slow_optional_http_never_blocks_primary_vitals(hass, cloud):
    entry = create_entry(hass)
    primary = await setup_entry(hass, entry)
    gate = asyncio.Event()
    started = asyncio.Event()

    async def slow_query(*args):
        started.set()
        await gate.wait()
        raise OwletConnectionError("optional failure")

    with (
        patch.object(primary.sock.api, "firebase_identity", return_value=("id", "uid")),
        patch(
            "custom_components.owlet.sleep_data.BodyPositionCoordinator._query",
            side_effect=slow_query,
        ),
    ):
        hass.config_entries.async_update_entry(
            entry, options={"scan_interval": 5, "body_position": True}
        )
        await asyncio.wait_for(started.wait(), 1)
        await primary.async_refresh()
        assert primary.last_update_success
        assert entity_state(hass, "sensor", "heart_rate").state == "121.0"
        gate.set()
        await hass.async_block_till_done()
        assert not primary.body_position.last_update_success
        assert primary.last_update_success
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_unload_cancels_in_flight_optional_query(hass, cloud):
    entry = create_entry(hass)
    primary = await setup_entry(hass, entry)
    started = asyncio.Event()
    gate = asyncio.Event()

    async def slow_query(*args):
        started.set()
        await gate.wait()

    with (
        patch.object(primary.sock.api, "firebase_identity", return_value=("id", "uid")),
        patch(
            "custom_components.owlet.sleep_data.BodyPositionCoordinator._query",
            side_effect=slow_query,
        ),
    ):
        hass.config_entries.async_update_entry(
            entry, options={"scan_interval": 5, "body_position": True}
        )
        await asyncio.wait_for(started.wait(), 1)
        body = primary.body_position
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert body._in_flight is None and body._cancel_expiry is None
