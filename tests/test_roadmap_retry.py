"""Account-wide request budgets and authentication failure recovery."""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import patch

import aiohttp
import pytest

from custom_components.owlet.owletapi.api import OwletAPI, parse_retry_after
from custom_components.owlet.owletapi.const import REGION_INFO
from custom_components.owlet.owletapi.exceptions import (
    OwletConnectionError,
    OwletRateLimitError,
)

from .cloud_fixtures import BASE, FakeSession
from .test_api_contract import authed


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_two_socks_share_transient_cooldown(status):
    session = FakeSession()
    session.get(
        BASE + "/dsns/one/properties.json", status=status, headers={"Retry-After": "77"}
    )
    session.get(BASE + "/dsns/two/properties.json", payload=[])
    api = authed(session)
    with patch("custom_components.owlet.owletapi.api.time.monotonic", return_value=100):
        with pytest.raises(OwletConnectionError):
            await api.get_properties("one")
        with pytest.raises(OwletRateLimitError) as caught:
            await api.get_properties("two")
        assert caught.value.retry_after == 77
    assert len(session.requests) == 1
    assert api.tokens["api_token"] == "valid"
    with patch("custom_components.owlet.owletapi.api.time.monotonic", return_value=178):
        assert await api._request("GET", "/dsns/two/properties.json") == []


@pytest.mark.parametrize(
    "failure", [aiohttp.ClientConnectionError("secret"), TimeoutError("secret")]
)
async def test_network_failures_share_bounded_cooldown(failure):
    session = FakeSession()
    session.get(BASE + "/devices.json", exception=failure)
    api = authed(session)
    with patch("custom_components.owlet.owletapi.api.time.monotonic", return_value=100):
        with pytest.raises(OwletConnectionError):
            await api._request("GET", "/devices.json")
        with pytest.raises(OwletRateLimitError) as caught:
            await api._request("GET", "/devices.json")
        assert 5 <= caught.value.retry_after <= 300
    assert len(session.requests[("GET", BASE + "/devices.json")]) == 1
    assert api.tokens["refresh"] == "refresh"


async def test_waiting_refresh_callers_do_not_retry_failed_exchange():
    session = FakeSession()
    key = REGION_INFO["europe"]["apiKey"]
    url = f"https://securetoken.googleapis.com/v1/token?key={key}"
    session.post(url, status=429, headers={"Retry-After": "90"}, repeat=True)
    api = OwletAPI(
        "europe", token="old", expiry=0, refresh="old-refresh", session=session
    )
    results = await asyncio.gather(
        api.authenticate(),
        api.authenticate(),
        api.firebase_identity(),
        return_exceptions=True,
    )
    assert all(isinstance(result, OwletRateLimitError) for result in results)
    assert len(session.requests[("POST", url)]) == 1
    assert api.tokens == {"api_token": "old", "expiry": 0, "refresh": "old-refresh"}


@pytest.mark.parametrize(
    "header",
    [
        "Wed, 21 Oct 2015 07:28:00",
        "999999999999999999999999",
        "Wed, 99 Oct 2015 07:28:00 GMT",
    ],
)
def test_retry_after_invalid_dates_never_raise(header):
    result = parse_retry_after(header)
    assert result is None or 5 <= result <= 3600


def test_retry_after_http_date_uses_utc():
    now = datetime.now(UTC)
    with patch("custom_components.owlet.owletapi.api.datetime") as clock:
        clock.now.return_value = now
        assert parse_retry_after(
            format_datetime(now + timedelta(seconds=85), usegmt=True)
        ) == pytest.approx(85, abs=1)


async def test_auth_retry_is_blocked_when_other_request_sets_account_cooldown():
    session = FakeSession()
    session.get(BASE + "/devices.json", status=401)
    session.get(
        BASE + "/dsns/other/properties.json", status=429, headers={"Retry-After": "45"}
    )
    api = authed(session)

    async def refresh():
        with pytest.raises(OwletRateLimitError):
            await api._request("GET", "/dsns/other/properties.json")
        api._update_tokens("new", time.time() + 3600, "refresh")

    with patch.object(api, "refresh_authentication", side_effect=refresh):
        with pytest.raises(OwletRateLimitError):
            await api._request("GET", "/devices.json")
    assert len(session.requests[("GET", BASE + "/devices.json")]) == 1


