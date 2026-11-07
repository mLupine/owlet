"""Test owlet coordinator."""

from __future__ import annotations

import json
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from custom_components.owlet.owletapi.exceptions import (
    OwletAuthenticationError,
    OwletConnectionError,
)

from . import async_init_integration
from .fixture_data import load_fixture

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def test_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test coordinator setup authentication error."""
    entry = await async_init_integration(hass, skip_setup=True)

    with (
        patch(
            "custom_components.owlet.Sock.update_properties",
            side_effect=OwletAuthenticationError(),
        ),
        patch("custom_components.owlet.OwletAPI.authenticate", return_value=None),
        patch(
            "custom_components.owlet.OwletAPI.get_devices",
            return_value=json.loads(load_fixture("get_devices.json", "owlet")),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test coordinator setup connection error error."""
    entry = await async_init_integration(hass, skip_setup=True)

    with (
        patch(
            "custom_components.owlet.Sock.update_properties",
            side_effect=OwletConnectionError(),
        ),
        patch("custom_components.owlet.OwletAPI.authenticate", return_value=None),
        patch(
            "custom_components.owlet.OwletAPI.get_devices",
            return_value=json.loads(load_fixture("get_devices.json", "owlet")),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_error(hass: HomeAssistant) -> None:
    """Test coordinator setup generic error."""
    entry = await async_init_integration(hass, skip_setup=True)

    with (
        patch(
            "custom_components.owlet.Sock.update_properties",
            side_effect=Exception(),
        ),
        patch("custom_components.owlet.OwletAPI.authenticate", return_value=None),
        patch(
            "custom_components.owlet.OwletAPI.get_devices",
            return_value=json.loads(load_fixture("get_devices.json", "owlet")),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.SETUP_RETRY
