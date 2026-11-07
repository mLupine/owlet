"""Upgrade, lifecycle, freshness and real platform behavior regressions."""

import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.owlet import async_migrate_entry
from custom_components.owlet.const import DOMAIN
from custom_components.owlet.diagnostics import async_get_config_entry_diagnostics
from custom_components.owlet.owletapi.api import OwletAPI
from custom_components.owlet.owletapi.exceptions import (
    OwletAuthenticationError,
    OwletConnectionError,
    OwletCredentialsError,
    OwletRateLimitError,
)

TOKENS = {
    "api_token": "secret-access",
    "expiry": 9999999999,
    "refresh": "secret-refresh",
}


def create_entry(
    hass, version=2, unique_id="europe_parent@example.invalid", options=None, **data
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=version,
        unique_id=unique_id,
        data={
            "region": "europe",
            "username": "parent@example.invalid",
            **TOKENS,
            **data,
        },
        options=options if options is not None else {"scan_interval": 5},
    )
    entry.add_to_hass(hass)
    return entry


def raw_v3(now=None, **values):
    return {
        "REAL_TIME_VITALS": {
            "value": json.dumps(
                {"hr": 121, "ox": 98, "bat": 80, "chg": 0, "bso": 1, **values}
            ),
            "data_updated_at": (now or dt_util.utcnow()).isoformat(),
        }
    }


def raw_v2(now=None):
    now = now or dt_util.utcnow()
    return {
        key: {"value": value, "data_updated_at": now.isoformat()}
        for key, value in {
            "HEART_RATE": 122,
            "OXYGEN_LEVEL": 99,
            "BATT_LEVEL": 85,
            "CHARGE_STATUS": 0,
            "BASE_STATION_ON": 1,
        }.items()
    }


@pytest.fixture
def cloud():
    with (
        patch.object(OwletAPI, "authenticate", return_value=None) as authenticate,
        patch.object(
            OwletAPI,
            "get_devices",
            return_value={"response": [{"device": {"dsn": "unit-one"}}]},
        ) as devices,
        patch.object(
            OwletAPI, "get_properties", return_value={"response": raw_v3()}
        ) as properties,
    ):
        yield authenticate, devices, properties


async def setup_entry(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    return hass.data[DOMAIN][entry.entry_id]["unit-one"]


def entity_state(hass, platform, key, serial="unit-one"):
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{serial}-{key}"
    )
    return hass.states.get(entity_id) if entity_id else None


@pytest.mark.parametrize(
    "version,unique,region,username,expected",
    [
        (
            1,
            None,
            "europe",
            " Parent@Example.invalid ",
            "europe_parent@example.invalid",
        ),
        (
            1,
            "europe_parent@example.invalid",
            "europe",
            "parent@example.invalid",
            "europe_parent@example.invalid",
        ),
        (
            1,
            "parent@example.invalid",
            "world",
            "parent@example.invalid",
            "world_parent@example.invalid",
        ),
        (2, "kept-exactly", "europe", "parent@example.invalid", "kept-exactly"),
    ],
)
async def test_migration_only_changes_account_identity(
    hass, version, unique, region, username, expected
):
    entry = create_entry(
        hass,
        version=version,
        unique_id=unique,
        region=region,
        username=username,
        options={"scan_interval": 15, "future_option": "preserved"},
    )
    before = (entry.entry_id, dict(entry.data), dict(entry.options))
    assert await async_migrate_entry(hass, entry)
    assert entry.version == 2 and entry.unique_id == expected
    assert before == (entry.entry_id, dict(entry.data), dict(entry.options))
    assert await async_migrate_entry(hass, entry)
    assert entry.unique_id == expected


@pytest.mark.parametrize(
    "version,region,username",
    [
        (3, "europe", "a"),
        (0, "europe", "a"),
        (1, None, "a"),
        (1, "invalid", "a"),
        (1, "europe", None),
        (1, "europe", ""),
    ],
)
async def test_migration_refuses_invalid_or_future_entries(
    hass, version, region, username
):
    entry = create_entry(hass, version=version, region=region, username=username)
    assert not await async_migrate_entry(hass, entry)
    assert entry.version == version


async def test_migration_collision(hass):
    create_entry(hass)
    entry = create_entry(hass, version=1, unique_id="parent@example.invalid")
    assert not await async_migrate_entry(hass, entry)
    assert entry.version == 1


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"scan_interval": None},
        {"scan_interval": True},
        {"scan_interval": -5},
        {"scan_interval": "bad"},
        {"scan_interval": 5},
    ],
)
async def test_default_and_legacy_options(hass, cloud, options):
    entry = create_entry(hass, options=options)
    coordinator = await setup_entry(hass, entry)
    assert coordinator.update_interval == timedelta(seconds=5)
    assert entry.options == options


