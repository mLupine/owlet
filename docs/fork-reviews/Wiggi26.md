# Wiggi26/owlet versus ryanbdclark/owlet: independent source review

## Practical result

This fork is principally a reliability, compatibility, packaging and regression-test effort. It does not add a new device protocol, replace the cloud client, add a new platform, or implement a new measurement algorithm. The useful runtime changes are concrete:

1. Options can open on the tested modern Home Assistant versions, entries missing a polling interval fall back to five seconds, and saving a changed interval schedules an integration reload automatically.
2. Poll authentication failure can now reach Home Assistant's reauthentication flow instead of failing while trying to look up a nonexistent email key.
3. Unsupported/missing sleep state stops being reported as awake or raising a dictionary lookup error. Missing normalized properties stop causing getter exceptions. Charging-sensitive entities require a known noncharging state.
4. Nonfinite numeric readings become unknown; instantaneous oxygen outside 0–100 becomes unavailable. Invalid raw booleans are withheld after a successful parser update, avoiding false alarms or false reassurance from coercion.
5. Invalid MACs and an invented hardware revision are omitted. Integration-owned error messages and exception chains are sanitized.
6. HACS installs the component source directory rather than requiring an uploaded ZIP. There is now an extensive offline HA test suite, two locked compatibility profiles and six CI jobs.

Important qualifications: stale source readings are still accepted, numeric parser failures still affect a whole sock poll, token refresh persistence/concurrency is unresolved, and switch commands still lack confirmed device readback. Tests deliberately characterize some defects rather than fixing them. Battery investigation adds evidence, not smoothing or a charging-spike fix.

## Exact comparison and method

Live GitHub API metadata retrieved on 2026-11-07:

