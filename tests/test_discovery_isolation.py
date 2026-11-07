"""Discovery bounds and independent device permission recovery."""

import asyncio
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.owlet.const import DOMAIN
from custom_components.owlet.owletapi.exceptions import OwletDevicesError

from .cloud_fixtures import BASE, FakeSession
from .test_api_contract import authed
from .test_superintegration import create_entry, raw_v3


def add_inventory(session, names):
    session.get(
        BASE + "/devices.json",
        payload=[{"device": {"dsn": name}} for name in names],
    )


def add_properties(session, name, status=200, repeat=False):
    session.get(
        BASE + f"/dsns/{name}/properties.json",
        status=status,
        payload=[
            {"property": {"name": key, **value}} for key, value in raw_v3().items()
        ],
        repeat=repeat,
    )


async def test_denied_devices_do_not_hide_healthy_siblings_and_can_return():
    session = FakeSession()
    api = authed(session)
    add_inventory(session, ["denied", "healthy"])
    add_properties(session, "denied", status=403)
    add_properties(session, "healthy")
    result = await api.get_devices()
    assert [d["device"]["dsn"] for d in result["response"]] == ["healthy"]
    add_inventory(session, ["denied", "healthy"])
    add_properties(session, "denied")
    add_properties(session, "healthy")
    result = await api.get_devices()
    assert [d["device"]["dsn"] for d in result["response"]] == ["denied", "healthy"]
    assert api.tokens["api_token"] == "valid"


async def test_all_denied_devices_produce_no_supported_device_error():
    session = FakeSession()
    api = authed(session)
    add_inventory(session, ["denied"])
    add_properties(session, "denied", status=403)
    with pytest.raises(OwletDevicesError):
        await api.get_devices()


@pytest.mark.parametrize("cancel", [False, True])
async def test_large_inventory_has_four_probe_ceiling_and_joins_workers(cancel):
    session = FakeSession()
    api = authed(session)
    names = [f"sock-{index}" for index in range(64)]
    add_inventory(session, names)
    saturated = asyncio.Event()
    release = asyncio.Event()
    active = 0
    peak = 0
    completed = []

    async def properties(serial, activate):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 4:
            saturated.set()
        try:
            await release.wait()
            completed.append(serial)
            return raw_v3()
        finally:
            active -= 1

    with patch.object(api, "_fetch_properties", side_effect=properties):
        task = asyncio.create_task(api.get_devices())
        try:
            await saturated.wait()
            assert active == 4
            if cancel:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert completed == []
            else:
                release.set()
                result = await task
                assert [d["device"]["dsn"] for d in result["response"]] == names
                assert sorted(completed) == sorted(names)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert peak == 4
    assert active == 0


async def test_entry_loads_healthy_device_and_reload_restores_denied_sibling(hass):
    session = FakeSession()
    entry = create_entry(hass)
    add_inventory(session, ["denied", "healthy"])
    add_properties(session, "denied", status=403)
    add_properties(session, "healthy", repeat=True)
    for name in ("denied", "healthy"):
        session.post(
            BASE + f"/dsns/{name}/properties/APP_ACTIVE/datapoints.json",
            payload={},
            repeat=True,
        )
    with patch("custom_components.owlet.async_get_clientsession", return_value=session):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert set(hass.data[DOMAIN][entry.entry_id]) == {"healthy"}
        registry = er.async_get(hass)
        original = registry.async_get_entity_id("sensor", DOMAIN, "healthy-heart_rate")
        assert original is not None
        assert hass.states.get(original).state == "121.0"
        add_inventory(session, ["denied", "healthy"])
        add_properties(session, "denied", repeat=True)
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert set(hass.data[DOMAIN][entry.entry_id]) == {"denied", "healthy"}
        assert (
            registry.async_get_entity_id("sensor", DOMAIN, "healthy-heart_rate")
            == original
        )
        assert hass.states.get(original).state == "121.0"
        assert await hass.config_entries.async_unload(entry.entry_id)
