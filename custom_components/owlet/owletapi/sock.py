"""Sock property normalization and the established base-station command."""

import json
import math
import time
from datetime import UTC, datetime
from typing import Any

from .api import OwletAPI, SockData
from .const import PROPERTIES, VALID_RANGES, VITALS_2, VITALS_3


def decode_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def decode_bool(value: Any) -> bool | None:
    if type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        return {"true": True, "false": False, "1": True, "0": False}.get(
            value.strip().lower()
        )
    return None


def decode_value(value: Any, kind: type, key: str) -> Any:
    if key == "charging":
        if type(value) is bool:
            return value
        number = decode_number(value)
        return bool(number) if number in (0, 1, 2) else None
    if kind is bool:
        return decode_bool(value)
    if kind is str:
        return value if isinstance(value, str) and value.strip() else None
    number = decode_number(value)
    if number is None:
        return None
    if key in VALID_RANGES:
        lower, upper = VALID_RANGES[key]
        if not lower <= number <= upper:
            return None
    if kind is int:
        return int(number) if number.is_integer() else None
    return number


def decode_object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    return value if isinstance(value, dict) else {}


def parse_timestamp(value: Any, now: datetime | None = None) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    parsed = parsed.astimezone(UTC)
    if (parsed - (now or datetime.now(UTC))).total_seconds() > 60:
        return None
    return parsed


class Sock:
    """One serial-numbered sock with independent source metadata per field."""

    def __init__(
        self, api: OwletAPI, data: SockData, version: int | None = None
    ) -> None:
        self.api = api
        self.serial = data["dsn"]
        self.name = data.get("product_name")
        self.model = data.get("model")
        self.oem_model = data.get("oem_model")
        self.sw_version = data.get("sw_version")
        self.mac = data.get("mac")
        self.version = version if version in (2, 3) else None
        self.revision: str | None = None
        self.raw_properties: dict[str, dict[str, Any]] = {}
        self.properties: dict[str, Any] = {}
        self.property_sources: dict[str, str] = {}
        self.capabilities: set[str] = set()

    def property_timestamp(self, key: str) -> datetime | None:
        source = self.property_sources.get(key)
        return parse_timestamp(
            self.raw_properties.get(source, {}).get("data_updated_at")
        )

    def property_tracks_changes_only(self, key: str) -> bool:
        source = self.property_sources.get(key)
        return self.raw_properties.get(source, {}).get("track_only_changes") is True

    @property
    def expected_vitals(self) -> tuple[str, ...]:
        return ("heart_rate", "oxygen_saturation") if self.version in (2, 3) else ()

    @property
    def last_updated_at(self) -> datetime | None:
        keys = ("heart_rate", "oxygen_saturation")
        values = [self.property_timestamp(key) for key in keys]
        return max((value for value in values if value is not None), default=None)

    def _decode_group(
        self, group: dict, values: dict, source: str | None = None
    ) -> None:
        for kind, fields in group.items():
            for key, raw_key in fields.items():
                if raw_key not in values:
                    continue
                value = values[raw_key] if source else values[raw_key].get("value")
                self.properties[key] = decode_value(value, kind, key)
                self.property_sources[key] = source or raw_key

    async def update_properties(self) -> dict:
        response = await self.api.get_properties(self.serial)
        raw = response.get("response")
        self.raw_properties = (
            {key: value for key, value in raw.items() if isinstance(value, dict)}
            if isinstance(raw, dict)
            else {}
        )
        if "REAL_TIME_VITALS" in self.raw_properties:
            self.version = 3
        elif "CHARGE_STATUS" in self.raw_properties:
            self.version = 2
        self.properties = {}
        self.property_sources = {}
        self._decode_group(PROPERTIES, self.raw_properties)
        if self.version == 3:
            self._decode_group(
                VITALS_3,
                decode_object(
                    self.raw_properties.get("REAL_TIME_VITALS", {}).get("value")
                ),
                "REAL_TIME_VITALS",
            )
            revision = decode_object(
                self.raw_properties.get("oem_sock_version", {}).get("value")
            ).get("rev")
            self.revision = (
                str(revision)
                if isinstance(revision, str | int) and not isinstance(revision, bool)
                else None
            )
        elif self.version == 2:
            self._decode_group(VITALS_2, self.raw_properties)
        if "RED_ALERT_SUMMARY" in self.raw_properties:
            self.properties["red_alert_updated_at"] = parse_timestamp(
                self.raw_properties["RED_ALERT_SUMMARY"].get("data_updated_at")
            )
            self.property_sources["red_alert_updated_at"] = "RED_ALERT_SUMMARY"
        self.capabilities.update(self.properties)
        return {"properties": self.properties, "raw_properties": self.raw_properties}

    async def control_base_station(self, on: bool) -> bool:
        value = json.dumps({"ts": int(time.time()), "val": "true" if on else "false"})
        await self.api.post_command(
            self.serial,
            "BASE_STATION_ON_CMD",
            {"datapoint": {"metadata": {}, "value": value}},
        )
        return True