async def test_live_settings_reschedule_poll_and_token_save_does_not_reload(
    hass, cloud, freezer
):
    entry = create_entry(
        hass, options={"scan_interval": 3600, "unknown_option": "keep"}
    )
    coordinator = await setup_entry(hass, entry)
    with patch.object(
        hass.config_entries, "async_reload", new_callable=AsyncMock
    ) as reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"scan_interval": 5}
        )
        await hass.async_block_till_done()
        assert result["type"] == "create_entry"
        assert coordinator.update_interval == timedelta(seconds=5)
        assert entry.options["unknown_option"] == "keep"
        assert cloud[0].await_count == 1
        before = cloud[2].await_count
        freezer.tick(7)
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert cloud[2].await_count > before
        coordinator.sock.api._update_tokens(
            "rotated-access", 9999999999, "rotated-refresh"
        )
        await hass.async_block_till_done()
        assert entry.data["refresh"] == "rotated-refresh"
        reload.assert_not_called()
        assert hass.data[DOMAIN][entry.entry_id]["unit-one"] is coordinator


@pytest.mark.parametrize("error", [OwletAuthenticationError, OwletCredentialsError])
async def test_poll_auth_errors_are_visible_and_sanitized(hass, cloud, error):
    entry = create_entry(hass)
    coordinator = await setup_entry(hass, entry)
    cloud[2].side_effect = error("private username and token")
    with pytest.raises(
        ConfigEntryAuthFailed, match="Owlet authentication expired"
    ) as caught:
        await coordinator._async_update_data()
    assert "private" not in str(caught.value)
    assert caught.value.__suppress_context__


async def test_rotation_is_saved_on_setup_failure(hass, cloud):
    entry = create_entry(hass)

    async def fail(api, versions):
        api._update_tokens("new-access", 9999999999, "new-refresh")
        raise OwletConnectionError("private payload")

    cloud[1].side_effect = None
    with patch.object(OwletAPI, "get_devices", new=fail):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY
    assert entry.data["refresh"] == "new-refresh"


async def test_rotation_persisted_after_failed_poll_and_backoff_recovers(hass, cloud):
    entry = create_entry(hass)
    coordinator = await setup_entry(hass, entry)

    async def fail(api, serial):
        api._update_tokens("new-access", 9999999999, "new-refresh")
        raise OwletRateLimitError("limited", retry_after=90)

    with patch.object(OwletAPI, "get_properties", new=fail):
        await coordinator.async_refresh()
        assert not coordinator.last_update_success
        assert coordinator.update_interval == timedelta(seconds=90)
    assert entry.data["refresh"] == "new-refresh"
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.update_interval == timedelta(seconds=5)


async def test_partial_first_snapshot_adds_new_entities_once(hass, cloud):
    cloud[2].return_value = {"response": raw_v3(ox=None)}
    raw = cloud[2].return_value["response"]
    vitals = json.loads(raw["REAL_TIME_VITALS"]["value"])
    del vitals["ox"]
    raw["REAL_TIME_VITALS"]["value"] = json.dumps(vitals)
    entry = create_entry(hass)
    coordinator = await setup_entry(hass, entry)
    assert entity_state(hass, "sensor", "oxygen_saturation") is None
    cloud[2].return_value = {"response": {**raw_v3(), "DISCOMFORT_ALRT": {"value": 1}}}
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert entity_state(hass, "sensor", "oxygen_saturation").state == "98.0"
    assert entity_state(hass, "binary_sensor", "discomfort_alert").state == "on"
    before = set(er.async_get(hass).entities)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert set(er.async_get(hass).entities) == before


