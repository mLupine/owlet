"""The Owlet Smart Sock integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_REGION, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import async_get_platforms

from .const import (
    CONF_OWLET_EXPIRY,
    CONF_OWLET_REFRESH,
    DOMAIN,
    SUPPORTED_VERSIONS,
    account_unique_id,
    find_account_entry,
)
from .coordinator import OwletCoordinator, store_tokens
from .owletapi.api import OwletAPI
from .owletapi.exceptions import (
    OwletAuthenticationError,
    OwletCredentialsError,
    OwletError,
)
from .owletapi.sock import Sock

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]
_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Qualify valid legacy accounts without changing data or registry identity."""
    if config_entry.version == 2:
        return True
    if config_entry.version != 1:
        return False
    region = config_entry.data.get(CONF_REGION)
    username = config_entry.data.get(CONF_USERNAME)
    if (
        region not in ("world", "europe")
        or not isinstance(username, str)
        or not username.strip()
    ):
        return False
    unique_id = account_unique_id(region, username)
    if find_account_entry(hass, region, username, config_entry.entry_id) is not None:
        return False
    hass.config_entries.async_update_entry(config_entry, unique_id=unique_id, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Create one shared authenticated client and independent device coordinators."""
    hass.data.setdefault(DOMAIN, {})
    api = None
    coordinators = {}
    setup_complete = False
    try:
        api = OwletAPI(
            region=entry.data[CONF_REGION],
            token=entry.data.get(CONF_API_TOKEN),
            expiry=entry.data.get(CONF_OWLET_EXPIRY),
            refresh=entry.data.get(CONF_OWLET_REFRESH),
            session=async_get_clientsession(hass),
        )
        api.tokens_updated = lambda tokens: store_tokens(hass, entry, tokens)
        returned_tokens = await api.authenticate()
        if isinstance(returned_tokens, dict):
            store_tokens(hass, entry, returned_tokens)
        devices = await api.get_devices(SUPPORTED_VERSIONS)
        if isinstance(devices.get("tokens"), dict):
            store_tokens(hass, entry, devices["tokens"])
        for device in devices["response"]:
            sock = Sock(api, device["device"], device.get("verified_version"))
            coordinators[sock.serial] = OwletCoordinator(hass, sock, entry)
        if not coordinators:
            raise ConfigEntryNotReady("No supported Owlet devices found")
        refresh_tasks = [
            asyncio.create_task(coordinator.async_config_entry_first_refresh())
            for coordinator in coordinators.values()
        ]
        try:
            await asyncio.gather(*refresh_tasks)
        finally:
            for task in refresh_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*refresh_tasks, return_exceptions=True)
        setup_complete = True
    except (OwletAuthenticationError, OwletCredentialsError):
        raise ConfigEntryAuthFailed(
            "Owlet authentication expired; sign in again"
        ) from None
    except (OwletError, TimeoutError):
        raise ConfigEntryNotReady("Unable to retrieve Owlet devices") from None
    except (ConfigEntryAuthFailed, ConfigEntryNotReady):
        raise
    except Exception as error:
        _LOGGER.warning("Unexpected Owlet setup error type: %s", type(error).__name__)
        raise ConfigEntryNotReady("Unexpected Owlet setup failure") from None
    finally:
        if api is not None:
            store_tokens(hass, entry, api.tokens)
        if not setup_complete:
            for coordinator in coordinators.values():
                await coordinator.async_close()
            if api is not None:
                await api.close()
    hass.data[DOMAIN][entry.entry_id] = coordinators

    @callback
    def stop_coordinators():
        for coordinator in coordinators.values():
            coordinator.shutdown()

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        for coordinator in coordinators.values():
            await coordinator.async_close()
        await api.close()
        loaded_platforms = {
            platform.domain
            for platform in async_get_platforms(hass, DOMAIN)
            if platform.config_entry is entry
        }
        if loaded_platforms:
            await hass.config_entries.async_unload_platforms(entry, loaded_platforms)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    entry.async_on_unload(stop_coordinators)
    for coordinator in coordinators.values():
        coordinator.configure_body_position()
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply only changed runtime options; credential writes never reload platforms."""
    for coordinator in hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).values():
        await coordinator.async_apply_options()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    coordinators = hass.data[DOMAIN].pop(entry.entry_id, {})
    for coordinator in coordinators.values():
        await coordinator.async_close()
    if coordinators:
        await next(iter(coordinators.values())).sock.api.close()
    return True
