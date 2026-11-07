# Owlet for Home Assistant

Maintained by mLupine. Upgrades retain existing account entries, credentials,
serial-based entities, user registry overrides, recorder history and the base-station
switch. Do not delete/re-add entries when updating.

Polling is configurable under Settings → Devices & services → Owlet → Configure.
The default remains five seconds; saves apply to the running coordinators.

The superintegration adds source-timestamp freshness, stale diagnostics, robust
parsing/authentication, Dream Sock statuses and optional historical body position.
Position is experimental and disabled by default. Optional notification blueprints
and dashboards are installed manually.

Minimum tested HA: 2024.1.2. Read README.md for installation, exact policies,
attribution, validation commands and limitations.
