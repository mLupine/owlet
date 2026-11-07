# soschlegel/owlet main versus ryanbdclark/owlet main

Reviewed live on 2026-11-07. This is a compatibility and packaging fork, not an expansion of the sensor/platform feature set. Six unique commits do not mean six independent features: two only change the version, two successively change the same CI checkout action, one adds an icon, and one contains essentially all runtime changes.

## Practical changes first

1. Authentication failures are more likely to produce the intended reauthentication flow instead of an uncaught setup exception or a KeyError while reporting the failure. Incorrect credentials entered during reauthentication now produce a visible password-field error.
2. The options dialog uses modern Home Assistant's framework-provided config-entry property. Saving a polling interval reloads the integration, so the new interval can take effect without restarting HA. The implementation also reloads on token-data changes; that is a real defect worth fixing before porting.
3. The dependency moves from pyowletapi 2025.4.1 to 2025.4.10 and removed exception imports are eliminated. Library internals were not audited; endpoint, authentication protocol, device support, and property-map equivalence are not independently established here.
4. The no-devices setup error gains text in source strings and all three translation files. There are no new entity definitions, identifiers, units, alerts, switches, regions, or configuration fields in the integration diff.
5. Tagged releases can automatically publish the HACS zip, daily hassfest uses a newer checkout action, and a local owl icon is added. These changes do not establish real-device correctness.

## Exact comparison boundary

| Item | Value |
|---|---|
| Upstream | ryanbdclark/owlet, default branch main |
| Upstream main SHA | `f8e0067a1e74a523b0bb4b0841b25404a6926ca8` |
| Fork | soschlegel/owlet, default branch main |
| Fork main SHA | `b51c6faccae26749253f1d0e02ff90912b764f3c` |
| Merge base | `f8e0067a1e74a523b0bb4b0841b25404a6926ca8` |
| Ahead / behind | 6 / 0 |
| GitHub comparison status | ahead |
| Compare | https://github.com/soschlegel/owlet/compare/ryanbdclark:main...main |

GitHub compare API and live branch metadata were read with gh; a unique temporary clone independently confirmed the two heads and complete commit/diff inventory. Since upstream is the merge base, the compare diff is also the direct head-to-head diff. Net: 12 files changed, 60 inserted lines, 71 deleted lines, including a new 4,737-byte PNG. This report refers to the upstream custom integration repository, not an assertion that these files ship in Home Assistant Core.

## Implementation by feature

### Authentication and reauthentication

