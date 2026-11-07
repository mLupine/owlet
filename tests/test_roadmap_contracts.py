"""Remaining roadmap contracts through public flows, registries and parsing."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.owlet.config_flow import authenticate_account
from custom_components.owlet.const import DOMAIN
from custom_components.owlet.coordinator import store_tokens
from custom_components.owlet.diagnostics import async_get_config_entry_diagnostics
from custom_components.owlet.owletapi.api import OwletAPI
from custom_components.owlet.owletapi.const import REGION_INFO
from custom_components.owlet.owletapi.exceptions import OwletConnectionError

from .cloud_fixtures import FakeSession, mock_refresh
from .test_review_regressions import command
from .test_superintegration import cloud as cloud
from .test_superintegration import (
    create_entry,
    entity_state,
    raw_v2,
    raw_v3,
    setup_entry,
)


@pytest.mark.parametrize("stage", ["authenticate", "get_devices", "get_properties"])
async def test_cancelled_setup_cleans_client_and_runtime(hass, cloud, stage):
    entry = create_entry(hass, options={"body_position": True, "stale_threshold": 5})
    started = asyncio.Event()
    cancelled = asyncio.Event()
    clients = []

    async def blocked(api, *args):
        clients.append(api)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with patch.object(OwletAPI, stage, new=blocked):
        task = asyncio.create_task(hass.config_entries.async_setup(entry.entry_id))
        await started.wait()
        task.cancel()
        results = await asyncio.gather(task, return_exceptions=True)
    assert results[0] is False or isinstance(results[0], asyncio.CancelledError)
    assert cancelled.is_set()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
    assert not ir.async_get(hass).issues
    assert all(not api.session.closed for api in clients)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_rotation_survives_partial_access_exchange_and_storage_reconstruction(
    hass,
):
    session = FakeSession()
    entry = create_entry(hass, options={"future": "keep"})
    api = OwletAPI(
        "europe", token="old", expiry=0, refresh="old-refresh", session=session
    )
    api.tokens_updated = lambda tokens: store_tokens(hass, entry, tokens)
    mock_refresh(session)
    session.replies[("GET", REGION_INFO["europe"]["url_mini"])].clear()

    session.get(REGION_INFO["europe"]["url_mini"], status=503)
    with pytest.raises(OwletConnectionError):
        await api.authenticate()
    assert entry.data["api_token"] == "old"
    assert entry.data["refresh"] == "new_refresh"
    persisted = json.loads(json.dumps(entry.as_dict()))
    assert "password" not in persisted["data"]
    restored = OwletAPI(
        persisted["data"]["region"],
        token=persisted["data"]["api_token"],
        expiry=persisted["data"]["expiry"],
        refresh=persisted["data"]["refresh"],
        session=session,
    )
    mock_refresh(session)
    await restored.authenticate()
    assert restored.tokens["api_token"] == "new_token"
    assert persisted["options"] == {"future": "keep"}
    assert persisted["entry_id"] == entry.entry_id


@pytest.mark.parametrize("stage", ["get_mini_token", "token_sign_in"])
async def test_cancelled_exchange_preserves_rotated_refresh(hass, stage):

    session = FakeSession()
    entry = create_entry(hass)
    api = OwletAPI(
        "europe", token="old", expiry=0, refresh="old-refresh", session=session
    )
    api.tokens_updated = lambda tokens: store_tokens(hass, entry, tokens)
    mock_refresh(session)
    started = asyncio.Event()

    async def blocked(*args):
        started.set()
        await asyncio.Event().wait()

    with patch.object(api, stage, side_effect=blocked):
        task = asyncio.create_task(api.authenticate())
        await started.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert entry.data["api_token"] == "old"
    assert entry.data["refresh"] == "new_refresh"
    assert not api._auth_lock.locked()
    mock_refresh(session)
    await api.authenticate()
    assert api.tokens["api_token"] == "new_token"
    assert len(session.requests[("POST", REGION_INFO["europe"]["url_signin"])]) == 1


async def test_flow_constructor_failure_is_sanitized(hass, caplog):
    with patch(
        "custom_components.owlet.config_flow.OwletAPI",
        side_effect=OwletConnectionError("nested-secret"),
    ):
        tokens, errors = await authenticate_account(
            hass, "europe", "parent@example.invalid", "password"
        )
    assert errors == {"base": "cannot_connect"}
    assert tokens == {}
    assert "nested-secret" not in caplog.text


async def test_poll_authentication_starts_existing_entry_reauth(hass, cloud):
    from custom_components.owlet.owletapi.exceptions import OwletAuthenticationError

    entry = create_entry(hass, options={"future": "keep"})
    coordinator = await setup_entry(hass, entry)
    before = (entry.entry_id, entry.unique_id, dict(entry.data), dict(entry.options))
    cloud[2].side_effect = OwletAuthenticationError("nested-secret")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert before == (
        entry.entry_id,
        entry.unique_id,
        dict(entry.data),
        dict(entry.options),
    )


@pytest.mark.parametrize("version", [2, 3])
async def test_battery_transition_is_exposed_without_smoothing(hass, cloud, version):
    cloud[1].return_value = {
        "response": [{"device": {"dsn": name}} for name in ("unit-one", "unit-two")]
    }
    cloud[2].return_value = {"response": raw_v3(btt=40) if version == 3 else raw_v2()}
    entry = create_entry(hass)
    coordinator = await setup_entry(hass, entry)
    registry_ids = {key: value.id for key, value in er.async_get(hass).entities.items()}
    for charging, percentage in ((0, 70), (1, 100), (1, 70), (None, 70), (0, 71)):
        raw = raw_v3(chg=charging, bat=percentage, btt=40) if version == 3 else raw_v2()
        if version == 2:
            raw["CHARGE_STATUS"]["value"] = charging
            raw["BATT_LEVEL"]["value"] = percentage
        cloud[2].return_value = {"response": raw}
        await coordinator.async_refresh()
        if version == 3:
            assert entity_state(hass, "sensor", "battery_minutes").state == (
                "40.0" if charging == 0 else "unavailable"
            )
        assert (
            float(entity_state(hass, "sensor", "battery_percentage").state)
            == percentage
        )
        assert entity_state(hass, "sensor", "battery_percentage", "unit-two").state == (
            "80.0" if version == 3 else "85"
        )
        assert entity_state(hass, "sensor", "heart_rate").state == (
            "unavailable" if charging != 0 else "121.0" if version == 3 else "122"
        )
    assert all(
        er.async_get(hass).async_get(key).id == value
        for key, value in registry_ids.items()
    )


async def test_inventory_reload_preserves_absent_returning_disabled_and_renamed_entities(
    hass, cloud
):
    cloud[1].return_value = {
        "response": [{"device": {"dsn": name}} for name in ("unit-one", "unit-two")]
    }
    entry = create_entry(hass)
    await setup_entry(hass, entry)
    registry = er.async_get(hass)
    original = registry.async_get(
        entity_state(hass, "sensor", "heart_rate", "unit-two").entity_id
    )
    custom = registry.async_update_entity(
        original.entity_id,
        new_entity_id="sensor.custom_pulse",
        name="My pulse",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    cloud[1].return_value = {
        "response": [{"device": {"dsn": "unit-one", "sw_version": "new"}}]
    }
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(custom.entity_id).id == original.id
    assert entity_state(hass, "sensor", "heart_rate", "unit-two") is None
    primary = registry.async_get(entity_state(hass, "sensor", "heart_rate").entity_id)
    assert dr.async_get(hass).async_get(primary.device_id).sw_version == "new"
    cloud[1].return_value = {
        "response": [
            {"device": {"dsn": name}} for name in ("unit-one", "unit-two", "unit-three")
        ]
    }
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    restored = registry.async_get(custom.entity_id)
    assert restored.id == original.id and restored.name == "My pulse"
    assert restored.disabled_by is er.RegistryEntryDisabler.USER
    assert restored.device_id == original.device_id
    assert entity_state(hass, "sensor", "heart_rate", "unit-three").state == "121.0"


@pytest.mark.parametrize(
    "mac,expected",
    [
        (None, set()),
        ("bad", set()),
        ("00:00:00:00:00:00", set()),
        ("ff:ff:ff:ff:ff:ff", set()),
        ("02:11:22:33:44:55", {("mac", "02:11:22:33:44:55")}),
    ],
)
async def test_device_metadata_has_no_invented_hardware(hass, cloud, mac, expected):
    cloud[1].return_value = {"response": [{"device": {"dsn": "unit-one", "mac": mac}}]}
    await setup_entry(hass, create_entry(hass))
    entity = er.async_get(hass).async_get(
        entity_state(hass, "sensor", "heart_rate").entity_id
    )
    device = dr.async_get(hass).async_get(entity.device_id)
    assert device.hw_version is None
    assert device.connections == expected


async def test_missing_runtime_diagnostics_are_exact(hass):
    result = await async_get_config_entry_diagnostics(hass, create_entry(hass))
    manifest = json.loads(Path("custom_components/owlet/manifest.json").read_text())
    assert result == {
        "entry_version": 2,
        "integration_version": manifest["version"],
        "homeassistant_version": HA_VERSION,
        "devices": [],
    }


def translation_leaf_keys(value, prefix=""):
    return {
        key
        for name, item in value.items()
        for key in (
            translation_leaf_keys(item, f"{prefix}{name}.")
            if isinstance(item, dict)
            else {f"{prefix}{name}"}
        )
    }


@pytest.mark.parametrize("locale", ["en", "fr", "nl"])
def test_maintained_locale_key_parity(locale):
    source = json.loads(Path("custom_components/owlet/strings.json").read_text())
    translated = json.loads(
        Path(f"custom_components/owlet/translations/{locale}.json").read_text()
    )
    assert translation_leaf_keys(source) == translation_leaf_keys(translated)
    assert "\ufffd" not in json.dumps(translated, ensure_ascii=False)


@pytest.mark.parametrize("path", ["setup", "poll", "switch", "flow"])
async def test_unexpected_nested_errors_never_escape_to_ha_logs(
    hass, cloud, caplog, path
):
    from homeassistant.exceptions import HomeAssistantError

    secret = "synthetic-nested-private-payload"
    error = RuntimeError({"token": {"value": secret}})
    error.add_note(secret)
    error.__cause__ = ValueError(secret)
    entry = create_entry(hass)
    if path == "setup":
        cloud[0].side_effect = error
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert "Owlet" in caplog.text
    elif path == "poll":
        coordinator = await setup_entry(hass, entry)
        cloud[2].side_effect = error
        await coordinator.async_refresh()
        assert not coordinator.last_update_success
    elif path == "switch":
        coordinator = await setup_entry(hass, entry)
        with patch.object(coordinator.sock, "control_base_station", side_effect=error):
            with pytest.raises(HomeAssistantError) as caught:
                await command(hass, False)
        assert secret not in str(caught.value)
    else:
        cloud[0].side_effect = error
        _, errors = await authenticate_account(
            hass, "europe", "parent@example.invalid", "password"
        )
        assert errors == {"base": "unknown"}
    assert secret not in caplog.text


async def test_false_command_result_is_not_acceptance(hass, cloud):
    from homeassistant.exceptions import HomeAssistantError

    coordinator = await setup_entry(hass, create_entry(hass))
    with patch.object(coordinator.sock, "control_base_station", return_value=False):
        with pytest.raises(HomeAssistantError):
            await command(hass, False)
    assert entity_state(hass, "switch", "base_station_on").state == "on"
    assert (
        entity_state(hass, "switch", "base_station_on").attributes["command_status"]
        is None
    )


async def test_populated_diagnostics_are_an_exact_allowlist(hass, cloud):
    raw = raw_v3()
    raw["FUTURE_SECRET"] = {"value": {"identity": "private"}}
    cloud[2].return_value = {"response": raw}
    entry = create_entry(
        hass, options={"scan_interval": 5, "unknown_secret": "private"}
    )
    await setup_entry(hass, entry)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result == {
        "entry_version": 2,
        "integration_version": json.loads(
            Path("custom_components/owlet/manifest.json").read_text()
        )["version"],
        "homeassistant_version": HA_VERSION,
        "devices": [
            {
                "generation": 3,
                "poll_success": True,
                "poll_seconds": 5,
                "stale_threshold_seconds": 0,
                "freshness_options_compatible": True,
                "readings_expected": True,
                "capabilities": [
                    "base_station_on",
                    "battery_percentage",
                    "charging",
                    "heart_rate",
                    "oxygen_saturation",
                ],
                "freshness": {
                    "base_station_on": "fresh",
                    "battery_percentage": "fresh",
                    "charging": "fresh",
                    "heart_rate": "fresh",
                    "oxygen_saturation": "fresh",
                },
                "body_position_enabled": False,
            }
        ],
    }


@pytest.mark.parametrize("reauth", [False, True])
@pytest.mark.parametrize(
    "error_name,initial_errors",
    [
        ("OwletEmailError", {"username": "invalid_email"}),
        ("OwletPasswordError", {"password": "invalid_password"}),
        ("OwletCredentialsError", {"base": "invalid_credentials"}),
        ("OwletRateLimitError", {"base": "rate_limited"}),
        ("OwletConnectionError", {"base": "cannot_connect"}),
        ("TimeoutError", {"base": "cannot_connect"}),
        ("OwletDevicesError", {"base": "no_devices"}),
    ],
)
async def test_initial_and_reauth_forms_report_actionable_errors(
    hass, error_name, initial_errors, reauth
):
    from custom_components.owlet.owletapi import exceptions

    error_type = (
        TimeoutError
        if error_name == "TimeoutError"
        else getattr(exceptions, error_name)
    )
    if reauth:
        entry = create_entry(hass, options={"future": "keep"})
        before = (
            entry.entry_id,
            entry.unique_id,
            dict(entry.data),
            dict(entry.options),
        )
        flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=dict(entry.data),
        )
        user_input = {"password": "synthetic"}
    else:
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        user_input = {
            "username": "new@example.invalid",
            "password": "synthetic",
            "region": "world",
        }
    with patch.object(
        OwletAPI, "authenticate", side_effect=error_type("nested-secret")
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input=user_input
        )
    expected = (
        {"base": "invalid_credentials"}
        if reauth and "username" in initial_errors
        else initial_errors
    )
    assert result["type"] == "form"
    assert result["errors"] == expected
    if reauth:
        assert before == (
            entry.entry_id,
            entry.unique_id,
            dict(entry.data),
            dict(entry.options),
        )
    else:
        assert hass.config_entries.async_entries(DOMAIN) == []