async def test_nearest_per_property_expiry_and_partial_stale_repair(
    hass, cloud, freezer
):
    now = dt_util.utcnow()
    raw = raw_v2(now)
    raw["HEART_RATE"]["data_updated_at"] = (now - timedelta(seconds=290)).isoformat()
    raw["HIGH_HR_ALRT"] = {
        "value": 0,
        "data_updated_at": (now - timedelta(days=1)).isoformat(),
    }
    cloud[2].return_value = {"response": raw}
    entry = create_entry(hass, options={"scan_interval": 3600})
    coordinator = await setup_entry(hass, entry)
    assert entity_state(hass, "sensor", "heart_rate").state == "122"
    freezer.tick(11)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert entity_state(hass, "sensor", "heart_rate").state == "unavailable"
    assert entity_state(hass, "sensor", "oxygen_saturation").state == "99"
    assert entity_state(hass, "binary_sensor", "high_heart_rate_alert").state == "off"
    assert coordinator.affected_vitals == ["heart_rate"]
    raw["HEART_RATE"]["data_updated_at"] = (
        dt_util.utcnow() - timedelta(hours=2)
    ).isoformat()
    raw["BATT_LEVEL"]["data_updated_at"] = dt_util.utcnow().isoformat()
    raw["OXYGEN_LEVEL"]["data_updated_at"] = dt_util.utcnow().isoformat()
    await coordinator.async_refresh()
    assert (DOMAIN, coordinator.issue_id) in ir.async_get(hass).issues
    raw["HEART_RATE"]["data_updated_at"] = dt_util.utcnow().isoformat()
    await coordinator.async_refresh()
    assert not coordinator.is_stale
    assert (DOMAIN, coordinator.issue_id) not in ir.async_get(hass).issues


async def test_unknown_timestamp_is_not_current_and_charging_suppresses_warning(
    hass, cloud
):
    raw = raw_v3()
    raw["REAL_TIME_VITALS"]["data_updated_at"] = "broken"
    cloud[2].return_value = {"response": raw}
    entry = create_entry(hass)
    coordinator = await setup_entry(hass, entry)
    assert coordinator.reading_status("heart_rate") == "unknown"
    assert entity_state(hass, "sensor", "heart_rate").state == "unavailable"
    assert entity_state(hass, "sensor", "last_updated").state == "unknown"
    assert coordinator.is_stale
    cloud[2].return_value = {"response": raw_v3(chg=2)}
    await coordinator.async_refresh()
    assert not coordinator.readings_expected and not coordinator.is_stale
    assert entity_state(hass, "binary_sensor", "charging").state == "on"
    assert entity_state(hass, "sensor", "heart_rate").state == "unavailable"


async def test_switch_readback_success_and_mismatch(hass, cloud):
    entry = create_entry(hass)
    await setup_entry(hass, entry)
    switch_id = er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, "unit-one-base_station_on"
    )
    cloud[2].return_value = {"response": raw_v3(bso=0)}
    with patch.object(
        OwletAPI, "post_command", return_value={"datapoint": {"value": "accepted"}}
    ) as command:
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": switch_id}, blocking=True
        )
        assert hass.states.get(switch_id).state == "off"
        args = command.call_args.args
        assert args[1] == "BASE_STATION_ON_CMD"
        assert json.loads(args[2]["datapoint"]["value"])["val"] == "false"
        with pytest.raises(HomeAssistantError, match="did not confirm"):
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": switch_id}, blocking=True
            )


async def test_diagnostics_excludes_all_identifiers_and_unknown_payloads(hass, cloud):
    raw = raw_v3()
    raw["FUTURE_SECRET"] = {"value": "sensitive-baby-payload"}
    cloud[2].return_value = {"response": raw}
    entry = create_entry(
        hass, options={"scan_interval": 5, "future_secret": "private-value"}
    )
    await setup_entry(hass, entry)
    encoded = json.dumps(await async_get_config_entry_diagnostics(hass, entry))
    for secret in [
        "secret-access",
        "secret-refresh",
        "parent@example.invalid",
        "unit-one",
        "sensitive-baby-payload",
        "private-value",
    ]:
        assert secret not in encoded


async def test_two_devices_are_independent_and_unload_cleans_timers(hass, cloud):
    cloud[1].return_value = {
        "response": [{"device": {"dsn": serial}} for serial in ("unit-one", "unit-two")]
    }
    cloud[2].side_effect = lambda serial: {
        "response": raw_v3(hr=111 if serial == "unit-one" else 133)
    }
    entry = create_entry(hass)
    coordinator = await setup_entry(hass, entry)
    assert entity_state(hass, "sensor", "heart_rate").state == "111.0"
    assert entity_state(hass, "sensor", "heart_rate", "unit-two").state == "133.0"
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert coordinator._cancel_expiry is None
    assert entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.parametrize("version", [1, 2])