Setup still constructs an OwletAPI from the stored region, access token, expiry and refresh token, authenticates, discovers supported devices, persists replacement tokens and starts one coordinator per device. The fork changes the exception imports and catches `OwletCredentialsError` together with `OwletAuthenticationError`, raising `ConfigEntryAuthFailed`. Upstream caught authentication, email and password errors but omitted credentials errors. Evidence: [custom_components/owlet/__init__.py:37-109](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/__init__.py#L37-L109) and [custom_components/owlet/__init__.py:37-104](https://github.com/ryanbdclark/owlet/blob/f8e0067a1e74a523b0bb4b0841b25404a6926ca8/custom_components/owlet/__init__.py#L37-L104).

The initial user form already caught `OwletCredentialsError` and returned base error `invalid_credentials`; that is upstream behavior. The fork removes the separate email/password catches and their exception imports. During reauthentication, it replaces the old `OwletPasswordError` handler with `OwletCredentialsError`, maps that to password-field `invalid_credentials`, and leaves token persistence, entry reload and successful abort behavior unchanged. Evidence: [custom_components/owlet/config_flow.py:49-142](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/config_flow.py#L49-L142).

The coordinator's `_async_update_data` already converted `OwletAuthenticationError` into `ConfigEntryAuthFailed`, but constructed the message with `entry.data[CONF_EMAIL]`. The config flow stores `CONF_USERNAME`, so this could raise KeyError before the intended exception was constructed. The fork uses `CONF_USERNAME` consistently. It does not otherwise change token handling, polling, transport-error handling or property conversion. Evidence: [custom_components/owlet/coordinator.py:28-55](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/coordinator.py#L28-L55) and [custom_components/owlet/config_flow.py:49-142](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/config_flow.py#L49-L142).

The compatibility commit claims that Firebase collapsed several error codes into INVALID_LOGIN_CRED[custom_components/owlet/translations/en.json:7-14](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/translations/en.json#L7-L14)TIALS, that pyowletapi removed two exception classes after 2025.4.1, and that all used dependency interfaces stayed unchanged. The integration diff proves the import/catch and pin changes, not those external historical claims. No pyowletapi wheel/source or Firebase implementation was inspected.

### Options and polling lifecycle

Upstream passed a ConfigEntry into `OptionsFlowHandler.__init__` and assigned `self.config_entry`. The fork removes that constructor and returns `OptionsFlowHandler()` from `async_get_options_flow`; the handler reads the base class property later in `async_step_init`. Evidence: [custom_components/owlet/config_flow.py:91-164](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/config_flow.py#L91-L164). Live HA Core source at `1cc3e51cce06be9c2aedac564b3b13134c661fc6` confirms that OptionsFlow exposes a getter-only config_entry property: [config_entries.py:4241-4250](https://github.com/home-assistant/core/blob/1cc3e51cce06be9c2aedac564b3b13134c661fc6/homeassistant/config_entries.py#L4241-L4250). This explains the old assignment failure on that framework implementation; it does not establish compatibility with every historical HA release.

The fork adds `entry.async_on_unload(entry.add_update_listener(async_update_options))` after forwarding platforms. `async_update_options` unconditionally calls `async_reload`. Cleanup unregisters the listener when the entry unloads. Re-setup reads the saved `scan_interval` and constructs coordinators with `timedelta(seconds=interval)`, so an options save now applies through rebuilding coordinators. Evidence: [custom_components/owlet/__init__.py:37-109](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/__init__.py#L37-L109) and [custom_components/owlet/coordinator.py:28-55](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/coordinator.py#L28-L55).

The polling form is unchanged: integer coercion, minimum five seconds, current option as default. New entries still default to five seconds. There is no upper limit, adaptive polling, per-device interval or push support.

### Error strings and translations

Source strings plus English, French and Ukrainian files lose `invalid_email` and `invalid_password`, retain `invalid_credentials`, and gain `no_devices`. The `no_devices` branch existed upstream but lacked the translation key. The French addition is French; the Ukrainian file's new message is English, matching its existing English error strings rather than providing a Ukrainian localization. Evidence: [custom_components/owlet/strings.json:17-25](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/strings.json#L17-L25), [custom_components/owlet/translations/en.json:7-14](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/translations/en.json#L7-L14), [custom_components/owlet/translations/fr.json:18-26](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/translations/fr.json#L18-L26) and [custom_components/owlet/translations/uk.json:18-26](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/translations/uk.json#L18-L26). Entity translation definitions are unchanged.

### Release packaging and repository presentation

The new release workflow runs for every pushed tag, checks that the exact tag string equals the manifest version, then changes into `custom_components/owlet` and zips its contents into root-level `owlet.zip`, excluding Python cache paths. It publishes using softprops/action-gh-release@v2 with generated notes and contents-write permission. A tag prefixed `v` fails when the manifest contains only the numeric version; this is intentional strict matching, not automatic normalization. Evidence: [.github/workflows/release.yml:1-35](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/.github/workflows/release.yml#L1-L35).

This supplies the asset name and archive-root structure expected by existing `hacs.json` (`zip_release: true`, filename owlet.zip). Live releases API returned release 2026.8.1 with an owlet.zip asset: [published release](https://github.com/soschlegel/owlet/releases/tag/2026.8.1). The asset was not downloaded or compared with main, and later main commits must not be assumed to appear in that older asset.

The hassfest checkout changes v3 → v4 → v5; the release workflow still uses v4. HACS continues using hacs/action@main and hassfest continues using home-assistant/actions/hassfest@master. The v5 commit title says Node 24 support; this report verifies the action reference only, not the action runtime's Node version. Evidence: [.github/workflows/cron.yml:9-23](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/.github/workflows/cron.yml#L9-L23).

The last commit adds `custom_components/owlet/brand/icon.png`, identified locally as a 256×256 RGBA PNG, 4,737 bytes. It changes presentation/validation assets only. The commit says it fixes the HACS brands check; subsequent successful validation runs support that the current checks pass, but do not prove that the icon alone caused success.

## Complete unique-commit inventory, oldest first

| Commit | Title | Effect |
|---|---|---|
| [9068b27bfda538cf56e3cd409f1e3096b7569e81](https://github.com/soschlegel/owlet/commit/9068b27bfda538cf56e3cd409f1e3096b7569e81) | Aktualisieren von manifest.json | Version only: 2025.4.3 → invalid intermediate 2026.8.q; superseded by next commit. |
| [877613d41e1a81e7c5a8ea8d59c5b2e4f5a4edac](https://github.com/soschlegel/owlet/commit/877613d41e1a81e7c5a8ea8d59c5b2e4f5a4edac) | Aktualisieren von manifest.json | Version only: corrects 2026.8.q → 2026.8.1, retained at head. |
| [a6ffd6ef2b1d6e50c3be8b52716b8c83ad6ac147](https://github.com/soschlegel/owlet/commit/a6ffd6ef2b1d6e50c3be8b52716b8c83ad6ac147) | Bump pyowletapi to 2025.4.10 and fix Home Assistant compatibility | All runtime compatibility, exception, strings, options/reload and release-workflow changes described above; also adapts config-flow tests. |
| [c585573b631584742a288fb885fd21c1150a1abf](https://github.com/soschlegel/owlet/commit/c585573b631584742a288fb885fd21c1150a1abf) | Bump actions/checkout to v4 in hassfest workflow | Maintenance only: cron hassfest checkout v3 → v4; superseded by next commit. |
| [9d97e8dae5095f6c40d29a2a636a9d148938234d](https://github.com/soschlegel/owlet/commit/9d97e8dae5095f6c40d29a2a636a9d148938234d) | Bump actions/checkout to v5 for Node 24 support | Maintenance only: cron hassfest checkout v4 → v5, retained. Does not change release-workflow checkout v4. |
| [b51c6faccae26749253f1d0e02ff90912b764f3c](https://github.com/soschlegel/owlet/commit/b51c6faccae26749253f1d0e02ff90912b764f3c) | Add owl brand icon to fix HACS brands check | Adds the 256×256 local brand icon; retained. |

No unique merge commits and no explicit revert commits exist. The invalid intermediate version `2026.8.q` is absent at head. The v4 change in cron.yml is superseded by v5; v4 in the separate release workflow remains. All other listed changes remain in the head diff. The two manifest-only commits should be treated as one version correction in a behavioral explanation.

## Configuration, entities and backward compatibility

The manifest version changes 2025.4.3 → 2026.8.1; requirement changes pyowletapi==2025.4.1 → ==2025.4.10. Domain `owlet`, cloud_polling classification, codeowner, documentation and issue-tracker URLs are unchanged; the latter still point at upstream. Evidence: [custom_components/owlet/manifest.json:1-15](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/manifest.json#L1-L15).

Config-flow VERSION remains 1. Stored data remains region, username, token, expiry and refresh; initial password remains an input rather than an explicitly saved data field. Options remain scan_interval. There is no migration function or schema bump, and no deliberate entity-registry migration is required by the code diff. The manifest/release version is distinct from config-entry schema version.

`const.py`, `entity.py`, `sensor.py`, `binary_sensor.py` and `switch.py` are byte-identical to upstream at these heads. Supported versions remain [2, 3], regions europe/world, and the default interval is five seconds. Existing unique IDs continue to use serial plus description key, and device identifiers remain domain plus serial. Evidence: [custom_components/owlet/const.py:3-11](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/const.py#L3-L11), [custom_components/owlet/entity.py:25-38](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/entity.py#L25-L38), [custom_components/owlet/sensor.py:36-146](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/sensor.py#L36-L146), [custom_components/owlet/binary_sensor.py:28-169](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/binary_sensor.py#L28-L169), [custom_components/owlet/switch.py:34-90](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/switch.py#L34-L90).

Consequently there is no integration-level addition of Dream Sock support, new vitals, alarm behavior or base-station controls. The existing dependency determines which model properties are populated, so a changed library could still change observed entity availability or values without any entity-file diff. That possibility is unverified, not evidence of a fork feature.

The declared minimum HA in unchanged `hacs.json` remains 2024.1. The modern options implementation needs framework support for automatic config-entry access; the fork does not revise its minimum or show an oldest-supported-version matrix. An upgrade can reuse existing entries on compatible HA, but compatibility with that old advertised minimum is not established. Pinning the newer dependency means installation must resolve that exact release.

## Concrete concerns and suggested fixes

### Medium: token persistence unnecessarily reloads the integration (fork-introduced)

Evidence: listener registration and unconditional reload at [custom_components/owlet/__init__.py:37-109](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/__init__.py#L37-L109); coordinator token persistence at [custom_components/owlet/coordinator.py:28-55](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/coordinator.py#L28-L55). HA's `async_update_entry` treats data changes and option changes as entry changes, then `_async_save_and_notify` schedules every update listener: [HA source:2834-2875](https://github.com/home-assistant/core/blob/1cc3e51cce06be9c2aedac564b3b13134c661fc6/homeassistant/config_entries.py#L2834-L2875).

Scenario: a normal poll returns replacement tokens; the coordinator writes them into entry.data; the listener reloads the whole entry despite unchanged scan_interval. This tears down/recreates platforms and coordinators, causes avoidable cloud discovery/refresh calls and can interrupt availability. Reauth also explicitly reloads after updating data, so the new listener can schedule a redundant reload there. This is not proof of an infinite loop: that would require repeated changing token values after each reload, which was not tested. Fix: compare the polling option with the active interval and reload only on an actual interval change, or use a framework options-only reload mechanism appropriate to the supported HA baseline. Test token-only updates do not reload and interval updates do.

### Low: reauthentication can silently redisplay on non-credentials errors (inherited)

Evidence: [custom_components/owlet/config_flow.py:49-142](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/config_flow.py#L49-L142) lines 135-136 logs the generic exception but never sets errors. Scenario: a network/library failure occurs while submitting the reauth form; the user sees the same form with no explanation. The fork fixes the credentials-specific case but leaves this one. Fix: assign a visible cannot_connect or unknown base error, with explicit transport/auth exception handling as appropriate. Existing `test_reauth_unknown_error` only asserts form and step, allowing this behavior.

### Medium compatibility risk: advertised HA minimum is not reconciled with modern options behavior

Evidence: [custom_components/owlet/config_flow.py:91-164](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/custom_components/owlet/config_flow.py#L91-L164) depends on the base class property, while HACS still advertises 2024.1. On a framework lacking that property, opening options fails at `self.config_entry.options`. The exact cutoff was not researched, so this is a conditional compatibility finding rather than a claim that every 2024 release breaks. Fix: test the actual minimum and raise the metadata floor or provide a deliberate compatibility path. Avoid blindly cherry-picking modern framework assumptions into a fork with a wider support policy.

### Low maintenance gap: functional changes have no runnable standalone test setup here

Evidence: tests import `homeassistant.components.owlet` rather than this repository's `custom_components.owlet` and rely on `tests.common` from HA's test harness. The repository has no pyproject/test dependency setup or local conftest; the only original CI workflow runs hassfest and HACS validation. This does not prove every test assertion is wrong, but passing validators cannot establish that this code's authentication/options behavior was exercised. Fix: establish custom-integration test loading and run lifecycle regressions in CI.

## Tests inspected and verification limits

The fork deletes the two tests for removed email/password exceptions, preserves initial credentials-error coverage, and changes the reauth-password test to inject OwletCredentialsError and expect invalid_credentials. Test changes are narrowly aligned with the exception API update: [tests/test_config_flow.py:56-199](https://github.com/soschlegel/owlet/blob/b51c6faccae26749253f1d0e02ff90912b764f3c/tests/test_config_flow.py#L56-L199).

Existing tests cover setup/unload, replacement tokens, setup auth/connection/no-device/general errors, coordinator errors, sensor and binary-sensor fixtures, config flow, reauth and an options-form submission. The options test uses skip_setup=True and only checks the returned options entry, so it does not exercise the newly registered listener or prove the interval changes on a running coordinator. No new setup CredentialsError regression or token-update/reload guard test was added. There is no switch test file. Existing setup tests also contain historical expectations such as a device name different from current entity.py, another reason not to assume they run unchanged.

Performed locally: parsed all 16 Python source/test files with ast.parse and all 12 JSON files with json.loads; full per-commit patches and aggregate code diff inspected; surrounding runtime/platform/test source read; PNG dimensions inspected. No dependency installation, pytest run, HA instance, cloud login or live device interaction was performed. No claim of operational authentication or sensor correctness follows from this review.

Live gh API reported successful Validate with hassfest runs at the reviewed fork head, including [run 42334546536](https://github.com/soschlegel/owlet/actions/runs/42334546536). The workflow contains hassfest and HACS validators, not pytest. No wait/poll loop was used.

## Candidates for mLupine

1. Port the username-key fix and setup/reauth CredentialsError handling, coordinated with the dependency version actually selected in mLupine. These repair specific failure paths without changing entity identifiers.
2. Port the options-constructor modernization if mLupine's supported HA baseline supplies the property. Apply interval changes promptly, but fix the broad update-listener behavior rather than copying it unchanged.
3. Port the missing no_devices strings. Preserve or improve Ukrainian localization rather than describing the English text as translated Ukrainian.
4. Consider the release zip workflow if mLupine uses HACS zip releases; adapt tag conventions and validate the actual archive. The icon and CI action refresh are maintenance candidates with little user-visible functional value.
5. Evaluate pyowletapi 2025.4.10 separately against mLupine's current dependency and devices. Do not use this fork's commit message as proof of API/endpoint equivalence or bundle obsolete version-only churn into a functional port.

All shared project files, remotes, refs, checkout and other agents' artifacts were left untouched. Analysis clone and auxiliary files are under `/tmp/owlet-soschlegel-z1zRi9`.
