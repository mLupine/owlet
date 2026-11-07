"""Opt-in historical position, isolated from primary telemetry polling."""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import aiohttp
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_BODY_POSITION
from .entity import OwletBaseEntity
from .owletapi.exceptions import OwletError
from .owletapi.sock import decode_number, parse_timestamp

_LOGGER = logging.getLogger(__name__)
FIRESTORE_BASE = "https://firestore.googleapis.com/v1/projects/owletcare-prod/databases/(default)/documents"
POSITION_CODES = {
    0: "no_data",
    1: "moving",
    2: "undetected",
    3: "no_data",
    4: "on_back",
    5: "on_back",
    6: "on_side",
    7: "on_side",
    8: "on_side",
    9: "on_side",
}


@dataclass(frozen=True)
class ProfileContext:
    account_key: str
    profile_id: str
    device_version: str


@dataclass(frozen=True)
class PositionSample:
    position: str | None
    observed_at: datetime


def _string_field(document: dict, key: str) -> str | None:
    fields = document.get("fields")
    value = fields.get(key) if isinstance(fields, dict) else None
    text = value.get("stringValue") if isinstance(value, dict) else None
    return text if isinstance(text, str) and text else None


def latest_position(payload, now: datetime) -> PositionSample | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        return None
    times = payload["data"].get("positionTimes")
    positions = payload["data"].get("bodyPositions")
    if (
        not isinstance(times, list)
        or not isinstance(positions, list)
        or len(times) != len(positions)
    ):
        return None
    samples = []
    for timestamp, code in zip(times, positions, strict=True):
        number = decode_number(timestamp)
        try:
            observed = (
                datetime.fromtimestamp(number, UTC)
                if number is not None
                else parse_timestamp(timestamp, now)
            )
        except (ValueError, OSError, OverflowError):
            continue
        if observed is None or not 0 <= (now - observed).total_seconds() <= 300:
            continue
        position_code = decode_number(code)
        position = (
            POSITION_CODES.get(int(position_code))
            if position_code is not None and position_code.is_integer()
            else None
        )
        samples.append(PositionSample(position, observed))
    return max(samples, key=lambda sample: sample.observed_at, default=None)


