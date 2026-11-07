"""HTTP contracts for the bundled client and tolerant property decoding."""

import asyncio
import json
import time
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import web
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.owlet.owletapi.api import OwletAPI, parse_retry_after
from custom_components.owlet.owletapi.const import REGION_INFO
from custom_components.owlet.owletapi.exceptions import (
    OwletAuthenticationError,
    OwletConnectionError,
    OwletCredentialsError,
    OwletEmailError,
    OwletPasswordError,
    OwletRateLimitError,
    OwletReadOnlyError,
)
from custom_components.owlet.owletapi.sock import (
    Sock,
    decode_bool,
    decode_number,
    parse_timestamp,
)

from .cloud_fixtures import BASE, DSN, FakeSession, load, mock_login, mock_refresh
from .test_superintegration import create_entry, entity_state, raw_v3, setup_entry


@pytest.fixture
def session():
    return FakeSession()


def authed(session):
    return OwletAPI(
        "europe",
        token="valid",
        expiry=time.time() + 3600,
        refresh="refresh",
        session=session,
        activation_interval=30,
    )


async def test_complete_password_refresh_chain_and_identity_cache(session):
    mock_login(session)
    api = OwletAPI("europe", "synthetic@example.invalid", "password", session=session)
    tokens = await api.authenticate()
    assert tokens["api_token"] == "new_token" and tokens["refresh"] == "new_refresh"
    assert tokens["expiry"] > time.time()
    before = sum(map(len, session.requests.values()))
    assert await api.firebase_identity() == ("id_token", "user")
    assert await api.firebase_identity() == ("id_token", "user")
    assert sum(map(len, session.requests.values())) == before


@pytest.mark.parametrize(
    "message,error",
    [
        ("INVALID_PASSWORD", OwletPasswordError),
        ("EMAIL_NOT_FOUND", OwletEmailError),
        ("INVALID_LOGIN_CREDENTIALS", OwletCredentialsError),
        ("TOO_MANY_ATTEMPTS_TRY_LATER", OwletRateLimitError),
    ],
)
async def test_credential_classification(session, message, error):
    key = REGION_INFO["europe"]["apiKey"]
    session.post(
        f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={key}",
        status=400,
        payload={"error": {"message": message}},
    )
    api = OwletAPI("europe", "synthetic@example.invalid", "pass", session=session)
    with pytest.raises(error):
        await api.authenticate()


async def test_concurrent_expiry_refresh_is_shared(session):
    mock_refresh(session)
    api = OwletAPI("europe", token="old", expiry=0, refresh="refresh", session=session)
    await asyncio.gather(api.authenticate(), api.authenticate(), api.authenticate())
    assert api.tokens["api_token"] == "new_token"
    key = REGION_INFO["europe"]["apiKey"]
    assert (
        len(
            session.requests[
                ("POST", f"https://securetoken.googleapis.com/v1/token?key={key}")
            ]
        )
        == 1
    )


async def test_concurrent_401_responses_do_not_invalidate_new_token(session):
    mock_refresh(session)
    session.get(BASE + "/devices.json", status=401)
    session.get(BASE + "/devices.json", status=401)
    session.get(BASE + "/devices.json", payload=[])
    session.get(BASE + "/devices.json", payload=[])
    api = authed(session)
    assert await asyncio.gather(
        api._request("GET", "/devices.json"), api._request("GET", "/devices.json")
    ) == [[], []]
    assert len(session.requests[("POST", REGION_INFO["europe"]["url_signin"])]) == 1
    assert api.tokens["api_token"] == "new_token"


async def test_persistent_401_is_auth_failure_after_one_retry(session):
    mock_refresh(session)
    session.get(BASE + "/devices.json", status=401, repeat=True)
    api = authed(session)
    with pytest.raises(OwletAuthenticationError):
        await api._request("GET", "/devices.json")
    assert len(session.requests[("GET", BASE + "/devices.json")]) == 2


@pytest.mark.parametrize(
    "status,error",
    [
        (429, OwletRateLimitError),
        (500, OwletConnectionError),
        (503, OwletConnectionError),
    ],
)
async def test_transient_status_does_not_refresh_credentials(session, status, error):
    session.get(BASE + "/devices.json", status=status, headers={"Retry-After": "77"})
    api = authed(session)
    with pytest.raises(error):
        await api._request("GET", "/devices.json")
    assert len(session.requests) == 1
    assert api.tokens["api_token"] == "valid"
    if status == 429:
        with pytest.raises(OwletRateLimitError):
            await api._request("GET", "/devices.json")
        assert len(session.requests[("GET", BASE + "/devices.json")]) == 1