async def test_discovery_failure_joins_other_capability_requests():
    session = FakeSession()
    api = authed(session)
    session.get(
        BASE + "/devices.json",
        payload=[{"device": {"dsn": name}} for name in ("one", "two")],
    )
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def properties(serial, activate):
        if serial == "one":
            await started.wait()
            raise OwletConnectionError("failed")
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with patch.object(api, "_fetch_properties", side_effect=properties):
        with pytest.raises(OwletConnectionError):
            await api.get_devices()
    assert cancelled.is_set()


async def test_duplicate_discovery_is_bounded_and_activation_is_not_per_poll():
    session = FakeSession()
    api = authed(session)
    session.get(
        BASE + "/devices.json",
        payload=[{"device": {"dsn": name}} for name in ("one", "two", "one")],
    )
    for name in ("one", "two"):
        session.get(
            BASE + f"/dsns/{name}/properties.json",
            payload=[{"property": {"name": "REAL_TIME_VITALS", "value": "{}"}}],
            repeat=True,
        )
        session.post(
            BASE + f"/dsns/{name}/properties/APP_ACTIVE/datapoints.json",
            payload={},
            repeat=True,
        )
    discovery = await api.get_devices()
    assert [device["device"]["dsn"] for device in discovery["response"]] == [
        "one",
        "two",
    ]
    assert sum(map(len, session.requests.values())) == 3
    with patch("custom_components.owlet.owletapi.api.time.monotonic", return_value=100):
        for _ in range(3):
            await asyncio.gather(api.get_properties("one"), api.get_properties("two"))
            await asyncio.gather(*api._activation_tasks.values())
    assert (
        sum(
            len(calls)
            for (method, _), calls in session.requests.items()
            if method == "POST"
        )
        == 2
    )
    assert sum(map(len, session.requests.values())) == 11
    assert api.tokens["api_token"] == "valid"
    await api.close()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id_token": "identity"},
        {"refresh_token": "new"},
        {"refresh_token": 17, "id_token": "identity"},
    ],
)
async def test_malformed_refresh_never_overwrites_complete_credentials(payload):
    session = FakeSession()
    key = REGION_INFO["europe"]["apiKey"]
    session.post(
        f"https://securetoken.googleapis.com/v1/token?key={key}", payload=payload
    )
    api = OwletAPI(
        "europe", token="old", expiry=0, refresh="old-refresh", session=session
    )
    with pytest.raises(OwletConnectionError):
        await api.authenticate()
    assert api.tokens == {"api_token": "old", "expiry": 0, "refresh": "old-refresh"}


async def test_transient_backoff_is_bounded_and_resets_after_success():
    session = FakeSession()
    url = BASE + "/devices.json"
    api = authed(session)
    now = 100
    delays = []
    for _ in range(9):
        session.get(url, status=503)
        with patch(
            "custom_components.owlet.owletapi.api.time.monotonic", return_value=now
        ):
            with pytest.raises(OwletConnectionError):
                await api._request("GET", "/devices.json")
            with pytest.raises(OwletRateLimitError) as caught:
                await api._request("GET", "/devices.json")
        delays.append(caught.value.retry_after)
        now += caught.value.retry_after + 1
    assert delays == [5, 10, 20, 40, 80, 160, 300, 300, 300]
    session.get(url, payload=[])
    with patch("custom_components.owlet.owletapi.api.time.monotonic", return_value=now):
        assert await api._request("GET", "/devices.json") == []
    session.get(url, status=503)
    with patch(
        "custom_components.owlet.owletapi.api.time.monotonic", return_value=now + 1
    ):
        with pytest.raises(OwletConnectionError):
            await api._request("GET", "/devices.json")
        with pytest.raises(OwletRateLimitError) as caught:
            await api._request("GET", "/devices.json")
    assert caught.value.retry_after == 5
