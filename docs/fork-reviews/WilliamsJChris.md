# WilliamsJChris/owlet versus ryanbdclark/owlet

Snapshot inspected 2026-11-07. This is a source review, not a claim of working Owlet cloud or Home Assistant runtime behavior.

## Practical result

The fork adds one substantial integration feature: a body-position enum sensor for version-3 socks. Existing heart rate, oxygen, sleep state, battery, alerts, switches, device discovery, and login flow remain upstream implementations. The README's newly listed sleep state is documentation catching up with existing upstream code, not a new sleep-state implementation.

Body position is obtained from a separate historical sleep-data API, not from the existing sock property response. Every normal v3 refresh now waits for this extra cloud work. The integration presents the last returned position within a four-hour query window without exposing its timestamp or testing its freshness. This deserves particular caution when interpreting it as current position.

The rest is HACS installation metadata, fork ownership/documentation/funding, an icon, translation corrections, release automation, and a reduction in CI validation coverage. Six commits is not six independently validated improvements.

## Exact comparison and method

| Item | Value |
|---|---|
| Upstream | `ryanbdclark/owlet`, branch `main` |
| Upstream SHA | `f8e0067a1e74a523b0bb4b0841b25404a6926ca8` |
| Fork | `WilliamsJChris/owlet`, default branch `main` |
| Fork SHA | `6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be` |
| Merge base | Same as upstream SHA |
| GitHub compare status | ahead, 6 ahead, 0 behind; 6 unique commits |
| Net diff | 20 files; 549 insertions, 66 deletions; includes binary icon |