@pytest.mark.parametrize(
    "value,expected",
    [
        ("10", 10),
        ("0", 5),
        ("999999", 3600),
        ("nan", None),
        ("inf", None),
        ("bad", None),
        (None, None),
    ],
)
def test_retry_after_bounds(value, expected):
    assert parse_retry_after(value) == expected


async def test_properties_publish_before_activation_and_activation_failure_is_isolated(
    session,
):
    session.get(
        BASE + f"/dsns/{DSN}/properties.json", payload=load("properties_v3.json")
    )
    api = authed(session)
    gate = asyncio.Event()

    async def activation(*args, **kwargs):
        await gate.wait()
        raise OwletAuthenticationError("private payload")

    with patch.object(api, "_maybe_activate", side_effect=activation) as activate:
        response = await api.get_properties(DSN)
        assert "REAL_TIME_VITALS" in response["response"]
        gate.set()
        await asyncio.gather(*api._activation_tasks.values())
        assert activate.await_count == 1
    await api.close()


async def test_close_cancels_activation_and_keeps_shared_session_open(session):
    session.get(
        BASE + f"/dsns/{DSN}/properties.json", payload=load("properties_v3.json")
    )
    api = authed(session)
    gate = asyncio.Event()
    with (
        patch.object(
            api, "_maybe_activate", side_effect=lambda *args, **kwargs: gate.wait()
        ),
        patch.object(session, "close", new_callable=AsyncMock) as close,
    ):
        await api.get_properties(DSN)
        tasks = list(api._activation_tasks.values())
        await api.close()
        assert all(task.done() for task in tasks)
        close.assert_not_awaited()


async def test_command_protocol_is_preserved_and_other_writes_refused(session):
    api = authed(session)
    url = BASE + f"/dsns/{DSN}/properties/BASE_STATION_ON_CMD/datapoints.json"
    session.post(url, payload={"datapoint": {"value": "accepted"}})
    sock = Sock(api, {"dsn": DSN})
    assert await sock.control_base_station(False)
    value = session.requests[("POST", url)][0].kwargs["json"]["datapoint"]["value"]
    assert json.loads(value)["val"] == "false"
    with pytest.raises(OwletReadOnlyError):
        await api.post_command(DSN, "UNSUPPORTED_WRITE", {})


@pytest.mark.parametrize(
    "value", [True, False, None, {}, [], "nan", "inf", "-inf", "bad"]
)
def test_invalid_numeric_values_are_unknown(value):
    assert decode_number(value) is None


@pytest.mark.parametrize("value", [2, 0.5, [], {}, "bad", None])
def test_invalid_boolean_values_are_unknown(value):
    assert decode_bool(value) is None


@pytest.mark.parametrize(
    "value",
    [
        None,
        "bad",
        "2026-01-01T00:00:00",
        (dt_util.utcnow() + timedelta(days=1)).isoformat(),
    ],
)
def test_invalid_timestamps_are_unknown(value):
    assert parse_timestamp(value) is None


async def test_malformed_fields_do_not_hide_valid_neighbors(session):
    api = authed(session)
    sock = Sock(api, {"dsn": DSN})
    response = raw_v3(hr=True, ox="nan", bat=80, st=72, ss=999, chg=2)
    response["SOCK_OFF"] = {"value": "not-a-boolean"}
    response["oem_sock_version"] = {"value": "broken json"}
    with patch.object(api, "get_properties", return_value={"response": response}):
        await sock.update_properties()
    assert sock.properties["heart_rate"] is None
    assert sock.properties["oxygen_saturation"] is None
    assert sock.properties["battery_percentage"] == 80
    assert sock.properties["skin_temperature"] == 72
    assert sock.properties["sleep_state"] == 999
    assert sock.properties["sock_off"] is None
    assert sock.properties["charging"] is True
    assert sock.revision is None
    response["REAL_TIME_VITALS"]["value"] = "{broken"
    response["LOW_BATT_ALRT"] = {"value": 1}
    with patch.object(api, "get_properties", return_value={"response": response}):
        await sock.update_properties()
    assert sock.properties["low_battery_alert"] is True
    assert "heart_rate" not in sock.properties


