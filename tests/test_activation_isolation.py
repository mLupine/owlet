"""Optional activation failures must not hide healthy sibling readings."""

from unittest.mock import patch

import aiohttp
import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.owlet.const import DOMAIN
from custom_components.owlet.owletapi.exceptions import (
    OwletConnectionError,
    OwletRateLimitError,
)

from .cloud_fixtures import BASE, FakeSession
from .test_api_contract import authed
from .test_discovery_isolation import add_inventory, add_properties
from .test_superintegration import create_entry


@pytest.mark.parametrize("failure", [400, 404, 503, "network", "timeout"])
async def test_failed_background_activation_keeps_sibling_available(hass, failure):
    session = FakeSession()
    entry = create_entry(hass)
    add_inventory(session, ["one", "two"])
    for name in ("one", "two"):
        add_properties(session, name, repeat=True)
    activation = BASE + "/dsns/one/properties/APP_ACTIVE/datapoints.json"
    if isinstance(failure, int):
        session.post(activation, status=failure, repeat=True)
    else:
        error = (
            aiohttp.ClientConnectionError() if failure == "network" else TimeoutError()
        )
        session.post(activation, exception=error, repeat=True)
    session.post(
        BASE + "/dsns/two/properties/APP_ACTIVE/datapoints.json",
        payload={},
        repeat=True,
    )
    with patch("custom_components.owlet.async_get_clientsession", return_value=session):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinators = hass.data[DOMAIN][entry.entry_id]
        await coordinators["two"].async_refresh()
        await coordinators["one"].async_refresh()
        await hass.async_block_till_done()
        for name in ("one", "two"):
            assert coordinators[name].last_update_success
            entity = er.async_get(hass).async_get_entity_id(
                "sensor", DOMAIN, f"{name}-heart_rate"
            )
            assert hass.states.get(entity).state == "121.0"
        assert len(session.requests[("POST", activation)]) == 1
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("status", [400, 403, 404])
async def test_rejected_device_read_does_not_pause_sibling(status):
    session = FakeSession()
    api = authed(session)
    session.get(BASE + "/dsns/one/properties.json", status=status)
    add_properties(session, "two")
    with pytest.raises(OwletConnectionError):
        await api.get_properties("one")
    result = await api._fetch_properties("two", activate=False)
    assert "REAL_TIME_VITALS" in result
    assert len(session.requests[("GET", BASE + "/dsns/two/properties.json")]) == 1


async def test_activation_rate_limit_still_honors_account_retry_after():
    session = FakeSession()
    api = authed(session)
    session.post(
        BASE + "/dsns/one/properties/APP_ACTIVE/datapoints.json",
        status=429,
        headers={"Retry-After": "90"},
    )
    with pytest.raises(OwletRateLimitError):
        await api.activate("one")
    with pytest.raises(OwletRateLimitError) as caught:
        await api.get_properties("two")
    assert 89 <= caught.value.retry_after <= 90
    assert ("GET", BASE + "/dsns/two/properties.json") not in session.requests
    await api.close()
