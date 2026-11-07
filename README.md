# Owlet for Home Assistant

Maintained at [mLupine/owlet](https://github.com/mLupine/owlet), based on Ryan Clark's Owlet integration and the attributed public-fork work in [docs/fork-adoption.md](docs/fork-adoption.md).

Supports the existing Smart Sock 2/3 cloud protocol and additional Dream Sock properties when the account exposes them. It requires Owlet's cloud. Cloud snapshots, Home Assistant automations and optional phone notifications can be delayed; they cannot establish that the baby or physical device is currently in a particular state.

## Upgrade an existing installation

Update the existing `mLupine/owlet` custom repository through HACS. Keep the existing Owlet config entries. Do not delete/re-add them. Restart Home Assistant after replacing the component files. Manual installation replaces only `config/custom_components/owlet` with the contents of `dist/owlet.zip`.

The integration domain stays `owlet`, account schema stays v2, and existing device/entity unique IDs stay serial-based, including the base-station switch. Credentials, options and registry overrides remain. Tests exercise both v1 migration and v2 upgrade with actual HA registry objects and recorder rows. Valid v1 account IDs migrate automatically; malformed identities, collisions and unsupported future schemas are refused rather than guessed. Back up the HA configuration and recorder before changing versions; an older v1 implementation has no reverse migration for v2 entries.

Minimum tested Home Assistant: **2024.1.2**. Also tested with **2026.10.2**. See [validation](docs/validation.md) for exact environments and limits. The bundled client is MIT licensed; its license ships in the installation archive. The integration retains its Apache-2.0 license.

## Change polling in Home Assistant

Open **Settings → Devices & services → Integrations → Owlet → Configure** (the entry's options/gear control). Save a polling interval from **5 to 3600 seconds**. Existing intervals above 3600 seconds are preserved; their options form accepts up to the stored interval. The default remains **5 seconds**. The running coordinators reschedule using the new interval; no HA restart or account recreation is required. Unknown stored option keys are preserved. Credential rotation saves do not reload platforms.

Additional options:

- Measurement freshness limit: **0/off by default** for new and existing entries, maximum 120 minutes. Enable it explicitly. When enabled, its duration must be strictly longer than the polling interval. Existing explicit settings remain effective. V2 properties can remain unchanged for hours even in a healthy capture; enabled gating keeps each original source time and can hide those readings.
- APP_ACTIVE cadence: **30 seconds** by default, configurable from 10 to 600 seconds. An observed idle APP_ACTIVE value requests reactivation sooner. Writes run separately from read publication and are cancelled on unload. This cadence is an integration policy, not a verified cloud guarantee.
- Historical body position: **off by default**. Uses a separate 60-second coordinator with a five-minute sample limit. Enabling it never adds HTTP latency to primary telemetry.

On **HA 2024.4 or newer**, the entry menu's **Reconfigure** action can authenticate the same username in a different region while retaining the entry. It refuses an already configured account/region. Reauthentication errors distinguish invalid credentials, connectivity, rate limits and unexpected failures.

## Readings and diagnostics

Measurements use the timestamp of their actual raw property. V3 measurements share REAL_TIME_VITALS; v2 properties each keep their own times. Independently updated statuses use their own timestamps. Missing/invalid times mean unknown freshness; polling time is never substituted. When freshness is enabled, expiry occurs at the nearest entity deadline. Stored incompatible interval/threshold combinations are honored without adjustment and reported as `freshness_options_compatible: false` in diagnostics. Edit the options to resolve the mismatch. Charging-sensitive readings remain unavailable while charging or when charging state is unknown.

Standalone alert/status flags in the event mapping retain their last reported event value while authenticated polling succeeds; an unchanged event timestamp alone does not expire them. Their raw mappings and the precise freshness policy are documented in [docs/freshness.md](docs/freshness.md). HTTP success does not establish live device connectivity. Last reading exposes source time. With freshness enabled, Data stale and repair warnings use the actual affected vital, even if battery continues updating. Charging/base-off suppresses warnings only while a device-output source timestamp remains within the freshness window. Successful HTTP polls never extend that window. Download diagnostics uses an allowlist and omits accounts, credentials, serials, MACs, baby data and raw cloud payloads. HA itself may still log an existing entry title containing an email.

Device inventory and discovery metadata refresh when you reload the existing Owlet entry or restart HA. Reload after adding or removing a sock. Removed devices retain registry records and customizations; their entities become unavailable. A returning serial reuses those records, including user-disabled entities. Optional properties first observed during normal polls add entities once without a reload. Duplicate serials in one discovery response are checked once. There is no additional discovery polling loop.

Transient account failures pause requests across socks and authentication. Retry-After seconds or HTTP dates are honored within the client's 5–3600-second bounds; absent server/network delays increase from five seconds to at most five minutes. The coordinator never polls faster than the configured interval. A 401 permits one shared credential refresh and retry. A device-level 403 cannot rotate account credentials or block sibling devices. Unload cancels and joins primary polls, activation, historical work and switch readback. No sleeps hold the authentication lock.

Malformed fields do not discard valid neighboring values. Nonfinite and boolean numeric readings become unknown. Oxygen and battery percentages use the protocol's 0–100 domain. Heart rate and temperature do not use invented physiological cutoffs. Unknown sleep codes remain unknown. New capabilities appearing after the initial snapshot add entities without a reload.

The base-station switch keeps the established command payload and always shows cloud readback state. A service returns when the cloud accepts the request. Its `command_status` attribute is then `pending`; a subsequent matching poll sets `confirmed`. The integration requests readback every two seconds for up to 30 seconds. An inconclusive timeout sets `unconfirmed` and logs a sanitized warning without aborting the automation. A later matching poll can still confirm it. POST errors reject the service. Requests are serialized, and the last accepted command supersedes earlier confirmation. Unload cancels and joins readback work. Matching cloud state does not prove physical actuation or a newly generated snapshot.

## Experimental historical body position

The additional route comes from Chris Williams's fork. It requires an exact DSN device match and one unambiguous service/profile association. There is no account-wide first-baby fallback. Identity refresh shares the primary client's refresh lock and persistence; identity tokens and profiles are cached. Profile mapping is rechecked after five minutes. Unsupported accounts, ambiguous mappings, missing timestamps and samples older than five minutes produce unavailable/unknown position.

The bounded 0–9 labels are derived from that fork and have not been independently established by vendor documentation or a live capture. Other codes are unknown; there is **no verified tummy-code mapping**. `positionTimes` supports epoch seconds or timezone-aware ISO strings; millisecond epochs, mismatched arrays and future samples are rejected. Do not interpret this optional historical sensor as a safety monitor.

## Optional examples

The [blueprints](blueprints/automation/owlet) send Companion phone notifications. Import them manually and select the intended alert entities/phone. Initial-active notifications explicitly control startup and unavailable/unknown → on recovery; the alert blueprint defaults this option on so an alert appearing after unavailable/unknown still notifies. The stale-data blueprint defaults it off. Each blueprint exposes the choice. Recovery notifications are separate. These files do not install automations automatically. Companion device notification delivery is not tested against a real phone.

The UI includes English, French, Ukrainian, and Dutch translations. Icon metadata is loaded by supported HA versions and ignored by HA 2024.1.2.

The [English and Dutch dashboards](dashboards) are optional examples adapted from Lucas Vollebergh/idomp. They show disabled freshness, failed polling and unknown alert states explicitly. Freshness text reads the backend Data stale attributes, including `freshness_enabled`; it does not create a frontend clock. Optional controls have their own view. These examples use modern sections/heading frontend cards; the integration's HA 2024.1.2 floor does not establish frontend support for those cards. Replace sample entity references with your existing entity IDs; user naming overrides and HA versions affect generated names. They require no custom cards. Copy the YAML into a manual dashboard. Their schema/text is checked, but no browser-rendering claim is made.

## Diagnostics and retained history

Download diagnostics includes component/HA versions, anonymous device capabilities and operational categories. It excludes stored account data, credentials, names, serials, network addresses and readings. Existing entry titles and entity names can still appear in HA's own logs. Review reports before sharing them.

Recorder rows, long-term statistics and backups can retain physiological history. Use HA's optional recorder exclusions and your backup retention policy to reduce future storage. Exclusions do not erase existing history, statistics or backup copies. Their deletion is a separate owner decision. This integration does not modify recorder settings or purge data.

## Development and packaging

Use Python 3.11.16 for HA 2024.1.2, Python 3.13.15 for HA 2024.12.5, or Python 3.14.5 for HA 2026.10.2. Install the corresponding hash-pinned requirements lock. Run `python -m pytest`, `ruff check custom_components tests scripts` and `ruff format --check custom_components tests scripts`. `python scripts/build_release.py` creates flat `dist/owlet.zip`, separate optional `dist/owlet-examples.zip`, and SHA256SUMS without publishing. It refuses unexpected component files and requires the complete reviewed runtime inventory. Use `--tag VERSION` to enforce manifest/tag equality and `--source-archive FILE.zip` to compare candidate runtime bytes with a Git source archive.

[Roadmap coverage](docs/roadmap-coverage.md), [implementation plan](docs/superintegration-plan.md), [adoption and exclusions](docs/fork-adoption.md), [decisions](docs/superintegration-decisions.tsv), and [validation evidence](docs/validation.md) are kept for parent review. No live Owlet account, installed HA instance, device or phone was changed during implementation.
