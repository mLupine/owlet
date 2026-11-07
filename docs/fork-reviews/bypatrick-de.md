# bypatrick-de/owlet main versus ryanbdclark/owlet main

Reviewed live on 2026-11-07. This is an independent source/history review, with existing CI results checked separately. No shared checkout files, refs, remotes, devices, or HA installations were changed.

## Practical result

This is a small modernization fork, not an expanded sensor integration. It updates the API dependency, repairs authentication error handling, adopts the newer Home Assistant options-flow pattern, makes interval changes affect existing coordinators, fixes HACS packaging assumptions, and supplies local branding. Sensor calculations, supported sock generations, device identifiers, entity unique IDs, switch commands, and regional choices are unchanged in the integration source.

The most useful fixes are the removal of a real `CONF_EMAIL` KeyError in the poll authentication-failure path, defaulting missing scan intervals to five seconds, and registering an options update listener. The dependency update could have additional behavioral effects, but this review did not inspect pyowletapi internals and does not attribute specific cloud protocol improvements to it.

## Exact comparison

| Item | Value |
|---|---|
| Upstream | `ryanbdclark/owlet`, branch `main` |
| Upstream SHA | `f8e0067a1e74a523b0bb4b0841b25404a6926ca8` |
| Fork | `bypatrick-de/owlet`, default branch `main` |
| Fork SHA | `86018c6d993da700508ed99e3b6c0410d6dba061` |
| Merge base | `f8e0067a1e74a523b0bb4b0841b25404a6926ca8` |
| GitHub compare status | ahead; 6 ahead, 0 behind |
| Net change | 27 files, 414 insertions, 307 deletions, including four binary images |