@pytest.mark.parametrize("region", ["europe", "world"])
async def test_actual_aiohttp_to_ha_platforms_and_command_readback(
    hass, aiohttp_server, socket_enabled, region, freezer
):
    state = {"base": 1, "activation": 0, "requested": None, "reads": 0}

    async def handler(request):
        if request.path == "/devices.json":
            return web.json_response([{"device": {"dsn": "unit-one"}}])
        if request.path.endswith("/properties.json"):
            if state["requested"] is not None:
                state["reads"] += 1
                if state["reads"] == 3:
                    state["base"] = state["requested"]
            raw = raw_v3(bso=state["base"])
            return web.json_response(
                [{"property": {"name": key, **value}} for key, value in raw.items()]
            )
        data = await request.json()
        if "BASE_STATION_ON_CMD" in request.path:
            state["requested"] = int(
                json.loads(data["datapoint"]["value"])["val"] == "true"
            )
        else:
            state["activation"] += 1
        return web.json_response({"datapoint": {"value": "accepted"}}, status=201)

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    server = await aiohttp_server(app)
    with patch.dict(
        REGION_INFO[region], {"url_base": str(server.make_url("")).rstrip("/")}
    ):
        entry = create_entry(
            hass, region=region, unique_id=f"{region}_parent@example.invalid"
        )
        await setup_entry(hass, entry)
        assert entity_state(hass, "sensor", "heart_rate").state == "121.0"
        switch = entity_state(hass, "switch", "base_station_on")
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": switch.entity_id}, blocking=True
        )
        await hass.async_block_till_done()
        assert entity_state(hass, "switch", "base_station_on").state == "on"
        assert (
            entity_state(hass, "switch", "base_station_on").attributes["command_status"]
            == "pending"
        )
        for _ in range(2):
            freezer.tick(2)
            async_fire_time_changed(hass, dt_util.utcnow())
            await hass.async_block_till_done()
        assert state["reads"] == 3
        assert entity_state(hass, "switch", "base_station_on").state == "off"
        assert (
            entity_state(hass, "switch", "base_station_on").attributes["command_status"]
            == "confirmed"
        )
        assert state["activation"] >= 1
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_optional_identity_does_not_exchange_or_block_valid_primary_access(
    session,
):
    api = authed(session)
    started = asyncio.Event()
    release = asyncio.Event()
    original_request = session.request
    mock_refresh(session)
    key = REGION_INFO["europe"]["apiKey"]
    url = f"https://securetoken.googleapis.com/v1/token?key={key}"
    session.get(BASE + "/devices.json", payload=[])

    class BlockedIdentityResponse:
        async def __aenter__(self):
            started.set()
            await release.wait()
            self.response = original_request("POST", url)
            return await self.response.__aenter__()

        async def __aexit__(self, *args):
            return await self.response.__aexit__(*args)

    def request(method, target, **kwargs):
        if target == url:
            return BlockedIdentityResponse()
        return original_request(method, target, **kwargs)

    with patch.object(session, "request", side_effect=request):
        task = asyncio.create_task(api.firebase_identity())
        try:
            await started.wait()
            assert await asyncio.wait_for(api._request("GET", "/devices.json"), 1) == []
            assert not task.done()
            release.set()
            assert await task == ("id_token", "user")
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
    assert not session.requests[("GET", REGION_INFO["europe"]["url_mini"])]
    assert not session.requests[("POST", REGION_INFO["europe"]["url_signin"])]
    assert api.tokens["api_token"] == "valid"
    assert api.tokens["refresh"] == "new_refresh"


@pytest.mark.parametrize(
    "version,marker", [(2, "CHARGE_STATUS"), (3, "REAL_TIME_VITALS")]
)
async def test_discovered_generation_survives_empty_first_poll(
    hass, session, version, marker
):
    from custom_components.owlet.coordinator import OwletCoordinator

    api = authed(session)
    session.get(BASE + "/devices.json", payload=[{"device": {"dsn": DSN}}])
    with patch.object(api, "_fetch_properties", return_value={marker: {"value": 0}}):
        discovery = await api.get_devices()
    device = discovery["response"][0]
    assert device["verified_version"] == version
    sock = Sock(api, device["device"], device["verified_version"])
    coordinator = OwletCoordinator(
        hass, sock, create_entry(hass, options={"stale_threshold": 5})
    )
    try:
        with patch.object(api, "get_properties", return_value={"response": {}}):
            await coordinator.async_refresh()
            assert coordinator.is_stale
            assert coordinator.affected_vitals == ["heart_rate", "oxygen_saturation"]
            await coordinator.async_refresh()
            assert coordinator.is_stale
    finally:
        coordinator.shutdown()


async def test_device_forbidden_does_not_rotate_account_credentials(session):
    session.get(BASE + "/dsns/unit-one/properties.json", status=403)
    session.get(BASE + "/devices.json", payload=[])
    api = authed(session)
    with pytest.raises(OwletConnectionError):
        await api._request("GET", "/dsns/unit-one/properties.json")
    assert await api._request("GET", "/devices.json") == []
    assert api.tokens["api_token"] == "valid"
    assert all(method == "GET" for method, url in session.requests)


async def test_unexpected_activation_failure_is_sanitized(session, caplog):
    api = authed(session)
    with patch.object(api, "_maybe_activate", side_effect=KeyError("private payload")):
        await api._activate_quietly(DSN)
    assert "Owlet activation failed" in caplog.text
    assert "private payload" not in caplog.text