- Upstream: `ryanbdclark/owlet`, branch `main`, `f8e0067a1e74a523b0bb4b0841b25404a6926ca8`.
- Fork: `Wiggi26/owlet`, default branch under review `main`, `8293fdda8aaf6960ddf624b1007c899c734ef95b`.
- GitHub comparison: **59 ahead, 0 behind**, status `ahead`; merge base equals upstream head.
- [Live branch comparison](https://github.com/Wiggi26/owlet/compare/ryanbdclark:main...main).
- [Immutable comparison](https://github.com/Wiggi26/owlet/compare/f8e0067a1e74a523b0bb4b0841b25404a6926ca8...8293fdda8aaf6960ddf624b1007c899c734ef95b).

Used `gh api` for both branch heads, cross-repository compare and exact-head checks. An isolated ordinary clone at `/tmp/owlet-wiggi26-L4ZXwQ/repo` supplied full git history, runtime diffs, merge conflict resolution, source, tests and documentation. No shared project files, checkout, refs or remotes were changed. No HA/cloud/device actions, messages, PRs, commits or pushes were performed. No local runtime test execution is claimed. Lockfile contents describe dependencies; external `pyowletapi` package source was not independently downloaded or audited here. Statements about that dependency below are explicitly based on fork contract-test source and documentation, not independent verification of the package implementation.

## Runtime implementation by feature

### Options, defaults and applying changes

Upstream `OptionsFlowHandler.__init__` assigns `self.config_entry`; the fork removes the constructor and returns `OptionsFlowHandler()` so HA supplies the entry. The form still coerces an integer and enforces minimum five seconds. It now defaults a missing option to `POLLING_INTERVAL`, and merges submitted fields into existing options rather than replacing unrelated keys. Evidence: [custom_components/owlet/config_flow.py:96-100](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/config_flow.py#L96-L100) and [custom_components/owlet/config_flow.py:150-173](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/config_flow.py#L150-L173).

`async_setup_entry` independently uses the same default when creating per-sock coordinators. This matters for already stored entries with empty options, not only newly created entries. A captured `options` snapshot plus update listener compares option dictionaries and calls `async_schedule_reload` only when options differ. Token-only entry updates do not reload. The listener is removed on unload. Evidence: [custom_components/owlet/__init__.py:61-72](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/__init__.py#L61-L72) and [custom_components/owlet/__init__.py:100-110](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/__init__.py#L100-L110).

Commits `88d039c` and `6c2f372` are complementary: the former fixes form/defaults, the latter applies saved values. `ae747b9` resolves the concurrent privacy/setup changes by preserving the options snapshot inside the setup try block. This is a real merge resolution, not another independent feature. Tests include [tests/test_options_reload.py](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/tests/test_options_reload.py) and [tests/test_config_flow.py](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/tests/test_config_flow.py).

A missing key is handled, but explicit `null`, negative or wrongly typed interval already in storage is not repaired by `.get(key, default)`; normal UI validation prevents these values. There is no storage-schema migration or version bump for config entries.

### Reauthentication and privacy

Upstream coordinator catches `OwletAuthenticationError` but interpolates `config_entry.data[CONF_EMAIL]`; the flow stores `CONF_USERNAME`, so the error path can raise `KeyError` before HA sees `ConfigEntryAuthFailed`. Fork raises a fixed `ConfigEntryAuthFailed("Authentication failed")`. Authentication errors remain distinct from connection/library/timeout/unexpected failures, which become sanitized `UpdateFailed` categories. Evidence: [custom_components/owlet/coordinator.py:86-107](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/coordinator.py#L86-L107); compare [custom_components/owlet/coordinator.py](https://github.com/ryanbdclark/owlet/blob/f8e0067a1e74a523b0bb4b0841b25404a6926ca8/custom_components/owlet/coordinator.py). [tests/test_polling_reauth.py](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/tests/test_polling_reauth.py) exercises HA reauth and registry preservation.

Setup now places API construction, authentication, discovery, token-envelope persistence and Sock/coordinator construction inside a common guarded region. Auth exceptions become fixed `ConfigEntryAuthFailed`, connection exceptions fixed `ConfigEntryNotReady`, device absence returns false, and unexpected errors log a fixed message and return false. Raised exceptions use `from None`, suppressing sensitive original chains. Initial coordinator refresh and platform forwarding remain outside that try block. Evidence: [custom_components/owlet/__init__.py:42-98](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/__init__.py#L42-L98).

User/reauth flows likewise move API construction inside their try blocks and replace exception traceback logs with fixed strings. Username remains the entry title and account unique ID remains lowercase username. Thus privacy is partial: sanitizing exceptions cannot remove HA Core's independent entry-title interpolation. The fork's [tests/test_core_log_privacy.py](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/tests/test_core_log_privacy.py) and [docs/LOG_PRIVACY.md](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/docs/LOG_PRIVACY.md) deliberately document this residual exposure. Generic reauth errors still return a form without setting an actionable base error ([custom_components/owlet/config_flow.py:118-147](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/config_flow.py#L118-L147)).

### Sleep, unknown values and availability

Upstream awake logic treats anything other than codes 8/15 as awake. Fork accepts exact integer codes 1, 8 and 15 only: 1 is awake, 8/15 asleep, everything else returns `None`. This avoids reporting code 0, unexpected codes, strings, booleans or missing data as a known awake state. Sleep enum getter uses exact integer type and dictionary `.get(..., "unknown")`; unknown codes no longer crash. The mapping itself is unchanged (`0 unknown`, `1 awake`, `8 light_sleep`, `15 deep_sleep`). Evidence: [custom_components/owlet/binary_sensor.py:174-188](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/binary_sensor.py#L174-L188), [custom_components/owlet/sensor.py:175-199](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/sensor.py#L175-L199), [custom_components/owlet/const.py](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/const.py).

Regular binary getters accept exact booleans or exact integers 0/1 and otherwise return unknown. Sensor getters use `.get`, reject booleans/non-numeric types and nonfinite floats. Switch getters apply the same binary rules; switch availability additionally requires a valid known read state. Charging-sensitive entities now require `charging is False`; unknown charging no longer behaves as not charging. Battery percentage and signal strength remain available during charging by their existing descriptions. Evidence: [custom_components/owlet/binary_sensor.py:137-155](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/binary_sensor.py#L137-L155), [custom_components/owlet/sensor.py:151-172](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/sensor.py#L151-L172), [custom_components/owlet/switch.py:74-110](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/switch.py#L74-L110).

Instant oxygen additionally requires a valid numeric value in 0–100 before availability; the existing ten-minute oxygen range guard becomes safe for missing/wrongly typed values. Invalid ordinary numbers become unknown, whereas invalid oxygen is unavailable. No plausibility limits are added for heart rate, temperature, battery percentage or duration. No measurement smoothing is introduced.

### Raw-flag defense: why normalized checks are insufficient

`9583139` adds `_RAW_ALERT_FLAGS`, `_raw_value` and `_invalid_raw_flags`. After `Sock.update_properties()` succeeds, the coordinator examines `sock.raw_properties`, validates ten top-level alert/status flags and version-specific charging/base state, then stores rejected normalized keys in `invalid_flags`. V2 charging/base fields are `CHARGE_STATUS` and `BASE_STATION_ON`; V3 fields are `chg` and `bso` decoded from wrapped `REAL_TIME_VITALS` JSON. Exact booleans and integers 0/1 pass; strings, fractional numbers, nulls, missing wrappers and containers do not. Evidence: [custom_components/owlet/coordinator.py:24-92](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/coordinator.py#L24-L92).

`OwletBaseEntity._property_value` returns `None` for rejected keys, otherwise reads normalized properties safely. Binary sensors, switch state and charging availability use it. Numeric/sleep values are not raw-validated by this guard. Neither dependency-owned dictionary is rewritten and no extra cloud call is made. Evidence: [custom_components/owlet/entity.py:27-31](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/entity.py#L27-L31) and [tests/test_raw_properties.py](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/tests/test_raw_properties.py).

This guard runs **after** normalization: malformed numeric input that aborts the parser still produces whole-sock `UpdateFailed`. It cannot recover current unrelated values from a poll that never produced a new normalized snapshot. Successful numeric coercion also remains visible: a raw `True` heart rate becomes `1.0` according to the explicit characterization test ([tests/test_numeric_validity.py:163-174](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/tests/test_numeric_validity.py#L163-L174)). That is a known boundary, not evidence the integration validates every raw type.

### Device registry metadata

`device_info` formats a string MAC with HA `format_mac`, requires a six-byte lowercase hex representation, excludes all-zero addresses and multicast/broadcast addresses, and supplies connections only when valid. Locally administered unicast MACs remain allowed. Missing/blank/non-string hardware version becomes `None` instead of invented `3r8`. Serial-based `(owlet, serial)` device identifier and entity unique IDs remain unchanged. Evidence: [custom_components/owlet/entity.py:33-59](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/entity.py#L33-L59). This prevents all devices without a MAC from sharing an `unknown` connection and avoids false hardware claims. It does not explicitly clean previously persisted invalid registry connections; a source-level omission is not proof of a complete historical-registry cleanup.

## Packaging, dependency, schema and entity inventory

- Runtime manifest changes maintainer to `@Wiggi26`, documentation/issues to the fork, and integration version `2025.4.3` → `2026.10.0`. **Runtime dependency remains exactly `pyowletapi==2025.4.1`**, same as upstream `main`. [custom_components/owlet/manifest.json](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/manifest.json).
- `hacs.json` drops `zip_release`, `filename: owlet.zip`, HACS minimum `1.32.1` and HA minimum `2024.1`; only name remains. This enables source-directory packaging but also removes an explicit compatibility floor. It does not prove support for every older HA version. [hacs.json](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/hacs.json).
- Adds component-local Apache license, attribution NOTICE and local HACS icon. Icon attribution points to the original HA brands blob and explicitly does not claim the mark is Apache licensed. [custom_components/owlet/NOTICE](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/NOTICE).
- README/info/changelog switch installation and update/rollback instructions to this fork, explain one owner for the component directory and keeping existing entries. Upstream source/tag versus uploaded-ZIP mismatch is described by the fork; this report compares source `main`, not historical release ZIP contents. [README.md](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/README.md), [docs/PACKAGING.md](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/docs/PACKAGING.md).
- No new platforms, entity description keys, units, translations, service schema, supported device versions, region choices or sleep mappings. Existing sensor/binary/switch set remains. Entity creation still depends on keys in the initial normalized snapshot; missing capabilities appearing later do not dynamically create entities. Account unique ID and entry `VERSION = 1` remain; config data remains region/username/tokens, options scan interval.
- Development-only `pyproject.toml` and `uv.lock` pin Linux profiles: HA 2025.12.4/Python 3.13.2 and HA 2026.10.2/Python 3.14.2, matching custom-component test plugins; requires Python >=3.13.2,<3.15 excluding 3.14.0/1. These are development-environment constraints, not a new runtime manifest Python requirement. Ruff, pip-audit and zizmor are dev tools. [pyproject.toml](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/pyproject.toml).

## CI and test changes

Original tests are substantially rewritten to use the custom-component plugin and real integration loading. Large original JSON fixtures are replaced with independently authored synthetic payloads; six fixture filenames ultimately remain, now small and loaded through `fixture_data.py`. The intermediate `121aa2d` deletion/inline fixture arrangement is superseded by `0222a61`. No real account capture is claimed. Socket blocking, strict fake HTTP queues and unexpected-call teardown checks prevent silent cloud fallback. Some tests exercise the pinned library through fake sessions; most integration tests mock API boundaries.

New coverage includes options/reload, two-sock separation, registry bindings/customizations, auth recovery, numeric validity, missing fields, raw parsing, metadata, privacy, synthetic charging transitions and dependency contracts. Battery tests show an input sequence 50→100→50→50 is exposed faithfully; they do not establish a production source or fix a spike. Core-log tests deliberately prove title leakage remains. Library contract tests characterize refresh, status-code, request-count, command truthiness and session-close behavior without changing the runtime dependency.

The workflow replaces scheduled `cron.yml` with push-to-main/PR-to-main `validate.yml`; six jobs cover Ruff/zizmor, two Core profiles, current-profile pip-audit, hassfest and HACS. Actions are pinned, contents permission read-only, credentials not persisted, concurrent outdated runs cancelled, job caches separated. Dependency audit covers the installed current profile, not the historical baseline. HACS originally failed brand validation after the raw-flag fix; `edb4648` adds the icon and later reconciliation records its recovery. Earlier failure is not the final status.

Live exact-head check-runs API reports all six **success** at the reviewed SHA. Repository documentation attributes 374 passes, one strict stale-source xfail and 97.45% combined coverage per profile to final runtime/brand validation. I verified current check conclusions, not independently reran pytest or extracted every job log. A strict xfail is a known failed behavior under an accepted expectation, not a pass. Coverage and offline tests prove neither live Owlet behavior nor every HA release. Evidence: [.github/workflows/validate.yml](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/.github/workflows/validate.yml), [docs/TESTING.md](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/docs/TESTING.md).

## Concrete remaining risks and candidate bugs

Severity here reflects the failure scenario, not medical certification or a claim of production occurrence. Most are inherited limitations, not newly introduced regressions.

| Severity / origin | Scenario and evidence | Concrete direction |
| --- | --- | --- |
| High, inherited | A successful cloud response contains a years-old source timestamp; coordinator reports success and numeric entities remain available. `test_old_source_measurement_unavailable` intentionally xfails. | Define per-reading freshness/clock policy, retain timezone, withhold stale measurements and test recovery/unchanged values with new timestamps. |
| Medium, retained dependency boundary | One raw null/malformed numeric field causes normalization to raise before new properties are published; coordinator catches the exception and whole sock becomes unavailable. Other sock coordinators continue on ordinary updates. | Fix dependency normalization per field or provide a supported pre-normalization hook; do not reuse old normalized values as current. |
| Medium, partial validation | Raw boolean heart rate becomes numeric 1.0 before sensor checking; finite implausible numeric values outside oxygen remain accepted. | Validate original numeric source types and agreed device-specific ranges at parser boundary. |
| Medium, inherited control gap | `async_turn_on/off` simply await the library call, discard its result and request no verification refresh/readback. Fork tests characterize library response-truthiness including nonempty error mappings. | Define command acknowledgement/error contract, sanitized errors and readback; a completed await is insufficient proof of action. |
| Medium, inherited auth gap | Coordinator persists tokens only when return envelope contains `tokens`; test contracts show client rotation can omit that envelope. Multiple sock coordinators share one API client without integration-level refresh lock. | Review library refresh/persistence atomically and test concurrent refresh, partial exchanges and actual restart storage. |
| Medium, partial privacy repair | Default entry title is username; Core setup logs independently print entry title. Generic integration errors are sanitized, title remains. | Review safe logging label/redaction design; neutral new titles alone do not repair existing/custom entries. |
| Low/medium, inherited UI | Reauth unexpected exception logs fixed message but sets no form error; user sees form again without actionable explanation. | Assign translated generic/connection/auth error categories without exposing raw exceptions. |
| Low, fork docs | README says saved interval requires reload/restart, but code now schedules reload automatically; support wording remains older than tested-profile evidence. NOTICE says application behaviour unchanged although later commits change it. | Update README and NOTICE to describe current behavior and distinguish tested profiles from broad support. |

Evidence anchors: [tests/test_sensor.py:87-106](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/tests/test_sensor.py#L87-L106), [tests/test_raw_properties.py](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/tests/test_raw_properties.py), [tests/test_numeric_validity.py:163-174](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/tests/test_numeric_validity.py#L163-L174), [custom_components/owlet/switch.py:90-96](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/custom_components/owlet/switch.py#L90-L96), [tests/test_library_contracts.py:511-580](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/tests/test_library_contracts.py#L511-L580), [docs/LOG_PRIVACY.md](https://github.com/Wiggi26/owlet/blob/8293fdda8aaf6960ddf624b1007c899c734ef95b/docs/LOG_PRIVACY.md). External library behaviors in this table are supported by the fork's test expectations; they were not independently executed here. No concrete newly introduced high-severity regression was established by this static review.

## Backward compatibility and migration

Keep the existing entry and component domain; installing the fork should not require deleting/readding the account. Serial-derived entity IDs and account unique ID generation are preserved. Options reload is intentionally disruptive briefly because it recreates per-sock coordinators/platforms, but tests assert identity and customization preservation. Simulated reload preservation is not an actual cross-Core storage migration test.

Automations must tolerate more honest unknown/unavailable states: unsupported sleep is no longer awake, malformed raw alerts no longer coerce to valid booleans, missing/invalid charging hides charging-sensitive measurements, and invalid oxygen is unavailable. This is a deliberate behavioral change even without new entity keys. Existing automations comparing only on/off may need explicit unknown/unavailable handling.

Only one HACS repository should manage `custom_components/owlet`. No dependency upgrade is involved compared with upstream main, but switching from a historical release ZIP may differ; inspect the installed artifact rather than assuming its pin matches source. Older HA support remains unestablished below the two explicit profiles. A rollback preserves files/entry shape but can reintroduce false awake, invalid flags and options/auth defects.

## Candidates to port to mLupine

1. Highest value: `88d039c` + `6c2f372` options/default/reload changes and their identity-preservation tests; adapt to mLupine's actual options architecture.
2. Port polling reauth fix `22e9c24`; it removes a clear error-path key mismatch. Combine with existing fork-specific auth/session behavior rather than replacing it blindly.
3. Port missing-value/sleep/numeric handling (`a6b006b`, `3ec870e`, `1d01b7d`) with explicit acceptance of unknown/unavailable semantics. Keep raw-versus-normalized validation distinction.
4. Consider `9583139` raw flag defense if mLupine retains this exact library/raw schema. It is useful narrow defense, not a replacement for parser repair; schema divergence requires re-review.
5. Port `70d2f19` metadata sanitation and selected privacy changes `f8f3d6e`, retaining enough safe error categories for diagnosis. Do not promise complete privacy.
6. Reuse synthetic HA regression infrastructure and strict library contracts selectively. They provide more value than importing audit-document churn or the fork's issue-sprint agent configuration. Set versions to the target fork's actual supported baseline.
7. Source packaging/local attribution/icon are useful if mLupine needs equivalent HACS delivery. Do not copy Wiggi26 ownership URLs/version unchanged. Battery and Core-log investigations are useful characterization tests, not runtime fixes to cherry-pick expecting changed behavior.

No direct comparison against mLupine source was requested/performed by this sub-review; these are candidate upstream-relative improvements, not a claim that mLupine lacks them.

## Complete unique-commit inventory

All 59 GitHub compare commits follow in API chronological order. Full immutable commit links provide exact patches. Merge commits are listed as history objects, not counted as additional independent features. No explicit revert commits were found. Only the initial packaging commit changes runtime version; there are no standalone version-only commits. Documentation shortening, fixture deletion/reintroduction and replacement of the cron workflow are historical intermediate changes superseded at final head.

1. [`c2bd8f65527e445e40be62454e6fb555af410769`](https://github.com/Wiggi26/owlet/commit/c2bd8f65527e445e40be62454e6fb555af410769) — **Modernize public-fork HACS source packaging and installation docs**. Source HACS packaging, fork manifest identity/version, install docs, component license/NOTICE, initial audit/roadmap and pinned validation automation.

2. [`c4de3fcf30310eb3e7727736a563d77ba9dd409a`](https://github.com/Wiggi26/owlet/commit/c4de3fcf30310eb3e7727736a563d77ba9dd409a) — **Record packaging validation and refresh hosted runner baseline**. Non-runtime change: .github/workflows/cron.yml, docs/AUDIT.md, docs/PACKAGING.md.

3. [`62a395405bbdd2c68a175cbd6bd81cf5cf06198b`](https://github.com/Wiggi26/owlet/commit/62a395405bbdd2c68a175cbd6bd81cf5cf06198b) — **Trim installation docs and run validation only on pushes and PRs**. Non-runtime change: .github/workflows/cron.yml, .github/workflows/validate.yml, AGENTS.md, CHANGELOG.md, NOTICE and 6 more files.

4. [`a1b1fb9d4c592cf61fb1b5078669346c065a3c75`](https://github.com/Wiggi26/owlet/commit/a1b1fb9d4c592cf61fb1b5078669346c065a3c75) — **Merge pull request #1 from Wiggi26/codex/hacs-fork-packaging**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: .github/dependabot.yml, .github/workflows/cron.yml, .github/workflows/validate.yml, .gitignore, AGENTS.md and 10 more files.

5. [`121aa2dd83d34e96c7bb572944ad9cfe94088f8e`](https://github.com/Wiggi26/owlet/commit/121aa2dd83d34e96c7bb572944ad9cfe94088f8e) — **Establish offline Home Assistant regression tests and CI gates**. Offline CI/test overhaul; runtime edits mechanical import/format cleanup. Rewrites original tests and fixtures, adds lockfile, compatibility matrix and strict regressions.

6. [`b8390744b0ae5d6f6edabe8af3b29143ae500940`](https://github.com/Wiggi26/owlet/commit/b8390744b0ae5d6f6edabe8af3b29143ae500940) — **Record CI evidence and separate parallel job caches**. Non-runtime change: .github/workflows/validate.yml, docs/AUDIT.md, docs/ROADMAP.md, docs/TESTING.md, pyproject.toml.

7. [`0222a61440e303667a3070793800e8a905da9b5b`](https://github.com/Wiggi26/owlet/commit/0222a61440e303667a3070793800e8a905da9b5b) — **Retain synthetic JSON response fixtures**. Non-runtime change: AGENTS.md, docs/AUDIT.md, docs/TESTING.md, tests/conftest.py, tests/fixture_data.py and 9 more files.

8. [`197bf4e2b316d5f8b7791b179371b0c887153f4c`](https://github.com/Wiggi26/owlet/commit/197bf4e2b316d5f8b7791b179371b0c887153f4c) — **Merge pull request #2 from Wiggi26/codex/offline-ci**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: .github/dependabot.yml, .github/workflows/validate.yml, .gitignore, .python-version, AGENTS.md and 33 more files.

9. [`3a44370888f8a58befb9c9ec0decfe576fb23b69`](https://github.com/Wiggi26/owlet/commit/3a44370888f8a58befb9c9ec0decfe576fb23b69) — **Triage audit findings into a fork-only remediation plan**. Non-runtime change: AGENTS.md, docs/AUDIT.md, docs/ROADMAP.md.

10. [`2838055661efa16350a1bd767acc97b0684ca347`](https://github.com/Wiggi26/owlet/commit/2838055661efa16350a1bd767acc97b0684ca347) — **Merge pull request #26 from Wiggi26/codex/remediation-plan**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: AGENTS.md, docs/AUDIT.md, docs/ROADMAP.md.

11. [`02a47ee1a8673d3267135364c72d6735de086b6d`](https://github.com/Wiggi26/owlet/commit/02a47ee1a8673d3267135364c72d6735de086b6d) — **Set up reusable Owlet issue sprint workflow**. Non-runtime change: .agents/skills/owlet-issue-sprint/SKILL.md, .agents/skills/owlet-issue-sprint/scripts/discover.py, .codex/agents/owlet-complex.toml, .codex/agents/owlet-reviewer.toml, .codex/config.toml and 2 more files.

12. [`df89cc8df5312dd4f8fe306bd74d4a9140990b56`](https://github.com/Wiggi26/owlet/commit/df89cc8df5312dd4f8fe306bd74d4a9140990b56) — **Increase reasoning effort for subagent model**. Non-runtime change: .codex/config.toml.

13. [`d963c787c0dc3ae0c140eec6052bd5eef9cd1002`](https://github.com/Wiggi26/owlet/commit/d963c787c0dc3ae0c140eec6052bd5eef9cd1002) — **Condense issue sprint guidance**. Non-runtime change: .agents/skills/owlet-issue-sprint/SKILL.md, AGENTS.md, docs/ISSUE_SPRINT.md.

14. [`aa0c4134f5fdbbaa163ec63d928d92e65628f6ce`](https://github.com/Wiggi26/owlet/commit/aa0c4134f5fdbbaa163ec63d928d92e65628f6ce) — **Merge pull request #27 from Wiggi26/codex/issue-sprint**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: .agents/skills/owlet-issue-sprint/SKILL.md, .agents/skills/owlet-issue-sprint/scripts/discover.py, .codex/agents/owlet-complex.toml, .codex/agents/owlet-reviewer.toml, .codex/config.toml and 2 more files.

15. [`88d039c771bf64eb7aeb7c4baf96fe06c0b3b961`](https://github.com/Wiggi26/owlet/commit/88d039c771bf64eb7aeb7c4baf96fe06c0b3b961) — **Repair options flow and missing polling defaults**. Fix options API and preserve unknown options; five-second defaults in form/setup.

16. [`a6b006b3f6c422b28f14ff12abffa1a53c10c840`](https://github.com/Wiggi26/owlet/commit/a6b006b3f6c422b28f14ff12abffa1a53c10c840) — **Preserve unknown and unsupported sleep states**. Unknown sleep no longer awake; exact-type checking and safe enum lookup.

17. [`be24d39592d0709a7a7bb8b8b3e1210900f46fc2`](https://github.com/Wiggi26/owlet/commit/be24d39592d0709a7a7bb8b8b3e1210900f46fc2) — **Establish retained cloud-library contracts**. Non-runtime change: docs/LIBRARY_CONTRACTS.md, tests/test_dependency.py, tests/test_library_contracts.py.

18. [`7807ed2050dc04f81a2bd341c16769ea244c8405`](https://github.com/Wiggi26/owlet/commit/7807ed2050dc04f81a2bd341c16769ea244c8405) — **Require concise documentation and focused docstrings**. Non-runtime change: AGENTS.md.

19. [`e7a3edd624849f7b8b353356fd8b8978f9e758a1`](https://github.com/Wiggi26/owlet/commit/e7a3edd624849f7b8b353356fd8b8978f9e758a1) — **Condense contract documentation and remove tracking labels from docstrings**. Non-runtime change: docs/LIBRARY_CONTRACTS.md, tests/test_dependency.py, tests/test_library_contracts.py.

20. [`1be3046f46a83dbd4e99b8af653335d57623eb56`](https://github.com/Wiggi26/owlet/commit/1be3046f46a83dbd4e99b8af653335d57623eb56) — **Merge pull request #31 from Wiggi26/codex/concise-docs**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: AGENTS.md.

21. [`bd3bd2a5216133aac44ecfeb88f8bb8c61becd9d`](https://github.com/Wiggi26/owlet/commit/bd3bd2a5216133aac44ecfeb88f8bb8c61becd9d) — **Merge pull request #30 from Wiggi26/codex/issue-7-library-contracts**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: docs/LIBRARY_CONTRACTS.md, tests/test_dependency.py, tests/test_library_contracts.py.

22. [`d3980ee50f221fd6e6c7d715bf84b5c01cfbe8d0`](https://github.com/Wiggi26/owlet/commit/d3980ee50f221fd6e6c7d715bf84b5c01cfbe8d0) — **Merge pull request #29 from Wiggi26/codex/issue-10-unknown-sleep**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: custom_components/owlet/binary_sensor.py, custom_components/owlet/sensor.py, tests/test_binary_sensor.py, tests/test_sensor.py.

23. [`202d1eae69de124dfc5fdd080eb4407b5e50a1dc`](https://github.com/Wiggi26/owlet/commit/202d1eae69de124dfc5fdd080eb4407b5e50a1dc) — **Merge pull request #28 from Wiggi26/codex/issue-3-options-defaults**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: custom_components/owlet/__init__.py, custom_components/owlet/config_flow.py, tests/test_config_flow.py, tests/test_init.py.

24. [`59bb7ecf6be55f33e505122c0ccab1d3d21e220e`](https://github.com/Wiggi26/owlet/commit/59bb7ecf6be55f33e505122c0ccab1d3d21e220e) — **docs: extend issue sprint lifecycle management**. Non-runtime change: .agents/skills/owlet-issue-sprint/SKILL.md, docs/ISSUE_SPRINT.md.

25. [`dcafed383601c0177dd9336e0996e913f01a9b4a`](https://github.com/Wiggi26/owlet/commit/dcafed383601c0177dd9336e0996e913f01a9b4a) — **Merge pull request #32 from Wiggi26/codex/issue-lifecycle-skill**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: .agents/skills/owlet-issue-sprint/SKILL.md, docs/ISSUE_SPRINT.md.

26. [`22e9c2408eb57939960123e863e7060134f2d7e5`](https://github.com/Wiggi26/owlet/commit/22e9c2408eb57939960123e863e7060134f2d7e5) — **Restore polling-triggered reauthentication**. Remove CONF_EMAIL lookup from polling auth error; allow HA reauthentication.

27. [`3ec870e225e7f5ec0069ccd3ea51e1164c79ff55`](https://github.com/Wiggi26/owlet/commit/3ec870e225e7f5ec0069ccd3ea51e1164c79ff55) — **Handle missing normalized entity properties**. Safe missing-property getters, numeric/binary type guards and conservative charging/switch availability.

28. [`70d2f19cb11c01980a22a26827d28d8969a9fd4c`](https://github.com/Wiggi26/owlet/commit/70d2f19cb11c01980a22a26827d28d8969a9fd4c) — **Omit invented hardware and invalid MAC connections**. Reject invalid MAC connections and invented hardware fallback.

29. [`2290b6e78f9522f9cfd6b5cb5d7124faf9999855`](https://github.com/Wiggi26/owlet/commit/2290b6e78f9522f9cfd6b5cb5d7124faf9999855) — **Merge pull request #35 from Wiggi26/codex/issue-16-device-metadata**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: custom_components/owlet/entity.py, tests/test_device_metadata.py.

30. [`6feada08c145d04ed64ac5c0fdd8d132569ec3a9`](https://github.com/Wiggi26/owlet/commit/6feada08c145d04ed64ac5c0fdd8d132569ec3a9) — **Merge pull request #34 from Wiggi26/codex/issue-9-missing-properties**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: custom_components/owlet/binary_sensor.py, custom_components/owlet/sensor.py, custom_components/owlet/switch.py, tests/test_binary_sensor.py, tests/test_sensor.py.

31. [`85173c147dc55af27b8ef10f8f8917da88da0eda`](https://github.com/Wiggi26/owlet/commit/85173c147dc55af27b8ef10f8f8917da88da0eda) — **Merge pull request #33 from Wiggi26/codex/issue-4-polling-reauth**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: custom_components/owlet/coordinator.py, tests/test_coordinator.py, tests/test_polling_reauth.py.

32. [`1af8867cc6a6c913728d92c526a714642deaf115`](https://github.com/Wiggi26/owlet/commit/1af8867cc6a6c913728d92c526a714642deaf115) — **Reconcile merged remediation evidence and remaining gates**. Non-runtime change: docs/AUDIT.md, docs/ROADMAP.md, docs/TESTING.md.

33. [`6c2f3722d631ef9bbe30f8ae0e6867f154e32557`](https://github.com/Wiggi26/owlet/commit/6c2f3722d631ef9bbe30f8ae0e6867f154e32557) — **Apply saved polling options through entry reload**. Register option-change reload listener; ignore token-only changes.

34. [`1d01b7d1f2b1639e4a84effea99e04ef419834d1`](https://github.com/Wiggi26/owlet/commit/1d01b7d1f2b1639e4a84effea99e04ef419834d1) — **Reject nonfinite sensor values and invalid oxygen percentages**. Reject NaN/infinity and invalid instantaneous oxygen range.

35. [`f8f3d6e60363e3addd6b9d34c27c887d3f267cdb`](https://github.com/Wiggi26/owlet/commit/f8f3d6e60363e3addd6b9d34c27c887d3f267cdb) — **Sanitize setup polling and flow failure details**. Sanitize errors/logs and broaden guarded setup/flow construction.

36. [`552450b1d0aa31a0dd54ad331fcd90abd69430bf`](https://github.com/Wiggi26/owlet/commit/552450b1d0aa31a0dd54ad331fcd90abd69430bf) — **Merge pull request #36 from Wiggi26/codex/batch-reconcile-20261019**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: docs/AUDIT.md, docs/ROADMAP.md, docs/TESTING.md.

37. [`f433772effadc051954cbb73a01877bb15462775`](https://github.com/Wiggi26/owlet/commit/f433772effadc051954cbb73a01877bb15462775) — **Merge pull request #37 from Wiggi26/codex/issue-3-options-reload**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: custom_components/owlet/__init__.py, tests/test_coordinator.py, tests/test_options_reload.py.

38. [`63f156d76fd31c9ec7180c3d186e26a7033da5fc`](https://github.com/Wiggi26/owlet/commit/63f156d76fd31c9ec7180c3d186e26a7033da5fc) — **Merge pull request #38 from Wiggi26/codex/issue-10-numeric-validity**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: custom_components/owlet/sensor.py, tests/test_numeric_validity.py, tests/test_sensor.py.

39. [`ae747b99cb6c9c6ea87237dfe4ee0eaac14e87af`](https://github.com/Wiggi26/owlet/commit/ae747b99cb6c9c6ea87237dfe4ee0eaac14e87af) — **Resolve PR 39 setup conflict with current fork main**. Conflict-resolution merge: combines privacy setup guard with the option snapshot/reload implementation and already merged numeric tests; preserves both changes.

40. [`2f1556652897ab1ec9d504017ef770ba84d363c5`](https://github.com/Wiggi26/owlet/commit/2f1556652897ab1ec9d504017ef770ba84d363c5) — **Merge pull request #39 from Wiggi26/codex/issue-6-error-privacy**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: custom_components/owlet/__init__.py, custom_components/owlet/config_flow.py, custom_components/owlet/coordinator.py, tests/test_error_privacy.py.

41. [`116508e29aada6c3fe99eff690c79f3978679334`](https://github.com/Wiggi26/owlet/commit/116508e29aada6c3fe99eff690c79f3978679334) — **Reconcile merged options numeric and privacy evidence**. Non-runtime change: docs/AUDIT.md, docs/ROADMAP.md, docs/TESTING.md.

42. [`c47f8a26f48abb15063e201eb06c1da486404176`](https://github.com/Wiggi26/owlet/commit/c47f8a26f48abb15063e201eb06c1da486404176) — **Characterize raw property parsing failures and coercion**. Characterization tests/docs for parser failure/coercion; does not fix raw numeric parsing.

43. [`8529eeebb426320b49e171bfcdbd232d7ab4cedf`](https://github.com/Wiggi26/owlet/commit/8529eeebb426320b49e171bfcdbd232d7ab4cedf) — **Trace synthetic battery charging transitions**. Synthetic battery transition replay/docs; no filter or runtime battery behavior change.

44. [`80c06ff47a33d63c5ce2645a6ff8da118115d550`](https://github.com/Wiggi26/owlet/commit/80c06ff47a33d63c5ce2645a6ff8da118115d550) — **Merge pull request #41 from Wiggi26/codex/issue-9-raw-properties**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: docs/RAW_PROPERTIES.md, tests/test_raw_properties.py.

45. [`d178a3390a07e50be624165a571afc7242871cec`](https://github.com/Wiggi26/owlet/commit/d178a3390a07e50be624165a571afc7242871cec) — **Merge pull request #42 from Wiggi26/codex/issue-18-battery-transitions**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: docs/BATTERY.md, tests/fixtures/battery_transitions.json, tests/test_battery_transitions.py.

46. [`0abbeb2348b35f4bd08ce9cfb9555aff26ea328a`](https://github.com/Wiggi26/owlet/commit/0abbeb2348b35f4bd08ce9cfb9555aff26ea328a) — **Reconcile merged parser and battery investigations**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: docs/AUDIT.md, docs/BATTERY.md, docs/RAW_PROPERTIES.md, docs/ROADMAP.md, docs/TESTING.md and 3 more files.

47. [`b7632c0b64c2b95b1269f8cd624dc05020849a63`](https://github.com/Wiggi26/owlet/commit/b7632c0b64c2b95b1269f8cd624dc05020849a63) — **Merge pull request #40 from Wiggi26/codex/batch-reconcile-20261019b**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: docs/AUDIT.md, docs/ROADMAP.md, docs/TESTING.md.

48. [`1f7e25b3aea509b53b259e8050d733b8d8f39850`](https://github.com/Wiggi26/owlet/commit/1f7e25b3aea509b53b259e8050d733b8d8f39850) — **Characterize Core entry-title log privacy**. Core entry-title log exposure characterization; no title/redaction repair.

49. [`7e50be28e6a296515628853495f08c3d7224e849`](https://github.com/Wiggi26/owlet/commit/7e50be28e6a296515628853495f08c3d7224e849) — **Merge pull request #43 from Wiggi26/codex/issue-6-core-log-privacy**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: docs/LOG_PRIVACY.md, tests/test_core_log_privacy.py.

50. [`467f793f14adc9cf1dfd061d43b5c4230e8de21d`](https://github.com/Wiggi26/owlet/commit/467f793f14adc9cf1dfd061d43b5c4230e8de21d) — **Reconcile merged Core log privacy evidence**. Non-runtime change: docs/AUDIT.md, docs/ROADMAP.md, docs/TESTING.md.

51. [`2fd2e70292448e88c8c9f3fe3271f96a632dc714`](https://github.com/Wiggi26/owlet/commit/2fd2e70292448e88c8c9f3fe3271f96a632dc714) — **Merge pull request #44 from Wiggi26/codex/batch-reconcile-20261019c**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: docs/AUDIT.md, docs/ROADMAP.md, docs/TESTING.md.

52. [`95831390bc2a7f52b099f9a6c04b243678027171`](https://github.com/Wiggi26/owlet/commit/95831390bc2a7f52b099f9a6c04b243678027171) — **Withhold invalid raw flag states after successful polls**. Post-success raw validation withholds invalid alert/charging/base states.

53. [`0dc08a8b76261aade768e8aa77bc1fb0a6ce947a`](https://github.com/Wiggi26/owlet/commit/0dc08a8b76261aade768e8aa77bc1fb0a6ce947a) — **Merge pull request #45 from Wiggi26/codex/issue-9-raw-flags**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: custom_components/owlet/binary_sensor.py, custom_components/owlet/coordinator.py, custom_components/owlet/entity.py, custom_components/owlet/sensor.py, custom_components/owlet/switch.py and 2 more files.

54. [`2e0deafa2d92b47b75ba25bac0cc9b4173983ac9`](https://github.com/Wiggi26/owlet/commit/2e0deafa2d92b47b75ba25bac0cc9b4173983ac9) — **Reconcile partial raw flag fix and failed HACS gate**. Non-runtime change: docs/AUDIT.md, docs/PACKAGING.md, docs/ROADMAP.md, docs/TESTING.md.

55. [`fe9e47688b3436e78dfb2cf72944adaae6c8ca84`](https://github.com/Wiggi26/owlet/commit/fe9e47688b3436e78dfb2cf72944adaae6c8ca84) — **Merge pull request #47 from Wiggi26/codex/batch-reconcile-20261020**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: docs/AUDIT.md, docs/PACKAGING.md, docs/ROADMAP.md, docs/TESTING.md.

56. [`edb46488d2a0abf5b398ee82f90e69148a38f520`](https://github.com/Wiggi26/owlet/commit/edb46488d2a0abf5b398ee82f90e69148a38f520) — **Add local Owlet icon for HACS brand validation**. Add local icon and provenance; repairs HACS brand gate without changing integration logic.

57. [`989cdf400c6c21ef8720c09bf5a279b36e023cf7`](https://github.com/Wiggi26/owlet/commit/989cdf400c6c21ef8720c09bf5a279b36e023cf7) — **Merge pull request #48 from Wiggi26/codex/issue-46-local-brand**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: custom_components/owlet/NOTICE, custom_components/owlet/brand/icon.png, docs/PACKAGING.md.

58. [`fca6f821c458cfbae2ff402235e8ecc5ec303308`](https://github.com/Wiggi26/owlet/commit/fca6f821c458cfbae2ff402235e8ecc5ec303308) — **Reconcile merged HACS brand gate evidence**. Non-runtime change: docs/AUDIT.md, docs/ROADMAP.md, docs/TESTING.md.

59. [`8293fdda8aaf6960ddf624b1007c899c734ef95b`](https://github.com/Wiggi26/owlet/commit/8293fdda8aaf6960ddf624b1007c899c734ef95b) — **Merge pull request #49 from Wiggi26/codex/reconcile-brand-gate**. Merge/integration of the named branch; incorporates its changes, not a separate feature. First-parent affected areas: docs/AUDIT.md, docs/ROADMAP.md, docs/TESTING.md.

## Verification boundary

This is a source/history review plus live metadata/check status verification. It is not an executed dependency audit, a fresh local test run, a HACS installation, a firmware/cloud trace, a manual HA UI acceptance test or a device-control test. The existing source and tests support useful targeted fixes; the commit count does not establish reliability.