async def test_upgrade_preserves_registry_overrides_and_real_recorder_rows(
    recorder_mock, hass, cloud, version
):
    from homeassistant.components.recorder.db_schema import States, StatesMeta
    from pytest_homeassistant_custom_component.components.recorder.common import (
        async_recorder_block_till_done,
        async_trigger_db_commit,
    )
    from sqlalchemy import select

    entry = create_entry(
        hass,
        version=version,
        unique_id="parent@example.invalid"
        if version == 1
        else "europe_parent@example.invalid",
        options={"scan_interval": 30, "unknown_option": "keep"},
    )
    before_data, before_options, before_id = (
        dict(entry.data),
        dict(entry.options),
        entry.entry_id,
    )
    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "unit-one")}
    )
    pulse = registry.async_get_or_create(
        "sensor", DOMAIN, "unit-one-heart_rate", config_entry=entry, device_id=device.id
    )
    pulse = registry.async_update_entity(
        pulse.entity_id,
        new_entity_id="sensor.user_selected_pulse",
        name="My chosen pulse",
        icon="mdi:heart",
    )
    switch = registry.async_get_or_create(
        "switch",
        DOMAIN,
        "unit-one-base_station_on",
        config_entry=entry,
        device_id=device.id,
    )
    await hass.async_start()
    hass.states.async_set(pulse.entity_id, "111")
    await hass.async_block_till_done()
    async_trigger_db_commit(hass)
    await async_recorder_block_till_done(hass)

    def recorded():
        with recorder_mock.get_session() as session:
            return list(
                session.execute(
                    select(States.state_id, States.metadata_id, States.state)
                    .join(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
                    .where(StatesMeta.entity_id == pulse.entity_id)
                )
            )

    before = await hass.async_add_executor_job(recorded)
    assert any(row.state == "111" for row in before)
    hass.states.async_remove(pulse.entity_id)
    await setup_entry(hass, entry)
    for _ in range(2):
        current = registry.async_get(pulse.entity_id)
        assert (
            current.id == pulse.id
            and current.unique_id == pulse.unique_id
            and current.device_id == device.id
        )
        assert current.name == "My chosen pulse" and current.icon == "mdi:heart"
        assert registry.async_get(switch.entity_id).id == switch.id
        assert hass.states.get(pulse.entity_id).state == "121.0"
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert (entry.entry_id, dict(entry.data), dict(entry.options)) == (
        before_id,
        before_data,
        before_options,
    )
    assert entry.version == 2 and entry.unique_id == "europe_parent@example.invalid"
    async_trigger_db_commit(hass)
    await async_recorder_block_till_done(hass)
    after = await hass.async_add_executor_job(recorded)
    assert set(before).issubset(after)
    assert any(row.state == "121.0" for row in after)
    assert len({row.metadata_id for row in after}) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("sleep_code", [0, 42, -1, True, None])
async def test_unknown_sleep_never_becomes_awake(hass, cloud, sleep_code):
    cloud[2].return_value = {"response": raw_v3(ss=sleep_code)}
    entry = create_entry(hass)
    await setup_entry(hass, entry)
    assert entity_state(hass, "binary_sensor", "sleep_state").state == "unknown"
    assert entity_state(hass, "sensor", "sleep_state").state == "unknown"


async def test_independently_updated_v3_status_uses_its_own_timestamp(hass, cloud):
    raw = raw_v3()
    raw["BATTERY_STATUS"] = {
        "value": 3,
        "data_updated_at": (dt_util.utcnow() - timedelta(hours=2)).isoformat(),
    }
    raw["LOW_OX_ALRT"] = {
        "value": 0,
        "data_updated_at": (dt_util.utcnow() - timedelta(days=1)).isoformat(),
    }
    cloud[2].return_value = {"response": raw}
    entry = create_entry(hass)
    await setup_entry(hass, entry)
    assert entity_state(hass, "sensor", "heart_rate").state == "121.0"
    assert entity_state(hass, "sensor", "battery_status").state == "unavailable"
    assert entity_state(hass, "binary_sensor", "low_oxygen_alert").state == "off"


async def test_failed_poll_never_speeds_up_a_long_configured_interval(hass, cloud):
    entry = create_entry(hass, options={"scan_interval": 3600})
    coordinator = await setup_entry(hass, entry)
    cloud[2].side_effect = OwletRateLimitError("limited", retry_after=90)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.update_interval == timedelta(seconds=3600)


@pytest.mark.parametrize(
    "error,expected",
    [
        (OwletCredentialsError, ConfigEntryState.SETUP_ERROR),
        (OwletConnectionError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_constructor_errors_use_sanitized_setup_mapping(hass, error, expected):
    entry = create_entry(hass)
    with patch("custom_components.owlet.OwletAPI", side_effect=error("private data")):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state == expected


async def test_change_only_v2_states_survive_old_change_times(hass, cloud):
    from .cloud_fixtures import load

    raw = {
        row["property"]["name"]: row["property"] for row in load("properties_v2.json")
    }
    now = dt_util.utcnow()
    for name in ("HEART_RATE", "OXYGEN_LEVEL"):
        raw[name]["data_updated_at"] = now.isoformat()
    for name, value in (
        ("BATT_LEVEL", 85),
        ("CHARGE_STATUS", 0),
        ("BASE_STATION_ON", 1),
    ):
        assert raw[name]["track_only_changes"] is True
        raw[name]["value"] = value
        raw[name]["data_updated_at"] = (now - timedelta(days=1)).isoformat()
    cloud[2].return_value = {"response": raw}
    coordinator = await setup_entry(hass, create_entry(hass))
    assert entity_state(hass, "sensor", "battery_percentage").state == "85"
    assert entity_state(hass, "binary_sensor", "charging").state == "off"
    assert entity_state(hass, "switch", "base_station_on").state == "on"
    assert not coordinator.is_stale
    raw["CHARGE_STATUS"]["value"] = 1
    for name in ("HEART_RATE", "OXYGEN_LEVEL"):
        raw[name]["data_updated_at"] = (now - timedelta(hours=2)).isoformat()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.readings_expected
    assert not coordinator.is_stale
    assert (DOMAIN, coordinator.issue_id) not in ir.async_get(hass).issues
    assert entity_state(hass, "binary_sensor", "charging").state == "on"


@pytest.mark.parametrize("payload", ["broken json", "{}", '{"bat":80}'])
async def test_never_observed_vitals_are_unhealthy_until_recovered(
    hass, cloud, freezer, payload
):
    raw = raw_v3()
    raw["REAL_TIME_VITALS"]["value"] = payload
    cloud[2].return_value = {"response": raw}
    coordinator = await setup_entry(hass, create_entry(hass))
    assert coordinator.affected_vitals == ["heart_rate", "oxygen_saturation"]
    assert coordinator.is_stale
    freezer.tick(3601)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert (DOMAIN, coordinator.issue_id) in ir.async_get(hass).issues
    cloud[2].return_value = {"response": raw_v3()}
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.is_stale
    assert (DOMAIN, coordinator.issue_id) not in ir.async_get(hass).issues
    assert entity_state(hass, "sensor", "heart_rate").state == "121.0"


@pytest.mark.parametrize("version", [2, 3])
async def test_invalid_present_vitals_warn_despite_advancing_timestamps(
    hass, cloud, freezer, version
):
    def invalid_snapshot():
        if version == 3:
            return raw_v3(hr="invalid", ox=None)
        raw = raw_v2()
        raw["HEART_RATE"]["value"] = "invalid"
        raw["OXYGEN_LEVEL"]["value"] = None
        return raw

    cloud[2].return_value = {"response": invalid_snapshot()}
    coordinator = await setup_entry(hass, create_entry(hass))
    assert coordinator.is_stale
    assert coordinator.affected_vitals == ["heart_rate", "oxygen_saturation"]
    for _ in range(4):
        freezer.tick(901)
        cloud[2].return_value = {"response": invalid_snapshot()}
        await coordinator.async_refresh()
    assert (DOMAIN, coordinator.issue_id) in ir.async_get(hass).issues
    cloud[2].return_value = {"response": raw_v3() if version == 3 else raw_v2()}
    await coordinator.async_refresh()
    assert not coordinator.is_stale
    assert not coordinator._unknown_since
    assert (DOMAIN, coordinator.issue_id) not in ir.async_get(hass).issues
    freezer.tick(7200)
    cloud[2].return_value = {"response": invalid_snapshot()}
    await coordinator.async_refresh()
    assert coordinator.is_stale
    assert (DOMAIN, coordinator.issue_id) not in ir.async_get(hass).issues


async def test_failed_multi_sock_setup_cancels_optional_work(hass, cloud):
    import asyncio

    from custom_components.owlet.sleep_data import BodyPositionCoordinator

    started = asyncio.Event()
    cancelled = asyncio.Event()
    release = asyncio.Event()
    coordinators = []

    async def historical_request(body):
        coordinators.append(body)
        started.set()
        try:
            await release.wait()
        finally:
            cancelled.set()

    async def properties(serial):
        if serial == "unit-one":
            return {"response": raw_v3()}
        await started.wait()
        raise OwletConnectionError("second sock failed")

    cloud[1].return_value = {
        "response": [{"device": {"dsn": serial}} for serial in ("unit-one", "unit-two")]
    }
    cloud[2].side_effect = properties
    with patch.object(BodyPositionCoordinator, "_fetch_position", historical_request):
        entry = create_entry(hass, options={"body_position": True, "scan_interval": 5})
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert cancelled.is_set()
    assert all(body._stopped and body._in_flight is None for body in coordinators)
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
