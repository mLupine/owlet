"""Lifecycle regressions driven by HA entry and service operations."""

import asyncio
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.const import Platform
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from custom_components.owlet.const import DOMAIN

from .test_review_regressions import command
from .test_superintegration import cloud as cloud
from .test_superintegration import create_entry, raw_v3, setup_entry


@pytest.mark.parametrize("age", [0, 7200])
async def test_unload_during_poll_cannot_recreate_expiry_or_repairs(hass, cloud, age):
    entry = create_entry(hass, options={"stale_threshold": 5})
    coordinator = await setup_entry(hass, entry)
    started = asyncio.Event()
    release = asyncio.Event()

    async def properties(serial):
        started.set()
        await release.wait()
        return {"response": raw_v3(dt_util.utcnow() - timedelta(seconds=age))}

    cloud[2].side_effect = properties
    poll = asyncio.create_task(coordinator.async_refresh())
    await started.wait()
    assert await hass.config_entries.async_unload(entry.entry_id)
    release.set()
    await asyncio.gather(poll, return_exceptions=True)
    assert coordinator._cancel_expiry is None
    assert (DOMAIN, coordinator.issue_id) not in ir.async_get(hass).issues
    before = cloud[2].await_count
    await coordinator.async_refresh()
    assert cloud[2].await_count == before


async def test_cancelled_service_does_not_schedule_command_confirmation(hass, cloud):
    entry = create_entry(hass)
    coordinator = await setup_entry(hass, entry)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocked(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with patch.object(coordinator.sock, "control_base_station", side_effect=blocked):
        service = asyncio.create_task(command(hass, False))
        await started.wait()
        service.cancel()
        result = await asyncio.gather(service, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)
        assert cancelled.is_set()
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.parametrize("partial", [False, True])
async def test_platform_forwarding_failure_cleans_runtime(hass, cloud, cancel, partial):
    entry = create_entry(hass, options={"stale_threshold": 5})
    captured = []
    original_forward = hass.config_entries.async_forward_entry_setups

    async def forward(*args):
        captured.extend(hass.data[DOMAIN][entry.entry_id].values())
        if partial:
            await original_forward(entry, [Platform.SENSOR])
        if cancel:
            raise asyncio.CancelledError
        raise RuntimeError("synthetic platform failure")

    with patch.object(
        hass.config_entries, "async_forward_entry_setups", side_effect=forward
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
    assert all(coordinator._cancel_expiry is None for coordinator in captured)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