class BodyPositionCoordinator(DataUpdateCoordinator[PositionSample | None]):
    """Separate slow cadence with cached, unambiguous sock-to-profile mapping."""

    def __init__(self, hass, sock, entry):
        super().__init__(
            hass,
            _LOGGER,
            name="owlet_body_position",
            update_interval=timedelta(seconds=60),
        )
        self.sock = sock
        self.entry = entry
        self._profile = None
        self._profile_expiry = 0.0
        self._cancel_expiry = None
        self._stopped = False
        self._in_flight = None

    async def _request(self, method, url, token, **kwargs):
        try:
            async with self.sock.api.session.request(
                method,
                url,
                headers={"Authorization": token},
                timeout=aiohttp.ClientTimeout(total=15),
                **kwargs,
            ) as response:
                if response.status != 200:
                    self._profile = None
                    raise UpdateFailed("Historical Owlet position request failed")
                return await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise UpdateFailed("Historical Owlet position unavailable") from None

    async def _query(self, token, collection, field, value):
        query = {
            "from": [{"collectionId": collection}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": field},
                    "op": "EQUAL",
                    "value": {"stringValue": value},
                }
            },
            "limit": 20,
        }
        rows = await self._request(
            "POST",
            f"{FIRESTORE_BASE}:runQuery",
            f"Bearer {token}",
            json={"structuredQuery": query},
        )
        if not isinstance(rows, list) or len(rows) >= 20:
            raise UpdateFailed("Invalid historical Owlet profile response")
        return [
            row["document"]
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("document"), dict)
        ]

    async def _resolve_profile(self, token) -> ProfileContext | None:
        devices = await self._query(token, "devices", "dsn", self.sock.serial)
        if len(devices) != 1 or _string_field(devices[0], "dsn") != self.sock.serial:
            return None
        device = devices[0]
        name = device.get("name")
        account = _string_field(device, "accountKey")
        if not isinstance(name, str) or not account:
            return None
        device_key = name.rsplit("/", 1)[-1]
        services = await self._query(token, "services", "deviceKey", device_key)
        profiles = set()
        for service in services:
            if _string_field(service, "deviceKey") != device_key:
                return None
            fields = service.get("fields", {})
            members = (
                fields.get("serviceUserKeys", {}).get("mapValue", {}).get("fields", {})
                if isinstance(fields, dict)
                else {}
            )
            if not isinstance(members, dict):
                return None
            profiles.update(
                key
                for key, value in members.items()
                if isinstance(value, dict) and value.get("booleanValue") is True
            )
        if len(profiles) != 1:
            return None
        return ProfileContext(
            account, profiles.pop(), self.sock.oem_model or self.sock.model or "SS3"
        )

    async def _async_update_data(self):
        self._in_flight = asyncio.current_task()
        try:
            return await self._fetch_position()
        finally:
            self._in_flight = None

    async def _fetch_position(self):
        if self._stopped or self.entry.options.get(CONF_BODY_POSITION) is not True:
            return None
        try:
            token, _ = await self.sock.api.firebase_identity()
            if time.monotonic() >= self._profile_expiry:
                self._profile = await self._resolve_profile(token)
                self._profile_expiry = time.monotonic() + (300 if self._profile else 60)
            if self._profile is None:
                return None
            profile = self._profile
            now = dt_util.utcnow()
            host = (
                "https://sleep-data.owletdata.com"
                if self.entry.data["region"] == "world"
                else "https://sleep-data.eu.owletdata.com"
            )
            payload = await self._request(
                "GET",
                f"{host}/v1/accounts/{quote(profile.account_key, safe='')}/profiles/{quote(profile.profile_id, safe='')}/sleep",
                token,
                params={
                    "startTime": str(int((now - timedelta(hours=4)).timestamp())),
                    "endTime": str(int(now.timestamp())),
                    "timeZone": self.hass.config.time_zone,
                    "version": profile.device_version,
                    "returnBodyPositions": "true",
                },
            )
            sample = latest_position(payload, now)
            if self._cancel_expiry:
                self._cancel_expiry()
                self._cancel_expiry = None
            if sample:
                self._cancel_expiry = async_track_point_in_utc_time(
                    self.hass, self._expire, sample.observed_at + timedelta(seconds=300)
                )
            return sample
        except OwletError:
            raise UpdateFailed("Historical Owlet authentication unavailable") from None
        except (KeyError, TypeError, AttributeError):
            raise UpdateFailed("Invalid historical Owlet response") from None

    @callback
    def _expire(self, now):
        self._cancel_expiry = None
        self.async_update_listeners()

    async def async_close(self):
        task = self._in_flight
        self.stop()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)

    def stop(self):
        self._stopped = True
        if self._in_flight:
            self._in_flight.cancel()
        if self._cancel_expiry:
            self._cancel_expiry()
            self._cancel_expiry = None
        self._unschedule_refresh()


class BodyPositionSensor(OwletBaseEntity, SensorEntity):
    """Experimental recent historical position; unknown codes stay unknown."""

    entity_description = SensorEntityDescription(
        key="body_position",
        translation_key="bodyposition",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    _attr_options = sorted(set(POSITION_CODES.values()))

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.sock.serial}-body_position"
        self._body = None
        self._remove_body_listener = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _handle_coordinator_update(self):
        body = self.coordinator.body_position
        if body is not self._body:
            if self._remove_body_listener:
                self._remove_body_listener()
            self._body = body
            self._remove_body_listener = (
                body.async_add_listener(self.async_write_ha_state) if body else None
            )
        super()._handle_coordinator_update()

    async def async_will_remove_from_hass(self):
        if self._remove_body_listener:
            self._remove_body_listener()
            self._remove_body_listener = None
        await super().async_will_remove_from_hass()

    @property
    def available(self):
        body = self.coordinator.body_position
        return bool(
            body
            and body.last_update_success
            and body.data
            and self.sock.properties.get("charging") is False
            and 0 <= (dt_util.utcnow() - body.data.observed_at).total_seconds() < 300
        )

    @property
    def native_value(self):
        body = self.coordinator.body_position
        return body.data.position if body and body.data else None

    @property
    def extra_state_attributes(self):
        body = self.coordinator.body_position
        return {
            "observed_at": body.data.observed_at.isoformat()
            if body and body.data
            else None,
            "experimental": True,
            "source": "historical_sleep_api",
        }
