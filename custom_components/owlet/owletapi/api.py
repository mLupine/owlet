import asyncio
import logging
import math
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from logging import Logger
from typing import Any, NotRequired, TypedDict

import aiohttp

from .const import REGION_INFO, WRITABLE_PROPERTIES
from .exceptions import (
    OwletAuthenticationError,
    OwletConnectionError,
    OwletCredentialsError,
    OwletDeviceError,
    OwletDevicesError,
    OwletEmailError,
    OwletError,
    OwletPasswordError,
    OwletPermissionError,
    OwletRateLimitError,
    OwletReadOnlyError,
)

logger: Logger = logging.getLogger(__package__)


MIN_RETRY_AFTER = 5.0
MAX_RETRY_AFTER = 3600.0
DISCOVERY_CONCURRENCY = 4


TOO_MANY_ATTEMPTS_BACKOFF = 900.0


def _is_allowed_write(url: str) -> bool:
    """Return True when a write targets one of the properties this client may set."""
    return any(
        url.endswith(f"/properties/{name}/datapoints.json")
        for name in WRITABLE_PROPERTIES
    )


def parse_retry_after(value: Any) -> float | None:
    """Parse a Retry-After header (seconds or an HTTP date) into seconds.

    The result is clamped so a bogus header can neither hammer the service
    nor stop polling for a day.
    """
    if value is None:
        return None
    text = str(value).strip()
    try:
        seconds = float(text)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(text) - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    if not math.isfinite(seconds):
        return None
    return min(max(seconds, MIN_RETRY_AFTER), MAX_RETRY_AFTER)


def _header(headers: Any, name: str) -> Any:
    try:
        return headers.get(name)
    except AttributeError:
        return None


def _transient_error(status: int, headers: Any) -> OwletConnectionError | None:
    """Return the error for a status that is the service's problem, not ours.

    429 and 5xx are transient: retry later, never treat them as a bad login.
    """
    if status == 429:
        return OwletRateLimitError(
            "Owlet is rate limiting requests",
            retry_after=parse_retry_after(_header(headers, "Retry-After")),
        )
    if status >= 500:
        return OwletConnectionError(
            f"Owlet service error {status}",
            retry_after=parse_retry_after(_header(headers, "Retry-After")),
        )
    return None


def _base_went_idle(properties: dict[str, dict[str, Any]]) -> bool:
    """Return True when the base station reports it stopped uploading."""
    prop = properties.get("APP_ACTIVE")
    if not isinstance(prop, dict):
        return False
    value = prop.get("value")
    if isinstance(value, str):
        value = value.strip().lower()
    return value in (0, False, "0", "false")


@dataclass
class _Reply:
    status: int
    body: Any
    headers: Any


class SockData(TypedDict):
    product_name: str
    model: str
    dsn: str
    oem_model: str
    sw_version: str
    mac: str
    lan_ip: str
    connection_status: str
    device_type: str
    manuf_model: str


class TokenDict(TypedDict):
    api_token: str | None
    expiry: float | None
    refresh: str | None


class DevicesResponse(TypedDict):
    response: list[dict[str, SockData]]
    tokens: NotRequired[TokenDict]


class PropertiesResponse(TypedDict):
    response: dict[str, dict[str, Any]]
    tokens: NotRequired[TokenDict]


