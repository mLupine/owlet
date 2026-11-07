"""Cross-family review regressions at the HA service and source boundaries."""

import asyncio
import json
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import icon as icon_helper
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.owlet.const import DOMAIN
from custom_components.owlet.diagnostics import async_get_config_entry_diagnostics
from custom_components.owlet.owletapi.api import OwletAPI
from custom_components.owlet.owletapi.exceptions import OwletConnectionError

from .test_superintegration import cloud as cloud
from .test_superintegration import (
    create_entry,
    entity_state,
    raw_v2,
    raw_v3,
    setup_entry,
)


def switch_id(hass):
    return er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, "unit-one-base_station_on"
    )


async def command(hass, state):
    await hass.services.async_call(
        "switch",
        "turn_on" if state else "turn_off",
        {"entity_id": switch_id(hass)},
        blocking=True,
    )


async def advance(hass, freezer, seconds):
    freezer.tick(seconds)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def test_command_applies_after_three_readbacks(hass, cloud, freezer):
    entry = create_entry(hass, options={"scan_interval": 120})
    await setup_entry(hass, entry)
    registry_entry = er.async_get(hass).async_get(switch_id(hass))
    cloud[2].side_effect = [{"response": raw_v3(bso=value)} for value in (1, 1, 0)]
    with patch.object(OwletAPI, "post_command"):
        await command(hass, False)
        await hass.async_block_till_done()
        assert hass.states.get(switch_id(hass)).state == "on"
        assert (
            hass.states.get(switch_id(hass)).attributes["command_status"] == "pending"
        )
        await advance(hass, freezer, 2)
        assert (
            hass.states.get(switch_id(hass)).attributes["command_status"] == "pending"
        )
        await advance(hass, freezer, 2)
        assert hass.states.get(switch_id(hass)).state == "off"
        assert (
            hass.states.get(switch_id(hass)).attributes["command_status"] == "confirmed"
        )
        assert er.async_get(hass).async_get(switch_id(hass)).id == registry_entry.id
        before = cloud[2].await_count
        await advance(hass, freezer, 31)
        assert cloud[2].await_count == before


async def test_command_timeout_is_visible_and_later_readback_can_confirm(
    hass, cloud, freezer, caplog
):
    entry = create_entry(hass, options={"scan_interval": 120})
    coordinator = await setup_entry(hass, entry)
    with patch.object(OwletAPI, "post_command"):
        await command(hass, False)
        await hass.async_block_till_done()
        await advance(hass, freezer, 31)
    assert hass.states.get(switch_id(hass)).state == "on"
    assert (
        hass.states.get(switch_id(hass)).attributes["command_status"] == "unconfirmed"
    )
    assert "cloud state remains unconfirmed" in caplog.text
    before = cloud[2].await_count
    await advance(hass, freezer, 3)
    assert cloud[2].await_count == before
    cloud[2].return_value = {"response": raw_v3(bso=0)}
    await coordinator.async_refresh()
    assert hass.states.get(switch_id(hass)).attributes["command_status"] == "confirmed"


async def test_command_failure_rejects_service_without_changing_physical_state(
    hass, cloud, caplog
):
    await setup_entry(hass, create_entry(hass))
    with patch.object(
        OwletAPI, "post_command", side_effect=OwletConnectionError("private-secret")
    ):
        with pytest.raises(HomeAssistantError, match="command failed") as caught:
            await command(hass, False)
    assert "private-secret" not in str(caught.value) + caplog.text
    assert hass.states.get(switch_id(hass)).state == "on"
    assert hass.states.get(switch_id(hass)).attributes["command_status"] is None


