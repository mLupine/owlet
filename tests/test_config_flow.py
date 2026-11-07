"""Test Owlet config flow."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.owlet.const import DOMAIN, POLLING_INTERVAL
from custom_components.owlet.owletapi.exceptions import (
    OwletCredentialsError,
    OwletDevicesError,
    OwletEmailError,
    OwletPasswordError,
)

from . import async_init_integration
from .const import AUTH_RETURN, CONF_INPUT, CONF_INPUT_WORLD
from .fixture_data import load_fixture


@pytest.fixture(autouse=True)
def flow_cloud_boundary():
    with (
        patch(
            "custom_components.owlet.config_flow.OwletAPI.get_devices",
            return_value=json.loads(load_fixture("get_devices.json")),
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_setup", return_value=True
        ),
    ):
        yield


async def test_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "custom_components.owlet.config_flow.OwletAPI.authenticate",
            return_value=AUTH_RETURN,
        ),
        patch("custom_components.owlet.config_flow.OwletAPI.get_devices"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "sample@gmail.com"
        assert result["data"] == {
            "region": "europe",
            "username": "sample@gmail.com",
            "api_token": "api_token",
            "expiry": 100,
            "refresh": "refresh_token",
        }
        assert result["options"] == {"scan_interval": POLLING_INTERVAL}


async def test_flow_wrong_password(hass: HomeAssistant) -> None:
    """Test incorrect login throwing error."""
    with patch(
        "custom_components.owlet.config_flow.OwletAPI.authenticate",
        side_effect=OwletPasswordError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"password": "invalid_password"}


async def test_flow_wrong_email(hass: HomeAssistant) -> None:
    """Test incorrect login throwing error."""
    with patch(
        "custom_components.owlet.config_flow.OwletAPI.authenticate",
        side_effect=OwletEmailError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"username": "invalid_email"}


async def test_flow_credentials_error(hass: HomeAssistant) -> None:
    """Test incorrect login throwing error."""
    with patch(
        "custom_components.owlet.config_flow.OwletAPI.authenticate",
        side_effect=OwletCredentialsError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_credentials"}


async def test_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error throwing error."""
    with patch(
        "custom_components.owlet.config_flow.OwletAPI.authenticate",
        side_effect=Exception(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_flow_no_devices(hass: HomeAssistant) -> None:
    """Test unknown error throwing error."""
    with (
        patch("custom_components.owlet.config_flow.OwletAPI.authenticate"),
        patch(
            "custom_components.owlet.config_flow.OwletAPI.get_devices",
            side_effect=OwletDevicesError(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "no_devices"}


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test reauth form."""

    entry = await async_init_integration(hass, skip_setup=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.owlet.config_flow.OwletAPI.authenticate",
        return_value=AUTH_RETURN,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "sample"},
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

        await hass.config_entries.async_unload(entry.entry_id)


async def test_reauth_invalid_password(hass: HomeAssistant) -> None:
    """Test reauth with invalid password errir."""
    entry = await async_init_integration(hass, skip_setup=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}
    )

    with patch(
        "custom_components.owlet.config_flow.OwletAPI.authenticate",
        side_effect=OwletPasswordError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "sample"}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"password": "invalid_password"}


async def test_reauth_unknown_error(hass: HomeAssistant) -> None:
    """Test reauthing with an unknown error."""

    entry = await async_init_integration(hass, skip_setup=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}
    )

    with patch(
        "custom_components.owlet.config_flow.OwletAPI.authenticate",
        side_effect=Exception(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "sample"}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "unknown"}


async def test_flow_same_email_different_region(hass: HomeAssistant) -> None:
    """Test that the same email can be added for different regions."""

    with (
        patch(
            "custom_components.owlet.config_flow.OwletAPI.authenticate",
            return_value=AUTH_RETURN,
        ),
        patch("custom_components.owlet.config_flow.OwletAPI.get_devices"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY

    with (
        patch(
            "custom_components.owlet.config_flow.OwletAPI.authenticate",
            return_value=AUTH_RETURN,
        ),
        patch("custom_components.owlet.config_flow.OwletAPI.get_devices"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT_WORLD,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["region"] == "world"


async def test_flow_duplicate_region_and_email(hass: HomeAssistant) -> None:
    """Test that duplicate email + region is still blocked."""

    with (
        patch(
            "custom_components.owlet.config_flow.OwletAPI.authenticate",
            return_value=AUTH_RETURN,
        ),
        patch("custom_components.owlet.config_flow.OwletAPI.get_devices"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    entry = await async_init_integration(hass, skip_setup=True)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 10},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {
        CONF_SCAN_INTERVAL: 10,
        "stale_threshold": 0,
        "activation_interval": 30,
        "body_position": False,
    }


async def test_legacy_v2_whitespace_identity_blocks_normalized_duplicate(hass):
    from .test_superintegration import create_entry

    entry = create_entry(
        hass,
        unique_id="europe_ parent@example.invalid ",
        username=" Parent@Example.invalid ",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "region": "europe",
            "username": "parent@example.invalid",
            "password": "pass",
        },
    )
    assert (
        result["type"] == FlowResultType.ABORT
        and result["reason"] == "already_configured"
    )
    assert entry.unique_id == "europe_ parent@example.invalid "


async def test_reconfigure_region_updates_in_place(hass):
    from .test_superintegration import create_entry

    entry = create_entry(hass, options={"scan_interval": 17, "custom": "kept"})
    before_id = entry.entry_id
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
    )
    with (
        patch(
            "custom_components.owlet.config_flow.authenticate_account",
            return_value=(AUTH_RETURN, {}),
        ),
        patch.object(hass.config_entries, "async_reload", return_value=True) as reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"region": "world", "password": "pass"}
        )
    assert result["reason"] == "reconfigure_successful"
    assert (
        entry.entry_id == before_id
        and entry.unique_id == "world_parent@example.invalid"
    )
    assert (
        entry.data["region"] == "world"
        and entry.data["username"] == "parent@example.invalid"
    )
    assert entry.options == {"scan_interval": 17, "custom": "kept"}
    reload.assert_awaited_once_with(entry.entry_id)
