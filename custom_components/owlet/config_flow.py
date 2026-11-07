"""Account and additive runtime settings flows."""

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACTIVATION_INTERVAL,
    CONF_BODY_POSITION,
    CONF_STALE_THRESHOLD,
    DEFAULT_ACTIVATION_INTERVAL,
    DEFAULT_STALE_THRESHOLD,
    DOMAIN,
    SUPPORTED_VERSIONS,
    account_unique_id,
    find_account_entry,
    integer_option,
    polling_interval,
)
from .owletapi.api import OwletAPI
from .owletapi.exceptions import (
    OwletAuthenticationError,
    OwletConnectionError,
    OwletCredentialsError,
    OwletDevicesError,
    OwletEmailError,
    OwletPasswordError,
    OwletRateLimitError,
)

_LOGGER = logging.getLogger(__name__)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REGION): vol.In(["europe", "world"]),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def authenticate_account(
    hass, region: str, username: str, password: str
) -> tuple[dict, dict]:
    api = OwletAPI(
        region=region,
        user=username,
        password=password,
        session=async_get_clientsession(hass),
    )
    errors = {}
    returned_tokens = None
    try:
        returned_tokens = await api.authenticate()
        await api.get_devices(SUPPORTED_VERSIONS)
    except OwletEmailError:
        errors[CONF_USERNAME] = "invalid_email"
    except OwletPasswordError:
        errors[CONF_PASSWORD] = "invalid_password"
    except (OwletAuthenticationError, OwletCredentialsError):
        errors["base"] = "invalid_credentials"
    except OwletDevicesError:
        errors["base"] = "no_devices"
    except OwletRateLimitError:
        errors["base"] = "rate_limited"
    except (OwletConnectionError, TimeoutError):
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.error("Unexpected Owlet login failure")
        errors["base"] = "unknown"
    finally:
        await api.close()
    tokens = {
        **(returned_tokens if isinstance(returned_tokens, dict) else {}),
        **api.tokens,
    }
    if not errors and not all(
        tokens.get(key) for key in ("api_token", "refresh", "expiry")
    ):
        errors["base"] = "cannot_connect"
    return tokens, errors


class OwletConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Keep mLupine's region-qualified account schema."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            region = user_input[CONF_REGION]
            if find_account_entry(self.hass, region, username) is not None:
                return self.async_abort(reason="already_configured")
            await self.async_set_unique_id(account_unique_id(region, username))
            self._abort_if_unique_id_configured()
            tokens, errors = await authenticate_account(
                self.hass, region, username, user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_create_entry(
                    title=username,
                    data={CONF_REGION: region, CONF_USERNAME: username, **tokens},
                    options={CONF_SCAN_INTERVAL: 5},
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return OptionsFlowHandler(config_entry)

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        entry = self._reauth_entry
        errors = {}
        if user_input is not None:
            tokens, errors = await authenticate_account(
                self.hass,
                entry.data[CONF_REGION],
                entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if CONF_USERNAME in errors:
                errors = {"base": "invalid_credentials"}
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **tokens}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors = {}
        if user_input is not None:
            region = user_input[CONF_REGION]
            unique_id = account_unique_id(region, entry.data[CONF_USERNAME])
            if (
                find_account_entry(
                    self.hass, region, entry.data[CONF_USERNAME], entry.entry_id
                )
                is not None
            ):
                return self.async_abort(reason="already_configured")
            tokens, errors = await authenticate_account(
                self.hass, region, entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if CONF_USERNAME in errors:
                errors = {"base": "invalid_credentials"}
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry,
                    unique_id=unique_id,
                    data={**entry.data, CONF_REGION: region, **tokens},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REGION, default=entry.data[CONF_REGION]): vol.In(
                        ["world", "europe"]
                    ),
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Use a private entry reference across old and current HA options APIs."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    def _schema(self) -> vol.Schema:
        options = self._entry.options
        return vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=polling_interval(options)
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=5, max=max(3600, polling_interval(options))),
                ),
                vol.Required(
                    CONF_STALE_THRESHOLD,
                    default=integer_option(
                        options, CONF_STALE_THRESHOLD, DEFAULT_STALE_THRESHOLD, 0, 120
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
                vol.Required(
                    CONF_ACTIVATION_INTERVAL,
                    default=integer_option(
                        options,
                        CONF_ACTIVATION_INTERVAL,
                        DEFAULT_ACTIVATION_INTERVAL,
                        10,
                        600,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=600)),
                vol.Required(
                    CONF_BODY_POSITION, default=options.get(CONF_BODY_POSITION) is True
                ): bool,
            }
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        if user_input is not None:
            try:
                validated = self._schema()(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_options"
            else:
                threshold = validated[CONF_STALE_THRESHOLD] * 60
                if threshold and threshold <= validated[CONF_SCAN_INTERVAL]:
                    errors[CONF_STALE_THRESHOLD] = "stale_threshold_too_short"
                else:
                    return self.async_create_entry(
                        title="", data={**self._entry.options, **validated}
                    )
        return self.async_show_form(
            step_id="init", data_schema=self._schema(), errors=errors
        )
