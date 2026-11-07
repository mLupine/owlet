# Owlet for Home Assistant

Maintained at [mLupine/owlet](https://github.com/mLupine/owlet), based on Ryan Clark's Owlet integration and the attributed public-fork work in [docs/fork-adoption.md](docs/fork-adoption.md).

Supports the existing Smart Sock 2/3 cloud protocol and additional Dream Sock properties when the account exposes them. It requires Owlet's cloud. Cloud snapshots, Home Assistant automations and optional phone notifications can be delayed; they cannot establish that the baby or physical device is currently in a particular state.

## Upgrade an existing installation

Update the existing `mLupine/owlet` custom repository through HACS. Keep the existing Owlet config entries. Do not delete/re-add them. Restart Home Assistant after replacing the component files. Manual installation replaces only `config/custom_components/owlet` with the contents of `dist/owlet.zip`.

The integration domain stays `owlet`, account schema stays v2, and existing device/entity unique IDs stay serial-based, including the base-station switch. Credentials, options and registry overrides remain. Tests exercise both v1 migration and v2 upgrade with actual HA registry objects and recorder rows. Valid v1 account IDs migrate automatically; malformed identities, collisions and unsupported future schemas are refused rather than guessed. Back up the HA configuration and recorder before changing versions; an older v1 implementation has no reverse migration for v2 entries.

Minimum tested Home Assistant: **2024.1.2**. Also tested with **2026.10.2**. See [validation](docs/validation.md) for exact environments and limits. The bundled client is MIT licensed; its license ships in the installation archive. The integration retains its Apache-2.0 license.

## Change polling in Home Assistant

Open **Settings → Devices & services → Integrations → Owlet → Configure** (the entry's options/gear control). Save a polling interval from **5 to 3600 seconds**. The default remains **5 seconds**. The running coordinators reschedule using the new interval; no HA restart or account recreation is required. Unknown stored option keys are preserved. Credential rotation saves do not reload platforms.

Additional options:

- Measurement freshness limit: **5 minutes** by default, **0** disables freshness checks, maximum 120 minutes.
- APP_ACTIVE cadence: **30 seconds** by default, configurable from 10 to 600 seconds. An observed idle APP_ACTIVE value requests reactivation sooner. Writes run separately from read publication and are cancelled on unload. This cadence is an integration policy, not a verified cloud guarantee.
- Historical body position: **off by default**. Uses a separate 60-second coordinator with a five-minute sample limit. Enabling it never adds HTTP latency to primary telemetry.

The entry menu's **Reconfigure** action can authenticate the same username in a different region while retaining the entry. It refuses an already configured account/region. Reauthentication errors distinguish invalid credentials, connectivity, rate limits and unexpected failures.

## Readings and diagnostics

Measurements use the timestamp of their actual raw property. V3 measurements share REAL_TIME_VITALS; v2 properties each keep their own times. Independently updated statuses use their own timestamps. Missing/invalid times mean unknown freshness; polling time is never substituted. Expiry occurs at the nearest entity deadline even with slow polling. Charging-sensitive readings remain unavailable while charging or when charging state is unknown.

Standalone alert/status flags in the event mapping retain their last reported event value while authenticated polling succeeds; an unchanged event timestamp alone does not expire them. Their raw mappings and the precise freshness policy are documented in [docs/freshness.md](docs/freshness.md). HTTP success does not establish live device connectivity. Last reading and Data stale diagnostics expose measurement freshness; a repair warning uses the actual affected vital, even if battery continues updating. Download diagnostics uses an allowlist and omits accounts, credentials, serials, MACs, baby data and raw cloud payloads. HA itself may still log an existing entry title containing an email.

Malformed fields do not discard valid neighboring values. Nonfinite and boolean numeric readings become unknown. Oxygen and battery percentages use the protocol's 0–100 domain. Heart rate and temperature do not use invented physiological cutoffs. Unknown sleep codes remain unknown. New capabilities appearing after the initial snapshot add entities without a reload.

The base-station switch keeps the established command payload. A command returns success only after a successful poll reads the requested state. This is cloud readback verification, not proof of physical actuation or a guarantee that the returned snapshot is newly generated.

## Experimental historical body position

The additional route comes from Chris Williams's fork. It requires an exact DSN device match and one unambiguous service/profile association. There is no account-wide first-baby fallback. Identity refresh shares the primary client's refresh lock and persistence; identity tokens and profiles are cached. Profile mapping is rechecked after five minutes. Unsupported accounts, ambiguous mappings, missing timestamps and samples older than five minutes produce unavailable/unknown position.

The bounded 0–9 labels are derived from that fork and have not been independently established by vendor documentation or a live capture. Other codes are unknown; there is **no verified tummy-code mapping**. `positionTimes` supports epoch seconds or timezone-aware ISO strings; millisecond epochs, mismatched arrays and future samples are rejected. Do not interpret this optional historical sensor as a safety monitor.

## Optional examples

The [blueprints](blueprints/automation/owlet) send Companion phone notifications. Import them manually and select the intended alert entities/phone. Initial-active notifications explicitly control startup and unavailable/unknown → on recovery; the default is off to avoid restart bursts. Recovery notifications are separate. These files do not install automations automatically. Companion device notification delivery is not tested against a real phone.

The [English and Dutch dashboards](dashboards) are optional examples adapted from Lucas Vollebergh/idomp. Replace sample entity references with your existing entity IDs; user naming overrides and HA versions affect generated names. They require no custom cards. Copy the YAML into a manual dashboard. Their schema/text is checked, but no browser-rendering claim is made.

## Development and packaging

Use Python 3.14.5 for the current test profile or Python 3.13.15 for the minimum profile. Install the corresponding hash-pinned requirements lock. Run `python -m pytest`, `ruff check custom_components tests scripts` and `ruff format --check custom_components tests scripts`. `python scripts/build_release.py` creates flat `dist/owlet.zip`, separate optional `dist/owlet-examples.zip`, and SHA256SUMS without publishing.

[Implementation plan](docs/superintegration-plan.md), [adoption and exclusions](docs/fork-adoption.md), [decisions](docs/superintegration-decisions.tsv), and [validation evidence](docs/validation.md) are kept for parent review. No live Owlet account, installed HA instance, device or phone was changed during implementation.