async def test_overlapping_commands_serialize_posts_and_last_acceptance_wins(
    hass, cloud, freezer
):
    await setup_entry(hass, create_entry(hass, options={"scan_interval": 120}))
    started = asyncio.Event()
    release = asyncio.Event()
    values = []

    async def post(serial, name, payload):
        values.append(json.loads(payload["datapoint"]["value"])["val"])
        if len(values) == 1:
            started.set()
            await release.wait()

    with patch.object(OwletAPI, "post_command", side_effect=post):
        first = asyncio.create_task(command(hass, False))
        await started.wait()
        second = asyncio.create_task(command(hass, True))
        await asyncio.sleep(0)
        assert values == ["false"]
        release.set()
        await asyncio.gather(first, second)
        await hass.async_block_till_done()
    assert values == ["false", "true"]
    state = hass.states.get(switch_id(hass))
    assert state.state == "on"
    assert state.attributes["requested_state"] is True
    assert state.attributes["command_status"] == "confirmed"
    before = cloud[2].await_count
    await advance(hass, freezer, 31)
    assert cloud[2].await_count == before


async def test_unload_cancels_and_joins_inflight_command_readback(hass, cloud, freezer):
    entry = create_entry(hass, options={"scan_interval": 120})
    await setup_entry(hass, entry)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocked(serial):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    cloud[2].side_effect = blocked
    with patch.object(OwletAPI, "post_command"):
        await command(hass, False)
        await started.wait()
        assert await hass.config_entries.async_unload(entry.entry_id)
    assert cancelled.is_set()
    before = cloud[2].await_count
    await advance(hass, freezer, 40)
    assert cloud[2].await_count == before
    assert entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.parametrize("enabled", [False, True])
async def test_unmodified_v2_capture_at_capture_time_preserves_legacy_default(
    hass, cloud, freezer, enabled
):
    capture = Path("tests/fixtures/update_properties_v2.json").read_bytes()
    assert (
        sha256(capture).hexdigest()
        == "61515c0acf2824adbc10ff11f496d05b723435ae348910c9f7437fb799553132"
    )
    freezer.move_to("2023-11-20T14:05:01+00:00")
    cloud[2].return_value = json.loads(capture)
    options = {"scan_interval": 5, "future_option": "keep"}
    if enabled:
        options["stale_threshold"] = 5
    entry = create_entry(hass, options=options)
    before = (entry.entry_id, dict(entry.data), dict(entry.options))
    coordinator = await setup_entry(hass, entry)
    assert entity_state(hass, "sensor", "heart_rate").state == "145"
    assert entity_state(hass, "sensor", "battery_percentage").state == "29"
    assert entity_state(hass, "switch", "base_station_on").state == "on"
    assert entity_state(hass, "sensor", "oxygen_saturation").state == (
        "unavailable" if enabled else "99"
    )
    assert entity_state(hass, "sensor", "signal_strength").state == (
        "unavailable" if enabled else "98.0"
    )
    assert coordinator.is_stale is enabled
    assert ((DOMAIN, coordinator.issue_id) in ir.async_get(hass).issues) is enabled
    assert before == (entry.entry_id, dict(entry.data), dict(entry.options))
    assert coordinator.sock.property_timestamp("oxygen_saturation").isoformat() == (
        "2023-11-20T12:22:26+00:00"
    )


@pytest.mark.parametrize("threshold", [1, 5])
async def test_options_reject_threshold_not_strictly_longer_than_poll(
    hass, cloud, threshold
):
    entry = create_entry(hass, options={"future_option": "keep"})
    await setup_entry(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"scan_interval": 300, "stale_threshold": threshold},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"stale_threshold": "stale_threshold_too_short"}
    assert entry.options == {"future_option": "keep"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 300, "stale_threshold": 6}
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert entry.options["future_option"] == "keep"
    assert hass.data[DOMAIN][entry.entry_id]["unit-one"].stale_seconds == 360


async def test_persisted_incompatible_options_are_honored_and_diagnosed(hass, cloud):
    entry = create_entry(hass, options={"scan_interval": 3600, "stale_threshold": 5})
    coordinator = await setup_entry(hass, entry)
    assert coordinator.base_interval == 3600
    assert coordinator.stale_seconds == 300
    assert entry.options == {"scan_interval": 3600, "stale_threshold": 5}
    diagnostic = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostic["devices"][0]["freshness_options_compatible"] is False
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 3600, "stale_threshold": 0}
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert coordinator.stale_seconds == 0
    assert coordinator.freshness_options_compatible


