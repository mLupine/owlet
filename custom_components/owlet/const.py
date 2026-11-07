"""Constants and persisted option validation."""

DOMAIN = "owlet"
CONF_OWLET_EXPIRY = "expiry"
CONF_OWLET_REFRESH = "refresh"
CONF_STALE_THRESHOLD = "stale_threshold"
CONF_ACTIVATION_INTERVAL = "activation_interval"
CONF_BODY_POSITION = "body_position"
SUPPORTED_VERSIONS = [2, 3]
POLLING_INTERVAL = 5
DEFAULT_STALE_THRESHOLD = 5
DEFAULT_ACTIVATION_INTERVAL = 30
MANUFACTURER = "Owlet Baby Care"
SLEEP_STATES = {0: "unknown", 1: "awake", 8: "light_sleep", 15: "deep_sleep"}


def integer_option(
    options: dict, key: str, default: int, minimum: int, maximum: int
) -> int:
    value = options.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return default
    try:
        number = int(value)
        if float(value) != number or not minimum <= number <= maximum:
            return default
    except (ValueError, TypeError, OverflowError):
        return default
    return number


def polling_interval(options: dict) -> int:
    return integer_option(options, "scan_interval", POLLING_INTERVAL, 5, 3600)


def account_unique_id(region: str, username: str) -> str:
    return f"{region}_{username.strip().lower()}"


def find_account_entry(
    hass, region: str, username: str, exclude_entry_id: str | None = None
):
    unique_id = account_unique_id(region, username)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude_entry_id:
            continue
        stored_region = entry.data.get("region")
        stored_username = entry.data.get("username")
        if entry.unique_id == unique_id:
            return entry
        if (
            stored_region in ("world", "europe")
            and isinstance(stored_username, str)
            and account_unique_id(stored_region, stored_username) == unique_id
        ):
            return entry
    return None