[Live cross-repository comparison](https://github.com/WilliamsJChris/owlet/compare/ryanbdclark:main...main). [Pinned comparison](https://github.com/WilliamsJChris/owlet/compare/f8e0067a1e74a523b0bb4b0841b25404a6926ca8...6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be).

Live `gh api` branch endpoints independently confirmed both tips; the fork repository endpoint confirmed default branch main and not archived. GitHub compare supplied ahead/behind and the complete commit list. An isolated clone in `/tmp/owlet-williams-EEz594/repo` supplied the complete diff, per-commit diffs, parent relationships, tests, and surrounding source. No project checkout, refs, remotes, files, devices, or external communications were changed.

## Complete unique-commit inventory

All six are single-parent commits. PR numbers in subjects do not make them Git merge commits. No explicit revert exists in the unique history; transient metadata changes are called out below.

| Commit | Title | Actual effect and survival |
|---|---|---|
| [20935bbcbee501a0016796f00ee2a0f3b2da2a4e](https://github.com/WilliamsJChris/owlet/commit/20935bbcbee501a0016796f00ee2a0f3b2da2a4e) | Update hacs.json with the proper format | Removes `zip_release: true` and `filename: owlet.zip`. Remains removed at tip. Installation metadata only. |
| [4e0b2289d1683bbbb498134526cca7a8c1aab991](https://github.com/WilliamsJChris/owlet/commit/4e0b2289d1683bbbb498134526cca7a8c1aab991) | Update manifest | Changes owner and documentation/issues to fork; removes version `2025.4.3` entirely. Owner/link changes survive; version removal does not. No runtime code. |
| [3a8441a79e28d5042b496bdba55b2eb298e9d2ab](https://github.com/WilliamsJChris/owlet/commit/3a8441a79e28d5042b496bdba55b2eb298e9d2ab) | Try these changes | Restores manifest version as `1.0.0`, normalizes repository URL capitalization, adds HACS `render_readme: true`. Version later replaced by `2026.8.1`; remaining edits survive. Metadata only. |
| [8dca7ad35f3cb6034ac694ba264396e493b20fb6](https://github.com/WilliamsJChris/owlet/commit/8dca7ad35f3cb6034ac694ba264396e493b20fb6) | Update README with new repository links and badges | Redirects README badges/release/maintainer/activity links to fork, updates HACS URL, explicitly identifies maintained fork. Documentation only; survives. |
| [9f8f04765fc20036c891f5d1d0424ca0748b8651](https://github.com/WilliamsJChris/owlet/commit/9f8f04765fc20036c891f5d1d0424ca0748b8651) | Add donation badge to README (#4) | Adds Celsius donation badge reference and spacing. Definitions/support copy expanded in final commit. No integration behavior. |
| [6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be](https://github.com/WilliamsJChris/owlet/commit/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be) | Dev (#7) | Single-parent combined feature/maintenance commit: complete body-position feature, translations/tests, icon, hub metadata, version 2026.8.1, release workflow, HACS-only validation replacing old workflow, funding and documentation. All final runtime differences originate here. |

There are no unique version-only commits strictly speaking: the version edits accompany ownership/HACS metadata or the feature commit. No other hidden unique merge-side commits appear in the reachable main comparison.

## Implementation by feature

### Body-position acquisition and profile resolution

New [`custom_components/owlet/sleep_data.py`](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/custom_components/owlet/sleep_data.py#L19-L58) implements its own cloud client on HA's aiohttp session rather than extending the pinned `pyowletapi` library.

`get_firebase_id_token` (40–58) selects `REGION_INFO[region]["apiKey"]` from that external dependency and posts the existing refresh token to Google's securetoken endpoint, including Android package/certificate headers. It consumes `id_token` and `user_id`. It does not cache returned ID tokens or persist a replacement refresh token. Whether these exact fields/headers are accepted and refresh-token rotation matters was not checked against live services or dependency internals.

`_run_firestore_query` (69–94) POSTs structured queries with Bearer authorization to a fixed `owletcare-prod` Firestore project and extracts documents from result rows. Non-200 raises an aiohttp response error.

[`resolve_profile_for_dsn`](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/custom_components/owlet/sleep_data.py#L97-L202) follows this chain:

1. Exchange refresh token for Firebase ID token/user ID.
2. Query `devices` by exact DSN, limit one. Extract document ID and `accountKey`, falling back to authenticated user ID.
3. Query `services` by device document ID (`deviceKey`), limit one. Select the first truthy `serviceUserKeys` map entry.
4. If no such profile, query `serviceUsers` by account key, limit one, and use that first profile document ID.
5. Return immutable `ProfileContext(account_key, profile_id, device_version)`.

HTTP client failures are debug-logged and become `None`. Unexpected JSON shapes, missing `name` or token keys, and timeouts outside aiohttp's ClientError hierarchy are not normalized here.

[`fetch_latest_body_position`](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/custom_components/owlet/sleep_data.py#L205-L270) resolves a profile if absent, refreshes Firebase credentials again, requests the last four hours of sleep data, and returns the final bodyPositions element decoded. World uses `https://sleep-data.owletdata.com`; all other regions use `https://sleep-data.eu.owletdata.com`. The configured flow restricts regions to world/europe, so that binary mapping matches the current config choices. The request sends epoch-second start/end, `timeZone`, profile device version, and `returnBodyPositions=true`; authorization is the raw ID token, unlike the Firestore Bearer header. This header difference is observed code, not a verified defect.

`positionTimes` is checked only for nonemptiness. No alignment, ordering, or age check occurs. No timestamp is attached to the entity. Empty results and handled HTTP failures return Python `None`, distinct from the explicit enum string `no_data`.

### Polling and entity behavior

[`coordinator.py:45–92`](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/custom_components/owlet/coordinator.py#L45-L92) retains the upstream property update/token persistence, then awaits `_async_update_body_position` within the same coordinator update. Version 2 exits immediately. Version 3 requires existing region/refresh data, chooses `sock.oem_model or sock.model or "SS3"`, resolves and caches a profile, and fetches position. The cache lives until coordinator recreation; no invalidation after reassigning a sock is implemented. Direct use of `sock.oem_model` assumes that external dependency exposes the attribute; dependency implementation was not inspected, so this is an assumption to verify, not a confirmed failure.

With a cached profile, each successful refresh adds one token POST and one sleep GET. At the unchanged five-second default, the nominal extra request rate is 24 requests/minute per v3 sock (60/5 × 2), excluding latency, retries, setup, and existing library requests. Initial successful resolution adds token + devices + services (and possibly serviceUsers). If resolution returns None, the fetch helper attempts resolution again in the same cycle. There is no independent interval or negative-cache/backoff. Charging does not skip cloud work.

[`sensor.py:124–134,222–256`](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/custom_components/owlet/sensor.py#L222-L256) creates `OwletBodyPositionSensor` for every version-3 sock, regardless of whether cloud position data is supported or returned. Unique ID is `<serial>-body_position`; device association stays the existing OwletBaseEntity association. It is enum-class with baby-changing-table icon and six options. It returns coordinator.body_position directly. Availability combines coordinator availability with not charging; absent charging property is treated as not charging. Unlike the generic upstream sensor, it uses `.get("charging")`.

[`const.py:13–35`](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/custom_components/owlet/const.py#L13-L35) maps codes: 0/3 → no_data; 1 → moving; 2 → undetected; 4/5 → on_back; 6–9 → on_side; everything else → tummy. The code contains no bounded valid range for tummy. The vendor semantics are asserted by this implementation; no vendor documentation or real captures were provided to establish them independently.

### Dependencies, configuration, schema and translation

[`manifest.json`](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/custom_components/owlet/manifest.json) keeps exactly `pyowletapi==2025.4.1`, domain `owlet`, name, config flow, and cloud_polling. Changes owner/docs/issues, adds `integration_type: hub`, and moves version from upstream 2025.4.3 to 2026.8.1 (via transient missing version and 1.0.0).

There is no new declared pip dependency. New imports use aiohttp, the existing library's REGION_INFO, and standard-library dataclass/datetime/zoneinfo. No configuration fields, options schema, services, switches, binary sensors, or config-entry version change. Existing `config_flow.py` VERSION remains 1 and polling minimum/default remain five seconds. No migration function is added.

`strings.json`, `translations/en.json`, `translations/fr.json`, and `translations/uk.json` add the bodyposition label/states and no_devices error label. English strings correct reauthentication/occurred spelling; strings.json replaces common translation references with literal English password/connection text. The `uk.json` additions are English, not Ukrainian translations. Other locales receive no fork-specific body-position strings. Importantly, no_devices was already emitted by upstream's flow; this supplies missing labels rather than new error handling.

### Packaging, CI and documentation

[`hacs.json`](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/hacs.json) retains minimum HACS 1.32.1 and HA 2024.1; removes zip_release/filename and enables README rendering. Do not assume the new ZIP is the HACS download source: the metadata no longer opts into the prior ZIP mode. Exact current HACS installer implementation was not inspected.

[`release.yml`](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/.github/workflows/release.yml#L1-L26) triggers on every pushed tag, checks out v4, zips contents of custom_components/owlet at archive root excluding pycache, and publishes owlet.zip with generated release notes via softprops/action-gh-release@v2 and contents:write. It neither checks tag/manifest agreement nor runs tests/validation first. It creates a release artifact; it does not bump versions itself.

[`validate.yaml`](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/.github/workflows/validate.yaml#L1-L19) runs HACS validation on push, PR, daily and manual dispatch with empty permissions. Deleted upstream cron.yml had both HACS and hassfest jobs. Thus manual dispatch is gained but hassfest validation is lost. Neither current workflow runs the Python test suite.

README/info.md redirect badges and project links, add donation support and describe the maintained fork; `.github/FUNDING.yml` configures buy_me_a_coffee and custom links. `custom_components/owlet/brand/icon.png` is a new 20,141-byte binary branding artifact. No runtime image consumer was added. CHANGELOG.md is unchanged despite the feature/version change.

## Potential bugs and concrete fixes

Severity describes impact if the stated scenario occurs, not proof that a particular household already experiences it.

| Severity | Scenario and evidence | Suggested fix |
|---|---|---|
| High: misleading state | Last position is old, but still within the four-hour result; sensor publishes it as current. sleep_data.py:262–270 checks only nonempty times and blindly takes positions[-1]. This can mislead position-based automations. | Parse paired timestamps, select newest valid sample, expose observation time, enforce an explicit freshness threshold, return unknown/unavailable when stale. |
| High: wrong baby | Missing service mapping on an account with multiple babies: fallback selects first account-wide serviceUsers row, limit 1 (169–196), without proving DSN association. Cached context then persists (coordinator:76–83). | Require an unambiguous device/profile relationship; reject ambiguous fallback and invalidate cached mapping on reassignment/errors. |
| Medium: invalid codes become tummy | Negative/unknown/new vendor code falls through const.py:35. Local decoder execution confirmed -1 and 99 both yield tummy. | Enumerate verified tummy codes; unknown/out-of-range codes should be unknown/no_data with diagnostic logging. |
| Medium: platform-dependent update failure | ZoneInfo("localtime") at sleep_data.py:230 is not portable and is outside error handling. Local execution raised ZoneInfoNotFoundError. Even where available, key is "localtime", which is sent verbatim rather than a configured IANA zone. Whether server accepts it is unverified. | Use HA's configured time zone via explicit parameter; handle unavailable zone data. |
| Medium: extra feature blocks existing sensors | Every v3 primary update awaits all new requests (coordinator:54,76–92); no dedicated timeout or isolated coordinator exists. Slow service can delay the whole device refresh; uncaught schema/zone errors can fail an otherwise successful property refresh. | Give historical data its own throttled update path, bounded request timeout, and boundary validation; preserve primary telemetry on optional-feature failure. |
| Medium: excessive repeated cloud calls | ID token renewed every poll; failed resolution repeats twice per cycle. Coordinator:76–92 plus fetch:215–223 establishes duplicate resolution and no caching of auth/failure. | Cache ID token until expiry, use a separate slower historical interval, negative-cache unresolved profiles and apply retry backoff. |
| Medium: malformed responses fail updates | Missing token keys (56–57), missing document name (136/196), nonnumeric final position (270), or unexpected containers can raise KeyError/ValueError/TypeError/AttributeError; only aiohttp.ClientError is handled. | Validate response objects and codes at the API boundary and return a feature-specific unavailable state with diagnostics. |
| Low: tests disagree with charging behavior | New test expects charging body-position state unknown, but entity explicitly returns available=False while charging; normal HA rendering should be unavailable. Test is not proof of correct semantics. | Run actual HA/custom-component tests and assert the intended unavailable state. |

Inherited issues should not be credited to the fork: for example coordinator auth exception refers to CONF_EMAIL whereas the flow stores CONF_USERNAME; that expression is present upstream too. No evidence was gathered that the fork fixes inherited library authentication, oxygen, or device-support problems.

## Backward compatibility and migration

Existing entries, devices, entity unique IDs, and options are unchanged, so there is no source-level requirement to delete/re-add the integration. The new entity gets a new unique ID and should be additive for v3 devices. Version-2 polling bypasses the new feature. Existing v3 entities nevertheless inherit the expanded coordinator failure/latency surface, so this is not behaviorally isolated just because their definitions are unchanged.

The namespace remains owlet: installing this over another owlet custom component replaces that implementation; it is not a second integration domain. Keep account data/registries intact when switching forks. No registry or data migration is supplied. Intermediate historical manifest versions were missing or 1.0.0, so do not use version history alone to infer feature ordering or installation validity. Minimum HA metadata was not advanced or verified against the new standard-library/runtime assumptions.

## Tests and verification limits

Existing suites cover config flow, coordinator, setup, binary sensors and sensors with JSON fixtures. Fork changes tests/__init__.py to mock profile resolution as None and position fetching as on_back, increments total entity expectation 18 → 19, increments enabled sensor expectation 8 → 9, and checks body position on asleep/awake/charging scenarios. Version-2 tests remain present. See [test helper](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/tests/__init__.py#L40-L70) and [sensor tests](https://github.com/WilliamsJChris/owlet/blob/6de3bc276c445f9f0c7cd11d5a89ff811d1aa9be/tests/test_sensor.py).

Tests import/patch homeassistant.components.owlet, while shipped code resides under custom_components/owlet. This inherited layout requires an appropriate HA development harness or adaptation; this repository has no conftest.py, dependency manifest or local test-runner configuration to establish that harness. New mocks bypass the entire real Firebase/Firestore/sleep-data path, so entity count assertions do not validate profile matching, body-position codes, timestamp handling, regions, response failures, token handling, or HTTP behavior. No tests for sleep_data.py or decoder were added.

Performed locally: parsed all integration Python modules with ast.parse and all integration JSON files with json.loads successfully; executed const.py decoder directly and demonstrated fallback codes; probed ZoneInfo("localtime") and observed ZoneInfoNotFoundError on this machine. Did not run full HA tests, hassfest/HACS validation, install dependencies, authenticate with Owlet, inspect dependency internals, or exercise devices. These checks establish syntax/JSON validity and specific isolated behavior only.

## Candidates for mLupine

1. Port the body-position concept and enum entity shape if historical position is useful. Reimplement acquisition with explicit identity, timestamp/freshness, response validation, token caching and an isolated polling cadence before enabling it. The final combined commit should not be blindly cherry-picked because it bundles funding/ownership/CI regressions.
2. Port missing no_devices labels and English typo corrections selectively. Supply real translations rather than copying English into uk.json.
3. Port the release ZIP workflow pattern with explicit version/tag validation and test/validation gates, while making HACS metadata match the intended delivery mode.
4. Consider integration_type hub and branding only if they fit mLupine's packaging and current HA/HACS requirements. Keep mLupine ownership/documentation; do not port donor links or remove hassfest.

The useful contribution is the additional cloud data route and entity model. The current implementation does not establish that the result is recent, belongs to the intended baby under ambiguous mapping, or safely survives optional API failures. Those are the main porting gates.
