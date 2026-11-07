# Owlet for Home Assistant

Maintained by mLupine. Upgrades retain existing account entries, credentials,
serial-based entities, user registry overrides, recorder history and the base-station
switch. Do not delete/re-add entries when updating.

Polling is configurable under Settings → Devices & services → Owlet → Configure.
The default remains five seconds; saves apply to the running coordinators.

Freshness defaults off for both new and existing entries. Enable it in options
with a duration longer than the polling interval. Explicit saved settings remain.

The superintegration adds source-timestamp freshness, stale diagnostics, robust
parsing/authentication, Dream Sock statuses and optional historical body position.
Commands expose pending/confirmed/unconfirmed cloud readback without optimistic
physical state. The UI includes Dutch translations and icon metadata.
Position is experimental and disabled by default. Optional notification blueprints
and dashboards are installed manually.

Minimum supported Home Assistant: 2026.10.2. Read README.md for installation, exact policies,
attribution, validation commands and limitations.