class OwletAPI:
    """A class that creates an API object, to be used to call against the Owlet baby Monitor API."""

    def __init__(
        self,
        region: str,
        user: str | None = None,
        password: str | None = None,
        token: str | None = None,
        expiry: float | None = None,
        refresh: str | None = None,
        session: aiohttp.ClientSession | None = None,
        activation_interval: float = 0,
        timeout: float = 30,
    ) -> None:
        """Sets all the necessary variables for the API caller based on the passed in information, if a session is not passed in then one is created."""
        self._region = region
        self._user = user
        self._password = password
        self._auth_token: str | None = token
        try:
            parsed_expiry = float(expiry) if not isinstance(expiry, bool) else 0
        except (ValueError, TypeError, OverflowError):
            parsed_expiry = 0
        self._expiry: float | None = (
            parsed_expiry if math.isfinite(parsed_expiry) else 0
        )
        self._refresh: str | None = refresh
        self._tokens_changed: bool = False
        self._owns_session = session is None
        self.session: aiohttp.ClientSession = session or aiohttp.ClientSession()
        self._activation_tasks: dict[str, asyncio.Task] = {}
        self.tokens_updated = None
        self._request_not_before = 0.0
        self._transient_failures = 0
        self._firebase_identity = None
        self._firebase_expiry = 0.0
        self.headers: dict[str, str] = {}
        self._activation_interval = activation_interval
        self._last_activation: dict[str, float] = {}
        self._activation_retry_after: dict[str, float] = {}
        self._timeout = aiohttp.ClientTimeout(total=timeout)

        self._auth_lock = asyncio.Lock()

        if self._auth_token:
            self.headers["Authorization"] = "auth_token " + self._auth_token

        if self._region not in ["europe", "world"]:
            raise OwletAuthenticationError("Supplied region not valid")

        self._api_url = REGION_INFO[self._region]["url_base"]

    @property
    def tokens(self) -> TokenDict:
        """Returns a TokenDict object with current auth token, expiry and refresh token"""
        return {
            "api_token": self._auth_token,
            "expiry": self._expiry,
            "refresh": self._refresh,
        }

    @staticmethod
    async def _json(response: Any) -> Any:
        """Decode a JSON body, an unreadable body is a transient error."""
        try:
            return await response.json(content_type=None)
        except (aiohttp.ClientError, ValueError):
            raise OwletConnectionError("Unreadable response from Owlet") from None

    async def password_verification(self) -> None:
        """Will attempt to use the users username and password to login to the identitytoolkit api if authentication fails
        for any reason the relevant error is thrown, otherwise the returned refresh token will be stored.
        """
        api_key = REGION_INFO[self._region]["apiKey"]
        async with self.session.request(
            "POST",
            f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={api_key}",
            data={
                "email": self._user,
                "password": self._password,
                "returnSecureToken": True,
            },
            headers={
                "X-Android-Package": "com.owletcare.owletcare",
                "X-Android-Cert": "2A3BC26DB0B8B0792DBE28E6FFDC2598F9B12B74",
            },
            timeout=self._timeout,
        ) as response:
            if (
                error := _transient_error(response.status, response.headers)
            ) is not None:
                raise error
            response_json = await self._json(response)
            if response.status != 200:
                match response.status:
                    case 400:
                        message = ""
                        if isinstance(response_json, dict):
                            error_info = response_json.get("error")
                            if isinstance(error_info, dict):
                                message = str(error_info.get("message", ""))
                        match message.split(":")[0].strip():
                            case "INVALID_PASSWORD":
                                raise OwletPasswordError("Incorrect password")
                            case "INVALID_EMAIL" | "EMAIL_NOT_FOUND":
                                raise OwletEmailError("Invalid or unknown email")
                            case "INVALID_LOGIN_CREDENTIALS":
                                raise OwletCredentialsError(
                                    "Invalid login credentials",
                                )
                            case "TOO_MANY_ATTEMPTS_TRY_LATER":
                                raise OwletRateLimitError(
                                    "Too many login attempts, try again later",
                                    retry_after=TOO_MANY_ATTEMPTS_BACKOFF,
                                )
                            case (
                                "API key not valid. Please pass a valid API key."
                                | "MISSING_EMAIL"
                                | "MISSING_PASSWORD"
                            ):
                                raise OwletAuthenticationError(
                                    "Identitytoolkit API failure 400, contact dev",
                                )
                            case _:
                                raise OwletAuthenticationError(
                                    "Generic identitytoolkit error, contact dev",
                                )
                    case 403:
                        raise OwletAuthenticationError(
                            "API failure 403, contact dev",
                        )
                    case 404:
                        raise OwletAuthenticationError(
                            "IdentityToolkit API failure 404, contact dev",
                        )
                    case _:
                        raise OwletAuthenticationError(
                            f"Generic identitytoolkit error {response.status}, contact dev",
                        )

            refresh = (
                response_json.get("refreshToken")
                if isinstance(response_json, dict)
                else None
            )
            if not isinstance(refresh, str) or not refresh:
                raise OwletConnectionError("Login response carried no refresh token")
            self._update_tokens(
                new_token=self._auth_token,
                new_expiry=self._expiry,
                new_refresh=refresh,
            )

    async def get_mini_token(self, id_token: str) -> str:
        """Attempts to authenticate against the ayla mini token service with the given ID token."""
        async with self.session.request(
            "GET",
            REGION_INFO[self._region]["url_mini"],
            headers={
                "Authorization": id_token,
            },
            timeout=self._timeout,
        ) as response:
            if (
                error := _transient_error(response.status, response.headers)
            ) is not None:
                raise error
            if response.status != 200:
                match response.status:
                    case 401:
                        raise OwletAuthenticationError("Invalid id token")
                    case _:
                        raise OwletAuthenticationError(
                            "Generic ayla mini error, contact dev",
                        )

            response_json = await self._json(response)
            mini_token = (
                response_json.get("mini_token")
                if isinstance(response_json, dict)
                else None
            )
            if not isinstance(mini_token, str) or not mini_token:
                raise OwletConnectionError("Mini token response carried no token")
            return mini_token

    async def token_sign_in(self, mini_token: str) -> TokenDict | None:
        """Will use the provided mini token to attempt to authenticate against the owlet endpoint, anything other than a 200 response."""
        async with self.session.request(
            "POST",
            REGION_INFO[self._region]["url_signin"],
            json={
                "app_id": REGION_INFO[self._region]["app_id"],
                "app_secret": REGION_INFO[self._region]["app_secret"],
                "provider": "owl_id",
                "token": mini_token,
            },
            timeout=self._timeout,
        ) as response:
            if (
                error := _transient_error(response.status, response.headers)
            ) is not None:
                raise error
            if response.status != 200:
                match response.status:
                    case 401:
                        raise OwletAuthenticationError("Invalid mini token")
                    case 404:
                        raise OwletAuthenticationError(
                            "Ayla 404 error contact dev",
                        )
                    case _:
                        raise OwletAuthenticationError(
                            "Generic ayla endpoint error, contact dev",
                        )

            response_json = await self._json(response)
            access_token = expires_in = None
            if isinstance(response_json, dict):
                access_token = response_json.get("access_token")
                expires_in = response_json.get("expires_in")
            if (
                not isinstance(access_token, str)
                or not access_token
                or isinstance(expires_in, bool)
                or not isinstance(expires_in, int | float)
                or not math.isfinite(expires_in)
                or expires_in <= 0
            ):
                raise OwletConnectionError("Sign in response carried no access token")

            self._update_tokens(
                new_token=access_token,
                new_expiry=time.time() - 60 + expires_in,
                new_refresh=self._refresh,
            )

            return self.tokens if self._tokens_changed else None

    async def refresh_authentication(self) -> TokenDict | None:
        """Refresh primary access while the caller owns the authentication lock."""
        id_token = await self._refresh_firebase_identity()
        mini_token = await self.get_mini_token(id_token)
        return await self.token_sign_in(mini_token)

    async def _refresh_firebase_identity(self) -> str:
        """Rotate the shared refresh credential without exchanging primary access."""
        if not self._refresh:
            raise OwletAuthenticationError("No refresh token supplied")

        api_key = REGION_INFO[self._region]["apiKey"]
        async with self.session.request(
            "POST",
            f"https://securetoken.googleapis.com/v1/token?key={api_key}",
            data={
                "grantType": "refresh_token",
                "refreshToken": self._refresh,
            },
            headers={
                "X-Android-Package": "com.owletcare.owletcare",
                "X-Android-Cert": "2A3BC26DB0B8B0792DBE28E6FFDC2598F9B12B74",
            },
            timeout=self._timeout,
        ) as response:
            if (
                error := _transient_error(response.status, response.headers)
            ) is not None:
                raise error
            if response.status != 200:
                match response.status:
                    case 400:
                        raise OwletAuthenticationError(
                            "Refresh token not valid",
                        )
                    case _:
                        raise OwletConnectionError(
                            f"Token refresh failed with status {response.status}",
                        )

            response_json = await self._json(response)
            new_refresh = id_token = None
            if isinstance(response_json, dict):
                new_refresh = response_json.get("refresh_token")
                id_token = response_json.get("id_token")
            if (
                not isinstance(new_refresh, str)
                or not new_refresh
                or not isinstance(id_token, str)
                or not id_token
            ):
                raise OwletConnectionError("Token refresh response was incomplete")

            self._update_tokens(
                new_token=self._auth_token,
                new_expiry=self._expiry,
                new_refresh=new_refresh,
            )

        user_id = response_json.get("user_id")
        expires_in = response_json.get("expires_in")
        try:
            duration = float(expires_in)
        except (ValueError, TypeError):
            duration = 0
        if (
            isinstance(user_id, str)
            and user_id
            and math.isfinite(duration)
            and duration > 60
        ):
            self._firebase_identity = (id_token, user_id)
            self._firebase_expiry = time.monotonic() + duration - 60
        return id_token

    async def authenticate(self) -> TokenDict | None:
        """Reuse valid access without waiting for optional identity requests."""
        if self._auth_token and self._expiry is not None and self._expiry > time.time():
            return None
        async with self._auth_lock:
            with self._request_budget():
                try:
                    if self._auth_token is None and self._refresh is None:
                        if self._user is None or self._password is None:
                            raise OwletAuthenticationError(
                                "Username or password not supplied",
                            )

                        await self.password_verification()

                    if (
                        self._auth_token is None
                        or self._expiry is None
                        or self._expiry <= time.time()
                    ):
                        return await self.refresh_authentication()
                except (aiohttp.ClientError, TimeoutError):
                    raise OwletConnectionError(
                        "Error connecting to the Owlet login service"
                    ) from None

        return None

    async def firebase_identity(self) -> tuple[str, str]:
        """Share identity refresh and rotation with the primary API client."""
        async with self._auth_lock:
            with self._request_budget():
                if (
                    self._firebase_identity is None
                    or time.monotonic() >= self._firebase_expiry
                ):
                    try:
                        await self._refresh_firebase_identity()
                    except (aiohttp.ClientError, TimeoutError):
                        raise OwletConnectionError(
                            "Owlet identity refresh unavailable"
                        ) from None
                if self._firebase_identity is None:
                    raise OwletConnectionError("Identity response was incomplete")
                return self._firebase_identity

    async def validate_authentication(self) -> TokenDict:
        """Validate the token against an authenticated endpoint."""
        await self._request("GET", "/devices.json")
        return self.tokens

    async def _refresh_rejected_token(self, rejected_token: str | None) -> None:
        async with self._auth_lock:
            with self._request_budget():
                if self._auth_token == rejected_token:
                    try:
                        await self.refresh_authentication()
                    except (aiohttp.ClientError, TimeoutError):
                        raise OwletConnectionError(
                            "Owlet credential refresh unavailable"
                        ) from None

    async def close(self) -> None:
        """Cancel owned activation work without closing HA's shared session."""
        tasks = list(self._activation_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._activation_tasks.clear()
        if self._owns_session:
            await self.session.close()

    def _update_tokens(
        self,
        new_token: str | None,
        new_expiry: float | None,
        new_refresh: str | None,
    ) -> None:
        if (
            self._auth_token != new_token
            or self._expiry != new_expiry
            or self._refresh != new_refresh
        ):
            self._auth_token = new_token
            if self._auth_token:
                self.headers["Authorization"] = "auth_token " + self._auth_token
            self._expiry = new_expiry
            self._refresh = new_refresh
            self._tokens_changed = True
            if self.tokens_updated is not None:
                self.tokens_updated(self.tokens)

    async def _supported_version(self, dsn: str, versions: list[int]) -> int | None:

        properties_item = await self._fetch_properties(dsn, activate=False)
        if "REAL_TIME_VITALS" in properties_item:
            return 3 if 3 in versions else None
        if "CHARGE_STATUS" in properties_item:
            return 2 if 2 in versions else None
        return None

    async def _probe_device_versions(
        self, devices: list[dict[str, Any]], versions: list[int]
    ) -> list[int | None]:
        """Bound discovery work and isolate device-specific permission failures."""
        pending = iter(enumerate(devices))
        results: list[int | None] = [None] * len(devices)

        async def probe_pending_devices() -> None:
            for index, device in pending:
                try:
                    results[index] = await self._supported_version(
                        device["device"]["dsn"], versions
                    )
                except OwletDeviceError:
                    continue

        workers = [
            asyncio.create_task(probe_pending_devices())
            for _ in range(min(DISCOVERY_CONCURRENCY, len(devices)))
        ]
        try:
            await asyncio.gather(*workers)
        finally:
            for worker in workers:
                if not worker.done():
                    worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        return results

    async def get_devices(
        self,
        versions: list[int] | None = None,
    ) -> DevicesResponse:
        """Returns a list of devices from the Owlet API."""
        versions = versions or [3, 2]
        api_response = await self._request(
            "GET",
            "/devices.json",
        )

        if isinstance(api_response, list):
            devices = [
                item
                for item in api_response
                if isinstance(item, dict)
                and isinstance(item.get("device"), dict)
                and isinstance(item["device"].get("dsn"), str)
                and item["device"]["dsn"]
            ]

            unique_devices = {}
            for device in devices:
                unique_devices.setdefault(device["device"]["dsn"], device)
            devices = list(unique_devices.values())

            results = await self._probe_device_versions(devices, versions)

            valid_devices = [
                {**device, "verified_version": version}
                for device, version in zip(devices, results, strict=True)
                if version is not None
            ]

            if not valid_devices:
                raise OwletDevicesError("No devices found")
            response: DevicesResponse = {"response": valid_devices}
            if self._tokens_changed:
                response["tokens"] = self.tokens
                self._tokens_changed = False
            return response
        else:
            raise OwletError("Unexpected response type from request.")

    async def activate(self, device_serial: str) -> None:
        """Sets APP_ACTIVE on the Owlet API to 1 to return properties."""
        data = {"datapoint": {"metadata": {}, "value": 1}}
        await self._request(
            "POST",
            f"/dsns/{device_serial}/properties/APP_ACTIVE/datapoints.json",
            data=data,
            record_transient_failure=False,
        )
        self._last_activation[device_serial] = time.monotonic()

    async def _maybe_activate(self, device_serial: str, force: bool = False) -> None:
        """Activate the device unless it was activated within the activation interval.

        force skips the interval: used when the base station reported that it
        went idle, so waiting would only lose readings.
        """
        if time.monotonic() < self._activation_retry_after.get(device_serial, 0):
            return
        last = self._last_activation.get(device_serial)
        if (
            not force
            and self._activation_interval > 0
            and last is not None
            and time.monotonic() - last < self._activation_interval
        ):
            return
        try:
            await self.activate(device_serial)
        except OwletError as error:
            delay = max(
                self._activation_interval, 5, getattr(error, "retry_after", 0) or 0
            )
            self._activation_retry_after[device_serial] = time.monotonic() + delay
            raise
        self._activation_retry_after.pop(device_serial, None)

    async def get_properties(
        self,
        device: str,
    ) -> PropertiesResponse:
        """Gets the properties from the Owlet API for a given device."""
        response: PropertiesResponse = {
            "response": await self._fetch_properties(device, activate=True)
        }

        if self._tokens_changed:
            response["tokens"] = self.tokens
            self._tokens_changed = False
        return response

    async def _fetch_properties(
        self, device: str, activate: bool
    ) -> dict[str, dict[str, Any]]:
        """Fetch the raw properties without reporting refreshed tokens."""
        api_response = await self._request(
            "GET",
            f"/dsns/{device}/properties.json",
        )
        if not isinstance(api_response, list):
            raise OwletError("Unexpected response type from request.")
        properties = {
            item["property"]["name"]: item["property"]
            for item in api_response
            if isinstance(item, dict)
            and isinstance(item.get("property"), dict)
            and isinstance(item["property"].get("name"), str)
        }
        if activate:
            existing = self._activation_tasks.get(device)
            if existing is None or existing.done():
                self._activation_tasks[device] = asyncio.create_task(
                    self._activate_quietly(device, force=_base_went_idle(properties))
                )
        return properties

    async def _activate_quietly(self, device: str, force: bool = False) -> None:
        """Write APP_ACTIVE when due; a transient failure is logged, not raised."""
        try:
            await self._maybe_activate(device, force=force)
        except Exception:
            logger.warning("Owlet activation failed; retrying on a later poll")

    async def post_command(
        self, device: str, command: str, data: dict[str, Any]
    ) -> Any:
        return await self._request(
            "POST", f"/dsns/{device}/properties/{command}/datapoints.json", data
        )

    async def _request(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
        *,
        record_transient_failure: bool = True,
    ) -> Any:
        """Send a request to the Owlet API and return the response."""
        if method != "GET" and not _is_allowed_write(url):
            raise OwletReadOnlyError(
                f"Refusing {method} {url}: only {sorted(WRITABLE_PROPERTIES)} may be written"
            )
        with self._request_budget(record_transient_failure=record_transient_failure):
            await self.authenticate()
            self._check_backoff()
            rejected_token = self._auth_token
            reply = await self._send(method, url, data)

            if reply.status == 401:
                await self._refresh_rejected_token(rejected_token)
                self._check_backoff()
                reply = await self._send(method, url, data)

            if reply.status == 401:
                raise OwletAuthenticationError("Owlet API rejected the token (401)")
            self._raise_for_status(reply)
            if record_transient_failure:
                self._transient_failures = 0
            return reply.body

    def _check_backoff(self) -> None:
        remaining = self._request_not_before - time.monotonic()
        if remaining > 0:
            raise OwletRateLimitError(
                "Owlet requests are backed off", retry_after=remaining
            )

    def _record_failure(self, error: OwletConnectionError) -> None:
        now = time.monotonic()
        if self._request_not_before > now:
            if error.retry_after:
                self._request_not_before = max(
                    self._request_not_before, now + error.retry_after
                )
            return
        self._transient_failures += 1
        delay = max(
            min(5 * 2 ** min(self._transient_failures - 1, 6), 300),
            error.retry_after or (60 if isinstance(error, OwletRateLimitError) else 0),
        )
        self._request_not_before = now + delay

    @contextmanager
    def _request_budget(self, *, record_transient_failure: bool = True):
        """Fail fast during shared cooldowns; never sleep while holding a lock."""
        self._check_backoff()
        try:
            yield
        except OwletDeviceError:
            raise
        except OwletConnectionError as error:
            if record_transient_failure or isinstance(error, OwletRateLimitError):
                self._record_failure(error)
            raise
        except (aiohttp.ClientError, TimeoutError):
            error = OwletConnectionError("Error connecting to Owlet")
            if record_transient_failure:
                self._record_failure(error)
            raise error from None

    @staticmethod
    def _raise_for_status(reply: _Reply) -> None:
        """Raise the matching transient error for an unsuccessful reply."""
        if (error := _transient_error(reply.status, reply.headers)) is not None:
            raise error
        if reply.status == 403:
            raise OwletPermissionError("Owlet API denied device access (403)")
        if reply.status not in (200, 201):
            raise OwletDeviceError(f"Owlet API returned status {reply.status}")

    async def _send(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
    ) -> _Reply:
        """Send one request and return the status, decoded JSON body and headers."""
        try:
            async with self.session.request(
                method,
                self._api_url + url,
                headers=dict(self.headers),
                json=data,
                timeout=self._timeout,
            ) as response:
                body = None
                if response.status in (200, 201):
                    body = await self._json(response)
                return _Reply(response.status, body, response.headers)
        except (aiohttp.ClientError, TimeoutError):
            raise OwletConnectionError("Error connecting to Owlet") from None