@pytest.mark.parametrize(
    "idle_key,idle_value", [("CHARGE_STATUS", 1), ("BASE_STATION_ON", 0)]
)
async def test_idle_suppression_needs_recent_source_upload_and_recovers(
    hass, cloud, freezer, idle_key, idle_value
):
    now = dt_util.utcnow()
    raw = raw_v2(now - timedelta(hours=2))
    for key in ("CHARGE_STATUS", "BASE_STATION_ON", "BATT_LEVEL"):
        raw[key]["track_only_changes"] = True
    raw[idle_key]["value"] = idle_value
    raw["SOCK_CONNECTION"] = {"value": 1, "data_updated_at": now.isoformat()}
    cloud[2].return_value = {"response": raw}
    entry = create_entry(hass, options={"scan_interval": 5, "stale_threshold": 1})
    coordinator = await setup_entry(hass, entry)
    assert not coordinator.is_stale
    assert not coordinator.readings_expected
    await advance(hass, freezer, 61)
    assert coordinator.readings_expected
    assert coordinator.is_stale
    assert coordinator.last_update_success
    assert (DOMAIN, coordinator.issue_id) in ir.async_get(hass).issues
    assert coordinator.reading_status("charging") == "state"
    assert coordinator.reading_available("charging")
    for _ in range(2):
        await coordinator.async_refresh()
        assert coordinator.is_stale
    raw["SOCK_CONNECTION"]["data_updated_at"] = dt_util.utcnow().isoformat()
    await coordinator.async_refresh()
    assert not coordinator.is_stale
    assert (DOMAIN, coordinator.issue_id) not in ir.async_get(hass).issues
    raw.update(raw_v2())
    await coordinator.async_refresh()
    assert not coordinator.is_stale
    assert coordinator.readings_expected
    assert entity_state(hass, "sensor", "heart_rate").state == "122"


async def test_dutch_translations_and_icon_metadata_load(hass, cloud):
    await setup_entry(hass, create_entry(hass))
    resources = await async_get_translations(hass, "nl", "entity", {DOMAIN})
    assert resources["component.owlet.entity.sensor.heartrate.name"] == "Hartslag"
    assert resources["component.owlet.entity.switch.base_on.name"] == "Basisstation aan"
    options = await async_get_translations(hass, "nl", "options", {DOMAIN})
    assert (
        "langer" in options["component.owlet.options.error.stale_threshold_too_short"]
    )
    icons = json.loads(Path("custom_components/owlet/icons.json").read_text())
    assert icons["entity"]["sensor"]["heartrate"]["default"] == "mdi:heart-pulse"
    assert (
        entity_state(hass, "sensor", "heart_rate").attributes["icon"]
        == "mdi:heart-pulse"
    )
    if hasattr(icon_helper, "async_get_icons"):
        loaded = await icon_helper.async_get_icons(hass, "entity", {DOMAIN})
        assert loaded[DOMAIN]["sensor"]["heartrate"]["default"] == "mdi:heart-pulse"


async def test_cached_matching_state_cannot_confirm_without_a_new_poll(hass, cloud):
    entry = create_entry(hass)
    coordinator = await setup_entry(hass, entry)
    started = asyncio.Event()

    async def blocked(serial):
        started.set()
        await asyncio.Event().wait()

    cloud[2].side_effect = blocked
    with patch.object(OwletAPI, "post_command"):
        await command(hass, True)
        await started.wait()
        coordinator.async_update_listeners()
        assert (
            hass.states.get(switch_id(hass)).attributes["command_status"] == "pending"
        )
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_unload_cancels_and_joins_inflight_command_post(hass, cloud):
    entry = create_entry(hass)
    await setup_entry(hass, entry)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocked(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with patch.object(OwletAPI, "post_command", side_effect=blocked):
        service = asyncio.create_task(command(hass, False))
        await started.wait()
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert cancelled.is_set()
        result = await asyncio.gather(service, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)
