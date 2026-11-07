# Rogash1/owlet independent fork review

Reviewed 2026-11-07 using live GitHub REST metadata and a separate temporary clone. No shared project files, checkout, remotes or refs were modified. No devices or accounts were accessed.

## Exact comparison

- Fork default branch: `maintenance/local-candidate`, head `36373a3bd29758a52f5f0f2f00e58163192342fb`.
- Upstream branch: `ryanbdclark/owlet:main`, head `f8e0067a1e74a523b0bb4b0841b25404a6926ca8`.
- GitHub comparison and independent git ancestry agree: **11 ahead, 0 behind**. Upstream head is the fork's ancestor. All 11 unique commits are single-parent commits: no merges and no explicit revert commits.
- [Requested branch comparison](https://github.com/ryanbdclark/owlet/compare/main...Rogash1:maintenance/local-candidate).
- [Immutable SHA comparison](https://github.com/ryanbdclark/owlet/compare/f8e0067a1e74a523b0bb4b0841b25404a6926ca8...36373a3bd29758a52f5f0f2f00e58163192342fb).
- Overall tree delta: 36 files, 1,226 insertions, 462 deletions, including moved historical tests and two binary icons. This is not a correctness metric.

## Practical behavior first

This is a maintenance consolidation fork with a companion API-library fork, an entry-schema migration and meaningful regression tests. It is not a new integration architecture. Most HA runtime changes arrive in one large initial commit. Subsequent commits mainly improve packaging, migration evidence, documentation and CI.

1. New accounts can coexist across `world` and `europe`, with account identity normalized as `region_email`. Existing entries migrate in place to schema version 2. Existing entity/device IDs deliberately remain unqualified; newly added entries get region-qualified IDs.
2. V3 measurements become unavailable when their cloud snapshot timestamp is missing, malformed, naive, future-dated or older than `max(120 seconds, 3 polling intervals)`. Equal numeric readings are not treated as evidence of staleness. A new diagnostic timestamp entity remains visible for an old snapshot.
3. Missing properties no longer normally raise `KeyError`; values become `None` and entities become unavailable. Missing sleep state no longer means awake. Unknown numeric sleep states still have an inconsistency described below.
4. Modern HA options flow works without assigning the now framework-owned config-entry property. Poll interval changes reload the integration; absent intervals default to 5 seconds and the coordinator enforces a minimum of 5.
5. Auth failures trigger HA reauthentication with generic messages, connection/API failures trigger retry/update failure, and token snapshots are persisted even when setup or polling fails after rotation.
6. Installation moves from upstream's PyPI `pyowletapi==2025.4.1` to a hash-pinned GitHub wheel from Rogash1's companion repository. This changes the trust and availability dependency; the integration diff alone does not establish what the new parser or HTTP code does.
7. HACS minimum HA rises from 2024.1 to 2026.2.3, source installs replace named ZIP-release installs, and metadata/support links point to Rogash1. Head bundles local Owlet icons without a further version bump.

Multi-device support, V2/V3 support, the existing sensor list, and the base-station switch already exist upstream. The fork tests multi-device behavior but should not receive credit for inventing it. Camera, recovery/body-position entities and alarm acknowledgment are not added.

## Feature implementation and evidence

All fork source links below use the exact reviewed head.

### Account schema and identity

[`config_flow.py:33-90`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/config_flow.py#L33-L90): input remains region, username and password. `OwletConfigFlow.VERSION` changes 1→2. `async_step_user` calls `async_set_unique_id` with region plus stripped/lowercase email, authenticates, fetches devices rather than calling old `validate_authentication`, and snapshots `owlet_api.tokens`. Saved data adds `entity_namespace` equal to region, while retaining original username spelling and tokens. Password is not saved; that omission already existed upstream.

[`__init__.py:37-52`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/__init__.py#L37-L52): `async_migrate_entry` rejects future major versions, returns immediately for version 2, validates legacy region and nonblank string username, checks normalized unique-ID collisions against other Owlet entries, then updates only config-entry unique ID/version. It leaves entry data/options and registry identities alone. Refusing a collision avoids silently merging accounts but leaves the affected entry unable to load until the collision is resolved.

[`entity.py:27-34,58-69`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/entity.py#L27-L69): `device_identifier` uses `entity_namespace_serial` when the marker exists, otherwise raw serial. `entity_unique_id(key)` appends `-key`. Sensor, binary-sensor and switch constructors all use this helper. Device-registry identifiers use the same derived identity. The marker is intentionally not backfilled during migration, preserving existing registry matches and user-assigned entity IDs.

Device metadata also stops inventing hardware revision `3r8`; it uses stringified `sock.revision` or `None`. MAC connections are omitted for falsey MAC values instead of providing an `unknown` fallback. Model and software version remain optional. Device names and suggested nursery area remain upstream behavior.

### Authentication, lifecycle and polling

[`__init__.py:55-124`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/__init__.py#L55-L124): setup still constructs one API object, fetches supported versions `[2,3]`, builds per-device coordinators, refreshes them concurrently and forwards all three platforms. New exception handling uses maintained API exception classes: authentication→`ConfigEntryAuthFailed`, connection/general API errors→`ConfigEntryNotReady`, no devices→false. A `finally` block writes changed API token snapshots even after errors. Existing result-dictionary token handling remains too.

[`coordinator.py:24-55`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/coordinator.py#L24-L55): polling now has `max(5, interval or POLLING_INTERVAL)`, passes `config_entry` to HA's coordinator, ignores the old update return payload and reads `sock.api.tokens` in `finally`. It fixes upstream's auth failure path that indexed `CONF_EMAIL` despite storing `CONF_USERNAME`. It wraps API failures with generic strings instead of exposing raw exception content. This assumes the maintained library exports compatible exception hierarchy and token snapshot semantics; those internals were not inspected.

[`config_flow.py:103-173`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/config_flow.py#L103-L173): reauth renders `invalid_credentials`, `cannot_connect` or `unknown` errors, updates returned tokens and reloads the entry. Options flow instantiation no longer accepts/assigns a config entry manually. Options UI still accepts integers ≥5. Setup registers an unload-scoped update listener that unconditionally reloads on any entry change; this has a token-rotation defect below.

### Freshness, missing data and entities

[`entity.py:36-55`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/entity.py#L36-L55): base availability first requires coordinator success. For V3 only, freshness applies to heart rate, instantaneous/averaged oxygen, sleep, skin temperature, movement/bucket, battery minutes/percentage, charging and base-station state. It parses ISO `last_updated`, requires timezone information, computes age against UTC and accepts ages from zero through the threshold. V2, signal strength, alert/disconnection/off keys and timestamp itself bypass this freshness check. The threshold is a local policy, not an Owlet SLA.

[`sensor.py:119-165,186-246`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/sensor.py#L119-L246): the eight ordinary descriptions retain units/classes and movement defaults. Setup still creates ordinary/sleep/average entities only for keys present during initial setup, and now always adds `OwletLastUpdatedSensor` for V3. That new sensor has timestamp device class, diagnostic category and charging availability. Its `native_value` parses an aware datetime or returns `None`. It is exempt from age gating, but still requires successful coordinator and a non-None source key. On total polling failure it is unavailable too.

All ordinary sensor, binary-sensor and switch getters use `.get`. Availability requires a non-None property and either exact `charging is False` or the description's charging exemption. Missing charging therefore cannot be mistaken for not charging. Exact identity comparison assumes the dependency returns Python booleans, not integer zero. The upstream oxygen-average 0–100 validity guard remains; it is not new.

`OwletSleepSensor.native_value` now falls back to `unknown` for unmapped codes. [`OwletAwakeSensor.is_on`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/binary_sensor.py#L149-L170) returns None for missing state but otherwise still treats every code except 8/15 as awake.

[`switch.py:75-94`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/switch.py#L75-L94): only availability/getter/identity changes. Explicit on/off commands still call `Sock.control_base_station`; no new control protocol or automatic alarm acknowledgments are present.

### Diagnostics, translations, distribution and tooling

[`diagnostics.py:1-18`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/diagnostics.py#L1-L18) adds an allowlisted config-entry diagnostic result: entry version plus per-device generation, polling success, poll seconds and whether the timestamp key exists. It deliberately omits accounts, tokens, serials, MACs and measurements. Key presence is not proof of valid timestamp.

`strings.json`/English translations remove separate invalid-email/password errors, add no-devices, fix reauthentication/occurred typos and name the timestamp sensor. French/Ukrainian gain no-devices and lose obsolete auth keys; French/Ukrainian do not gain timestamp translations. Ukrainian remains largely English. Existing polling-label mismatch remains: English says minimum 10 while validation accepts 5.

[`manifest.json`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/custom_components/owlet/manifest.json) sets version `2026.9.20rc2`, Rogash1 ownership/docs/issues and direct requirement `pyowletapi@https://github.com/Rogash1/pyowletapi/releases/download/2026.9.20rc2/pyowletapi-2026.9.20rc2-py3-none-any.whl#sha256=c6f03ad0e50a943b1077b7275317da41ac89ae9f739a4d599abecabbee94fc7d`. Domain `owlet`, cloud-polling class and config-flow flag remain unchanged. The manifest does not include API source. Claims about HTTP retries, authentication hardening, parsing and timestamps in that wheel require separate review.

[`hacs.json`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/hacs.json) retains HACS 1.32.1, raises HA minimum to 2026.2.3, sets `zip_release:false` and removes `filename:owlet.zip`. GitHub asset access is now necessary for dependency installation. Hash pinning prevents silent wheel replacement but does not establish trust or availability.

[`scripts/build_release.py`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/scripts/build_release.py) validates metadata and creates a ZIP of git-tracked component files plus LICENSE/NOTICE/README/CHANGELOG/SECURITY, using sorted paths, fixed timestamps and permissions, then writes SHA256SUMS. It reads working-tree contents, so uncommitted edits to tracked files enter the archive; it does not prove a clean commit build. It neither publishes nor changes git. ZIP byte reproducibility across compression-library versions is not established.

[`scripts/validate_metadata.py`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/scripts/validate_metadata.py) enforces one whitespace-free direct wheel requirement, matching integration/dependency version and GitHub owner/path/hash shape, issue tracker/minimum HA and 256/512 PNG headers. Optional live check validates Issues enabled, nonempty topics and matching tracker URL. It checks hash syntax, not downloaded wheel bytes, and PNG headers, not full image integrity.

CI adds manual dispatch, read-only contents permissions, 15-minute job caps, pinned checkout/setup-python actions and disabled checkout credentials. HACS now checks out source first. Regression CI uses Python 3.14.6, pinned test lock, metadata validation, separate `--no-deps` wheel installation and offline pytest. Hassfest/HACS actions still use moving master/main refs. [`workflow`](https://github.com/Rogash1/owlet/blob/36373a3bd29758a52f5f0f2f00e58163192342fb/.github/workflows/cron.yml).

Documentation is rewritten around experimental maintenance, companion API, synthetic test scope, in-place migration and version-aware rollback; Apache LICENSE remains. NOTICE attributes adapted ideas to soschlegel, mLupine, gitcak, talmg, Jofeled, batas and bgunner1987. Those attributions are author statements, not independently verified equivalence with those forks. Security policy says best effort, no formal audit or guaranteed response. `.gitignore` replaces broad Python boilerplate with targeted environments/builds, private agent records, HA state/DBs, credentials, backups and archives. It cannot remove already tracked secrets. The final icon commit copies historical brand PNGs and records original brand-source SHA/trademark notice; provenance is documented, not independently image-matched here.

## Complete unique-commit inventory, oldest first

Each SHA is full and immutable. None is a merge. No explicit revert exists; superseded intermediate details are identified below.

| Commit | Title | Actual effect / current status |
|---|---|---|
| [81b84aaed1e12cf73b88766f3ef87cdc75eadd2c](https://github.com/Rogash1/owlet/commit/81b84aaed1e12cf73b88766f3ef87cdc75eadd2c) | Adapt maintained API, config lifecycle and timestamp-aware availability | Main runtime batch: maintained API rc1, schema migration, region account ID, options/reauth/error/token handling, polling fallback, freshness/missing-data logic, timestamp/diagnostics, metadata cleanup, translations, active maintenance tests and archived upstream harness. Initial dependency/version later superseded; functionality mostly survives. |
| [98478c6ef2e3510b2eb022c1f15c684e86382658](https://github.com/Rogash1/owlet/commit/98478c6ef2e3510b2eb022c1f15c684e86382658) | Align HACS metadata with tested local-only candidate | Raises HA baseline and switches HACS away from named ZIP-release mode; NOTICE annotation. No runtime algorithm change. |
| [414a0b79b42d7ce741ab56d50f53d411d7883d9e](https://github.com/Rogash1/owlet/commit/414a0b79b42d7ce741ab56d50f53d411d7883d9e) | Scope new entity IDs by region while retaining existing registry IDs | Adds marker for new entries, central ID helper and matching device identity, updates all three entity platforms and namespace tests. Preserves unmarked legacy identities. |
| [43ee2482528ac43e403c386fc6d9fc5564a08033](https://github.com/Rogash1/owlet/commit/43ee2482528ac43e403c386fc6d9fc5564a08033) | Check out integration source before HACS validation | Adds missing checkout step and attribution. Later expanded/reformatted by CI commit; the fix remains. |
| [4ed3b8a8148d258355d3bbbdd9eeafd024c94c43](https://github.com/Rogash1/owlet/commit/4ed3b8a8148d258355d3bbbdd9eeafd024c94c43) | Verify HA 2026.9.3 migration preserves registries and recorded history | Adds exact target test lock, recorder fixture ordering, migration test with renamed entity/real synthetic recorder rows through reloads and ignores local artifacts. No integration runtime change. |
| [210f0a1e4620afa1d089608b4228ab6d6159401f](https://github.com/Rogash1/owlet/commit/210f0a1e4620afa1d089608b4228ab6d6159401f) | Document maintained integration, security review and version-aware rollback | Rewrites README, adds maintenance changelog/security policy, updates attribution and manifest owner/docs/issues. No runtime code change. Much detailed prose later condensed; not evidence of a formal audit. |
| [e83f09f7ce0afcd5b4adebcde1c35ff53789bcb9](https://github.com/Rogash1/owlet/commit/e83f09f7ce0afcd5b4adebcde1c35ff53789bcb9) | Prepare hash-pinned GitHub wheel dependency and release validation | Replaces named rc1 requirement with direct rc1 wheel URL/hash, adds URL/version assertions and installation guidance. URL spacing and rc1 pin later superseded. No new release-build script in this commit despite broad title. |
| [7cda7f34691d935bdd5ffa539c73edea25f5747a](https://github.com/Rogash1/owlet/commit/7cda7f34691d935bdd5ffa539c73edea25f5747a) | Keep public project documentation and reproducible tooling; archive internal records | Condenses docs/security/notice, rewrites ignore policy and adds deterministic ZIP builder. Tracked diff does not demonstrate where private records were archived; no internal archive is shipped. No HA runtime change. |
| [55341cb0db1e9e993bdfe5e0e1caae0df875aae8](https://github.com/Rogash1/owlet/commit/55341cb0db1e9e993bdfe5e0e1caae0df875aae8) | Fix hassfest requirement formatting and validate integration metadata in CI | Removes requirement whitespace, adds metadata validator, modern pinned checkout/Python setup, metadata/HA regression CI and requirement-format test. Same rc1 wheel/hash at this point. |
| [3e024cb81d35cae5ac71e3368c5ff19ea2dbb92c](https://github.com/Rogash1/owlet/commit/3e024cb81d35cae5ac71e3368c5ff19ea2dbb92c) | Prepare 2026.9.20rc2 experimental prerelease | Integration version and wheel version/hash become rc2; README/changelog updated. Release/dependency-only, not a Python runtime diff. Dependency bytes differ; cannot label its external behavior unchanged without inspecting that wheel. |
| [36373a3bd29758a52f5f0f2f00e58163192342fb](https://github.com/Rogash1/owlet/commit/36373a3bd29758a52f5f0f2f00e58163192342fb) | Bundle existing Owlet icons after shared brand registry removal | Adds 256/512 icons, source/trademark attribution, PNG checks and build-time validation; docs/changelog update. Integration still reports rc2, so this head has post-rc2 unreleased content. |

Intermediate rc1 named requirement, whitespace-bearing direct requirement, old HACS ZIP filename/mode and verbose earlier maintenance records are no longer present. Those are superseded edits, not separate current capabilities. Historical upstream changelog remains below the new maintenance entries.

## Concrete defects and verification targets

### Medium: token persistence also triggers integration reload

The newly installed update listener at `__init__.py:118` calls unconditional `async_reload` at 122–124. Coordinator token rotation writes config-entry **data**, not options. HA Core 2026.9.3 invokes the same update listeners for changed data and options: independently inspected [`config_entries.py:2649-2682`](https://github.com/home-assistant/core/blob/2026.9.3/homeassistant/config_entries.py#L2649-L2682). Thus any changed token snapshot during ordinary polling schedules a full unload/reload. This is established framework behavior, not speculation about the dependency. Frequency depends on token rotation behavior, which was not inspected. It can interrupt entity availability/polling and multiply reloads with near-simultaneous changes. An endless loop is not established.

Fix: make the listener compare saved options with current options and reload only for option changes, or use a dedicated options update mechanism. Add a test that rotates tokens after a fully loaded setup and asserts zero reloads, followed by a real options change asserting one reload. Existing tests separately prove persistence and direct listener invocation; they miss their interaction.

### Medium: unknown sleep codes can still claim awake

`binary_sensor.py:169-170` excludes only 8/15. With fresh V3 data, `charging=False` and `sleep_state=0` or an unexpected code, the awake binary sensor is available and true, while `OwletSleepSensor` reports `unknown`. `const.py` explicitly defines 0 as unknown. The fork fixes missing-None behavior but leaves this inherited classification bug. Fix by explicitly mapping awake=1, asleep=8/15 and all unknown/unmapped values=None/unavailable. Test 0, 1, 8, 15 and an unmapped code.

### Medium, policy gap: stale alert flags remain available

Freshness key allowlist excludes all high/low/critical alert keys, `sock_disconnected` and `sock_off`. Binary descriptions allow charging and only require non-None values. Successful polling that repeatedly returns an old snapshot containing those flags can therefore leave stale alert on/off states available while vital measurements are unavailable. This is a concrete integration-policy asymmetry; whether the dependency returns independently fresh alerts or retained stale flags was not inspected. Fix by establishing per-property timestamp provenance and gating snapshot-derived flags, rather than indiscriminately assuming every flag shares the vitals timestamp. Add a stale-snapshot binary-sensor test.

### Low: future clock skew hides all freshness-gated readings

The lower bound `0 <= age` rejects even a timestamp slightly ahead of HA's clock. A future API timestamp or local NTP lag makes fresh data unavailable. This is explicit code behavior; no occurrence in real Owlet traffic is established. Consider bounded, documented skew tolerance and boundary tests.

### Low: region scoping is not complete device isolation

Device identifiers are region-scoped for new entries, but MAC connection identifiers remain global. Same reported MAC across regions can cause HA device-registry merging despite different identifier tuples. Likewise two different accounts in the same region exposing the same serial generate identical entity IDs. This may be correct for shared physical devices, but region/account isolation should not be advertised more broadly than implemented. Existing namespace test compares identifier tuples, not actual registry merging. Add realistic overlapping-account and duplicate-MAC registry tests before changing policy.

### Inherited limitation: entities are discovered only during initial setup

Ordinary/sleep/average entity creation depends on initial property-key presence (`sensor.py:119-132`, `binary_sensor.py:108-116`). If an initially absent field later appears, `.get` guards do not create a new entity until reload. This predates the fork but matters with a parser that may omit missing measurements. Determine the companion parser's property-presence contract before claiming complete recovery from missing data.

### Low: developer test suite loses legacy breadth

Archived tests are excluded from discovery, not repaired. New focused tests do not preserve every old sensor/binary-sensor assertion, V2 fixture scenario or switch behavior. This is explicitly documented and sensible as a temporary harness repair, but not evidence that all historical behavior remains validated.

## Compatibility and migration implications

- Upgrade in place to preserve registry IDs. Deleting/readding creates region-qualified IDs and can separate entities from historical identities. User-facing slug names can also receive suffixes on recreation.
- Schema version 2 prevents a simple safe downgrade to version-1 code. Restore a coherent pre-migration backup of HA config/registries and recorder database; restoring old files alone is insufficient. This is advice already documented by the fork, not a performed migration.
- Legacy raw-serial identities intentionally remain, including preexisting cross-account collision risks. Migration refuses malformed/colliding/future entries; it does not repair them.
- Existing users retain options; missing intervals now fall back safely. No new services, platform domains, sensor units, state classes or supported-generation list are introduced beyond timestamp diagnostic entity/category and availability semantics.
- Automations that previously consumed retained numeric values may now see `unavailable`; unknown and unavailable need deliberate handling. The timestamp diagnostic is useful for this, but also disappears on coordinator failure.
- New dependency is paired to maintained integration API expectations (`tokens`, `revision`, timestamp type, exception classes). Porting HA code while leaving an incompatible API version installed is unsafe. Old HA baselines supported by upstream are outside the fork's advertised compatibility.

## Tests and actual verification

Inspected complete net integration diff, surrounding HA integration sources, per-commit file inventories and manifest history; retained full diff/history in `/tmp/owlet-rogash1-XZkGBB/full.diff` and `commits.patch`. Temporary clone is `/tmp/owlet-rogash1-XZkGBB/repo`. Live GitHub branch SHA checks match cloned heads.

Locally ran `python3 scripts/validate_metadata.py`: **passed**. System Python was 3.9.6; did not install the 137-entry HA target environment or run pytest. This review therefore does not claim a local test-suite pass. No code was changed or live HA tested.

GitHub check-runs for exact fork head showed successful **Metadata and HA regressions**, **Hassfest validation**, **HACS Action**, including [run 42339218702](https://github.com/Rogash1/owlet/actions/runs/42339218702). That is observed CI status, not a fresh local execution. README reports 22 mocked tests on HA 2026.9.3/Python 3.14.6 and earlier 21 on HA 2026.2.3/Python 3.13.15; the second baseline statement was not independently rerun.

Active tests cover migration/idempotence/collision/future-invalid guards; auth/connection failure and token persistence; stale/missing readings; missing sleep; modern options; regional user flow; one/two-device setup/reload/unload using real Sock parser with synthetic responses; reauth success/errors; failure rotation; allowlisted diagnostics; dependency metadata; legacy/new namespace; and real synthetic recorder/registry continuity through reloads with a user-renamed entity. Recorder fixture initialization is explicitly ordered. `pytest.ini` excludes `tests/upstream`; original tests and helper retained there are historical evidence only.

Not proven: real cloud auth/token lifecycle, expired-token concurrency, wheel transport/parser security, V2 freshness, full property catalog, timestamp provenance/clock skew, actual switches/alarms, live HAOS dependency installation/restart/container replacement, hardware correctness, migration of arbitrary real registries, or all intermediate HA versions. Successful CI and 11 commits do not answer those questions.

## Candidates to port into mLupine

1. **High value:** token snapshot persistence in failure `finally` paths and removal of wrong `CONF_EMAIL` lookup, conditional on reviewing the target API contract. Port together with a listener fix and a loaded-entry rotation test.
2. **High value:** modern OptionsFlow lifecycle, default/minimum polling handling and visible reauth errors. Test against mLupine's chosen HA baseline rather than copying the advertised minimum blindly.
3. **High value:** guarded, idempotent migration that preserves existing entity/device IDs, plus the renamed-entity recorder test. Region-qualified account IDs are already credited to mLupine; assess overlap before treating these as new features.
4. **High value with policy work:** aware last-updated diagnostic, None-safe getters, explicit missing charging semantics and timestamp freshness. Add unknown-sleep mapping, clock-skew cases and alert-provenance tests first; do not copy the threshold as a manufacturer guarantee.
5. **Low-risk useful:** allowlisted diagnostics and accurate device revision/no fake MAC metadata. Verify API attribute availability.
6. **Useful engineering:** metadata validation, pinned build/test environment, source checkout before HACS validation, fixed-time tracked-file ZIP builder and icon checks. Replace hardcoded Rogash1 URL/version constraints with mLupine's actual release policy. Add clean-tree checks if release reproducibility matters.
7. **Do not port blindly:** companion-wheel requirement, HA minimum jump, source-install HACS policy, ownership/support URLs, local branding and generic error suppression. These are distribution/support choices, not automatic improvements; inspect dependency source/assets and installation paths separately.

Overall: a useful integration-side consolidation with unusually explicit migration tests and honest hardware limits. It still contains an avoidable data-update/reload interaction and incomplete unknown/stale-state semantics. Review and port individual behavior with its dependency and regression coverage; wholesale cherry-picking would also import another maintainer's packaging assumptions.