[Branch comparison](https://github.com/ryanbdclark/owlet/compare/main...bypatrick-de:main). [Immutable upstream-to-fork comparison](https://github.com/ryanbdclark/owlet/compare/f8e0067a1e74a523b0bb4b0841b25404a6926ca8...86018c6d993da700508ed99e3b6c0410d6dba061). GitHub API comparison and independently fetched git ancestry agreed. The six commits include two merges: counting them as six independent features would be misleading.

## Implementation by feature

### Authentication and setup errors

The dependency changes from `pyowletapi==2025.4.1` to `pyowletapi==2025.4.10`; the integration version changes from `2025.4.3` to `2026.10.0b1`: [custom_components/owlet/manifest.json:1-15](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/manifest.json#L1-L15).

`async_setup_entry` replaces imports/catching of `OwletEmailError` and `OwletPasswordError` with `OwletCredentialsError`, retaining `OwletAuthenticationError`. Those exceptions now raise `ConfigEntryAuthFailed`; connection failures still raise `ConfigEntryNotReady`; device-discovery failures still return false. API construction and stored-token merging are otherwise unchanged: [custom_components/owlet/__init__.py:9-15](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/__init__.py#L9-L15), [custom_components/owlet/__init__.py:38-74](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/__init__.py#L38-L74). The beta notes say the older exception classes were removed from the newer dependency; successful CI imports support compatibility with the selected dependency, but this is not a dependency source audit.

`OwletConfigFlow.async_step_user` changes wrong email/password handling from separate username/password field errors to a shared `base: invalid_credentials` error for either credentials or authentication exceptions. It explicitly maps `OwletConnectionError` to `base: cannot_connect`, instead of the broad unexpected-error handler. Existing `OwletDevicesError -> no_devices` handling gains a corresponding English string. Input schema, username-based duplicate detection, authentication validation, and stored data remain the same: [custom_components/owlet/config_flow.py:33-89](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/config_flow.py#L33-L89).

`async_step_reauth_confirm` receives the same credentials/authentication and connection mappings; its broad catch now also sets `base: unknown`, whereas upstream logged unexpected failures and redisplayed without an error. It still authenticates using stored region/username plus the submitted password, merges returned tokens, reloads the entry, and aborts as successful. It does not add a region-edit or username-edit migration: [custom_components/owlet/config_flow.py:101-148](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/config_flow.py#L101-L148).

`OwletCoordinator._async_update_data` previously attempted to interpolate `self.config_entry.data[CONF_EMAIL]` while handling an authentication exception, although entries use `CONF_USERNAME`. That could replace the intended authentication failure with `KeyError`. The fork removes that lookup and raises `ConfigEntryAuthFailed("Owlet authentication expired; please sign in again")`. Polling and token persistence are otherwise unchanged: [custom_components/owlet/coordinator.py:40-54](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/coordinator.py#L40-L54); compare [custom_components/owlet/coordinator.py:40-55](https://github.com/ryanbdclark/owlet/blob/f8e0067a1e74a523b0bb4b0841b25404a6926ca8/custom_components/owlet/coordinator.py#L40-L55).

### Options and polling

`async_get_options_flow` now constructs `OptionsFlowHandler()` without passing the entry. The handler's constructor assigning `self.config_entry` is removed; it uses the entry supplied by Home Assistant. Missing options default to `POLLING_INTERVAL` both in the form and setup: [custom_components/owlet/config_flow.py:95-99](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/config_flow.py#L95-L99), [custom_components/owlet/config_flow.py:152-171](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/config_flow.py#L152-L171), [custom_components/owlet/__init__.py:76-95](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/__init__.py#L76-L95).

Upstream passed `None` to the coordinator when a stored entry lacked `scan_interval`, reaching `timedelta(seconds=None)`; the new fallback avoids that failure. The default itself was already five seconds upstream. The form already enforced integer coercion and minimum five; the fork does not lower a ten-second enforcement limit. The previous English label saying minimum ten was simply wrong.

The new `async_update_options` listener builds a `timedelta` from current options and assigns it to every device coordinator under the config entry. Registration uses `entry.async_on_unload(entry.add_update_listener(...))`, so HA can remove it on unload. It does not reload platforms or explicitly call authentication, preserving running entities and the shared API session: [custom_components/owlet/__init__.py:95-110](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/__init__.py#L95-L110). It does not explicitly request an immediate poll; exact next-poll scheduling belongs to HA's coordinator implementation and was not independently audited here.

### UI text

`strings.json` and `translations/en.json` add `no_devices: No supported Owlet devices found` and replace the options label key `pollinterval` with `scan_interval`, matching `CONF_SCAN_INTERVAL`. Label text becomes `Polling interval in seconds (minimum 5)`. Most of the large English translation diff is indentation normalization, not changed entity names. Existing unused invalid-email/password messages remain. No other language translation file changes. See [custom_components/owlet/strings.json:17-42](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/strings.json#L17-L42), [custom_components/owlet/translations/en.json:1-30](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/translations/en.json#L1-L30).

### HACS, versions, and assets

`hacs.json` raises the declared HA minimum from `2024.1` to `2024.12.0`; HACS minimum remains `1.32.1`. It removes `zip_release: true` and `filename: owlet.zip`, eliminating the explicit requirement for a separately uploaded release ZIP. This is packaging metadata, not a change to the integration domain or installation directory: [hacs.json:1-5](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/hacs.json#L1-L5).

The branding change adds `brand/icon.png`, `icon@2x.png`, `logo.png`, and `logo@2x.png`, plus provenance in [custom_components/owlet/brand/SOURCE.txt:1-8](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/brand/SOURCE.txt#L1-L8). That file states the images were copied unchanged from `home-assistant/brands` commit `3f75f91202d6e0f94c9cdae55c6fa776ae838672`, `custom_integrations/owlet`, and that central custom-integration branding was removed on 2026-10-20. These are repository provenance claims, not an independent audit of the external brands history. No Python logic loads the assets.

The manifest still points documentation/issues to upstream. `BETA-HINWEISE.txt` adds German development, installation, backup, rollback, and validation notes. Some outstanding items are stale relative to later commits: it still says to create a fork and prepare `owlet.zip`, despite this being a fork and the ZIP requirement having been removed. It accurately discloses mock-only testing and missing live login/device checks: [BETA-HINWEISE.txt:1-36](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/BETA-HINWEISE.txt#L1-L36).

## Complete unique-commit inventory

- [`7aa4cf290e04c379b4373e4a127675fdb966fd77`](https://github.com/bypatrick-de/owlet/commit/7aa4cf290e04c379b4373e4a127675fdb966fd77) — Modernize Owlet authentication and options for Home Assistant 2026. Main implementation: dependency and beta version bump; exception migration and auth-error fix; current options-flow construction, missing-interval fallback, live interval listener; English labels; HA minimum; custom-integration test repairs, three added tests, pytest configuration, CI workflow, and beta notes. All substantive code changes remain at head.

- [`bb3851a9bf26c92df78d5ae705461ce6a53454c3`](https://github.com/bypatrick-de/owlet/commit/bb3851a9bf26c92df78d5ae705461ce6a53454c3) — Fix pip cache dependency path for integration tests. Adds `cache-dependency-path: requirements-test.txt` to setup-python so pip caching looks at the actual test requirements file. Remains at head; no integration runtime effect.

- [`16374f1c846e8189da6ceb1dcc29328cec1df634`](https://github.com/bypatrick-de/owlet/commit/16374f1c846e8189da6ceb1dcc29328cec1df634) — Fix HACS downloads for fork without release ZIP assets. Removes `zip_release` and `filename` from HACS configuration, so this fork no longer advertises a required owlet.zip release asset. Remains at head; supersedes the inherited packaging assumption and leaves the beta ZIP TODO stale.

- [`dac3bcc9caa63e33bb6994a991ca7135273a38f6`](https://github.com/bypatrick-de/owlet/commit/dac3bcc9caa63e33bb6994a991ca7135273a38f6) — Merge pull request #1 from bypatrick-de/codex/modernize-owlet. Merge of PR #1, modernize-owlet. Incorporates the preceding implementation/cache/HACS commits; does not add a separate feature or extra merge-resolution change.

- [`53de2d9dc9fc9dcf9100fefb1a4ca236f6914e74`](https://github.com/bypatrick-de/owlet/commit/53de2d9dc9fc9dcf9100fefb1a4ca236f6914e74) — Bundle original Owlet brand images for HACS validation. Adds four local brand images and SOURCE.txt provenance. Remains at head; no integration Python behavior change.

- [`86018c6d993da700508ed99e3b6c0410d6dba061`](https://github.com/bypatrick-de/owlet/commit/86018c6d993da700508ed99e3b6c0410d6dba061) — Merge pull request #2 from bypatrick-de/fix/local-brand-assets. Merge of PR #2, local-brand-assets. Incorporates the brand commit; no separate feature or extra merge-resolution change.

There are no unique revert commits or version-only commits. The version bump is bundled with the modernization commit. No introduced runtime feature was subsequently reverted. Both merges incorporate changes already enumerated above.

## Entity and configuration compatibility

The integration domain stays `owlet`; config-flow version stays 1. There is no `async_migrate_entry` addition. Stored keys remain region, username, token/expiry/refresh, plus the `scan_interval` option. Password is submitted during login/reauthentication but is not newly persisted. Region choices remain `europe` and `world`; supported versions remain `[2, 3]`: [custom_components/owlet/config_flow.py:33-46](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/config_flow.py#L33-L46), [custom_components/owlet/const.py:3-11](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/const.py#L3-L11).

No production changes exist in `sensor.py`, `binary_sensor.py`, `switch.py`, `entity.py`, or `const.py`. Existing entity unique IDs remain serial-plus-property. Existing device name `Owlet Sock <serial>`, charging availability rules, sleep mappings, oxygen averaging exposure, and base-station switch predate this fork. The test changes from 18 to 19 registry entities, from an old device name to the serial-based name, and from `unknown` to `unavailable` while charging do not represent newly implemented entity behavior. They align tests with the existing integration and selected HA environment: [tests/test_init.py:28-49](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/tests/test_init.py#L28-L49), [custom_components/owlet/entity.py:25-38](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/entity.py#L25-L38), [custom_components/owlet/sensor.py:148-160](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/sensor.py#L148-L160).

Existing installations with well-formed entries should not require entity recreation or a data migration on the source evidence. Entries without the option now have a recovery path. Entries containing an explicit null or invalid interval are not repaired by `dict.get`'s default, which applies only when the key is absent. HACS now excludes declared support for HA before 2024.12.0; that older minimum is not covered by the test matrix. The newer dependency may impose additional compatibility constraints outside the reviewed integration source.

## Tests and evidence limits

The fork adds `pytest-homeassistant-custom-component==0.13.373` and the matching API pin to `requirements-test.txt`, uses automatic asyncio mode/function fixture loop scope, and enables custom integrations through an autouse fixture. Imports and mock patch targets move from nonexistent/inappropriate `homeassistant.components.owlet` paths to `custom_components.owlet`; fixture helpers move from HA-core `tests.common` to the custom-component harness. See [requirements-test.txt:1-2](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/requirements-test.txt#L1-L2), [pytest.ini:1-4](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/pytest.ini#L1-L4), [tests/conftest.py:1-7](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/tests/conftest.py#L1-L7), [tests/__init__.py:21-69](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/tests/__init__.py#L21-L69).

Four JSON fixtures remove `tokens: ""`. That key was not a token mapping and could reach mapping unpacking in production code; removing it models absence of refreshed tokens instead. It does not change production token-handling behavior. Positive token handling remains represented by existing setup tests, but malformed token shapes are not validated by the integration.

The three added test functions cover setup with absent interval, interval updates without an authentication call, and initial-login connection errors. Existing tests are repaired for the new exception type, custom-component load path, naming and charging availability. The coordinator authentication test now expects SETUP_ERROR rather than SETUP_RETRY, consistent with the intended authentication exception instead of the former accidental KeyError. Two separately named wrong-email/password tests now both inject the same credentials exception; their names overstate distinct coverage.

The workflow uses Python 3.14, installs the pinned requirements, and runs `python -m pytest -q`: [.github/workflows/tests.yaml:1-16](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/.github/workflows/tests.yaml#L1-L16). Live GitHub API metadata reports successful [Integration tests at the exact head](https://github.com/bypatrick-de/owlet/actions/runs/40943596435). Downloaded logs explicitly show **30 passed in 1.21s**, Python **3.14.9**, HA **2026.10.2**, and pyowletapi **2025.4.10**. [Hassfest at the same head](https://github.com/bypatrick-de/owlet/actions/runs/42343873113) also reports success. These are existing remote results, not tests rerun by this review. Local `git diff --check` passed.

No live account login, EU/world endpoint checks, real token refresh, multi-sock concurrency, elapsed-time polling test, long-running freshness test, minimum-HA-version test, or physical switch-command validation was performed. There is no dedicated switch test module in this fork. Dependency internals and HA coordinator internals were not reviewed. CI success proves the mocked suite passed in that environment; it does not establish current cloud acceptance.

## Concrete risks and potential bugs

### Medium: inherited stale cloud data remains indistinguishable from fresh values

Scenario: the cloud repeatedly returns a successful response containing old property values. `_async_update_data` accepts the update without comparing source timestamps or marking stale data unavailable; entity availability checks coordinator success/charging. A dashboard can therefore continue displaying old readings as available. This behavior is inherited, not introduced by the six commits, and the beta notes explicitly leave freshness testing open. Evidence: [custom_components/owlet/coordinator.py:40-54](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/coordinator.py#L40-L54), [custom_components/owlet/sensor.py:148-160](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/sensor.py#L148-L160), [BETA-HINWEISE.txt:29-33](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/BETA-HINWEISE.txt#L29-L33). A concrete improvement is to retain source timestamps and expose staleness separately after establishing the dependency's timestamp semantics.

### Medium, conditional: credentials exceptions during polling may miss the reauth path

Setup and config flow now recognize both `OwletCredentialsError` and `OwletAuthenticationError`, but `_async_update_data` only maps the latter to `ConfigEntryAuthFailed`. If the upgraded dependency raises a credentials error from `Sock.update_properties` for an invalid refresh credential, it can take the generic OwletError/UpdateFailed path rather than launching reauthentication, depending on exception inheritance. This is a concrete catch-set mismatch, but the actual dependency emission/inheritance was not inspected, so it is a risk requiring verification rather than a confirmed live bug. Evidence: [custom_components/owlet/__init__.py:50-65](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/__init__.py#L50-L65), [custom_components/owlet/coordinator.py:43-54](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/coordinator.py#L43-L54). Inspect the pinned package and add separate poll-time credentials/authentication tests before normalizing the handlers.

### Low: missing-option recovery does not repair explicit malformed values

Scenario: a legacy/manual entry stores `scan_interval: null`; setup still calls `timedelta(seconds=None)`. The same problem affects the listener for a bad option update. The form prevents normal users submitting such values, so this is boundary hardening rather than a common regression. Evidence: [custom_components/owlet/__init__.py:76-80](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/__init__.py#L76-L80), [custom_components/owlet/__init__.py:100-104](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/__init__.py#L100-L104). Validate persisted values before using them if malformed-entry recovery is an intended requirement.

### Low: support links and beta instructions point at the wrong operational state

Fork users following the unchanged manifest issue tracker land at upstream, while beta notes still request fork creation and a ZIP which HACS metadata no longer requires. This can misdirect troubleshooting and installation expectations. Evidence: [custom_components/owlet/manifest.json:1-15](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/custom_components/owlet/manifest.json#L1-L15), [BETA-HINWEISE.txt:29-34](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/BETA-HINWEISE.txt#L29-L34), [hacs.json:1-5](https://github.com/bypatrick-de/owlet/blob/86018c6d993da700508ed99e3b6c0410d6dba061/hacs.json#L1-L5). Update ownership URLs and installation notes for the actual release process.

No confirmed high-severity defect introduced by this diff was established. The minimum-version declaration and exact interval scheduling remain unverified compatibility claims; absence of dedicated coverage is not itself proof of a runtime bug.

## Candidates for mLupine

1. Port the coordinator authentication-message fix: small, directly addresses an obvious wrong-key exception, and preserves identifiers/data.
2. Port absent-interval defaults, current options-flow construction, listener registration and unload cleanup together. Strengthen with elapsed-time scheduling and multiple-coordinator tests instead of asserting only the assigned property.
3. Consider the API pin and exception updates as one compatibility change. First inspect the dependency delta and its poll-time exception contract; do not claim this fork proves token refresh or EU login works.
4. Reuse the custom-component test harness/CI structure and corrected English schema key. Keep existing behavior assertions, add real error-path distinctions, and add switch and minimum-version coverage where mLupine needs it.
5. Reuse local assets/provenance and archive-based HACS metadata only if they match mLupine's release mechanism. Do not copy another fork's beta version or stale ownership/install notes wholesale.

This report does not compare mLupine's current code, so these are candidates to reconcile with that branch, not claims that mLupine lacks them.
