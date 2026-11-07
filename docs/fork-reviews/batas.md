# batas/owlet: independent fork review

Reviewed live GitHub metadata and isolated cloned source on 2026-11-07. Scope is the custom Home Assistant integration in ryanbdclark/owlet, not a comparison against the current Home Assistant Core repository.

## Practical result

This is a small authentication/dependency compatibility fork plus release packaging work. It does not add sensors, change polling, extend device support in integration code, change switch behavior, or introduce a new configuration format. The 15 unique commits are not 15 user features: three are merges and seven repeatedly edit the same release workflow.

1. The installed library pin moves from `pyowletapi==2025.4.1` to `2025.4.10`. This is the broadest possible runtime change, but library internals were not inspected here. No claim about new Owlet cloud endpoints, Dream Sock support, region fixes, data interpretation, or authentication success follows merely from that version number.
2. Setup now handles `OwletCredentialsError` alongside `OwletAuthenticationError`, and removes imports of the older email/password error classes. Configuration and password reauthentication present a generic invalid-credentials error rather than a field-specific email/password error.
3. Releases can receive an `owlet.zip` containing integration files directly at archive root. HACS already requested that filename upstream; this fork adds the producer.
4. Metadata directs support/documentation to batas and reports integration version `2026.8.7`. Existing entity IDs and stored config should retain their integration-side shape.

## Exact comparison

| Item | Value |
|---|---|
| Upstream | `ryanbdclark/owlet`, default branch `main` |
| Upstream SHA | `f8e0067a1e74a523b0bb4b0841b25404a6926ca8` |
| Fork | `batas/owlet`, default branch `main` |
| Fork SHA | `6b36398ffd326b5eb2908cdf52b003a107534a17` |
| GitHub compare | ahead 15, behind 0; status `ahead` |
| Merge base | upstream head (fork contains the entire upstream head history) |
| Moving compare | https://github.com/ryanbdclark/owlet/compare/main...batas:owlet:main |
| Immutable compare | https://github.com/ryanbdclark/owlet/compare/f8e0067a1e74a523b0bb4b0841b25404a6926ca8...batas:owlet:6b36398ffd326b5eb2908cdf52b003a107534a17 |

Live metadata was obtained with `gh api repos/{owner}/owlet`, branch endpoints and the cross-fork compare endpoint. Local Git confirmed both head SHAs and the complete commit/diff inventory. Seven files differ: 47 added lines and 62 removed lines. Raw metadata and isolated clone are under `/tmp/owlet-batas-8tLMMo/`; no shared project files, refs, remotes or checkout were modified.

## Implementation by feature

### Dependency and authentication

[Manifest](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/manifest.json#L1-L15) changes the requirement, version, codeowner, documentation and issue URL. The integration remains `owlet`, config-flow enabled and `cloud_polling`.

[`async_setup_entry`](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/__init__.py#L37-L94) still creates `OwletAPI` from region and stored token/expiry/refresh plus HA's session; authenticates, persists refreshed tokens, calls `get_devices(SUPPORTED_VERSIONS)`, builds one coordinator per DSN, performs initial refresh, and forwards binary sensor/sensor/switch platforms. Only exception imports and the authentication exception tuple change. At lines 55–59 a credentials exception now produces `ConfigEntryAuthFailed`. Connection failure remains retryable through `ConfigEntryNotReady`; no devices still returns false.

[`OwletConfigFlow.async_step_user`](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/config_flow.py#L49-L89) still authenticates then calls `validate_authentication()`. It removes `OwletEmailError` -> username/invalid_email and `OwletPasswordError` -> password/invalid_password mappings; `OwletCredentialsError` -> base/invalid_credentials already existed upstream and remains. Both authenticate and validation exceptions are inside the same try block. Other exceptions still log and show unknown. Username normalization/duplicate checking, Europe/world selection, entry title and token dictionary storage remain unchanged.

[`async_step_reauth_confirm`](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/config_flow.py#L106-L142) replaces password-error handling with credentials-error handling and changes the UI error location to `base`. It still requests only a password, reuses stored username/region, persists returned tokens, reloads the entry and aborts with reauth_successful. No email editing or schema migration is added.

The deleted imports are consistent with the fork's stated compatibility intention. Whether the pinned library actually exports every remaining class and what inheritance/conditions its exceptions use were not independently verified. Treat that as a dependency contract to test, not a proven cloud fix.

### Release and validation automation

[Validation workflow](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/.github/workflows/cron.yml#L1-L24) upgrades checkout v3 to v4 for hassfest and adds checkout v4 before HACS validation. Push, pull request and daily schedule triggers stay unchanged; hassfest and HACS actions still follow mutable master/main refs. There is no pytest job.

[Release workflow](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/.github/workflows/release.yml#L1-L23) is new: release-created trigger, Ubuntu runner, contents-write permission, checkout v4, zip all files from `custom_components/owlet`, upload using softprops/action-gh-release v2. The final `../../owlet.zip` path is correct relative to that directory, placing the file in repository root for the upload step. Archive root includes manifest/config flow/platforms/translations, rather than an extra `owlet/` directory.

[Existing HACS configuration](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/hacs.json#L1-L7) already says zip_release=true and filename=owlet.zip; advertised HACS minimum remains 1.32.1 and HA minimum remains 2024.1. The fork did not demonstrate compatibility against that minimum.

Live release listing showed v20260809, v20260808, v20260806, v20260805 and v20260803 with an owlet.zip asset; v20260807 and v20260804 had no assets. Assets were not downloaded or compared to source. Their presence is packaging metadata, not runtime verification. Release tags use a different naming scheme from the manifest's 2026.8.7; do not assume tag names encode distinct manifest versions.

### Unchanged entities, configuration and schemas

The complete source diff contains no changes in `sensor.py`, `binary_sensor.py`, `switch.py`, `entity.py`, `coordinator.py`, `const.py`, strings or translations. [Constants](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/const.py) still allow device versions 2/3 with five-second default polling. Options still coerce an integer and enforce minimum five seconds. ConfigFlow.VERSION remains 1; no migration function or new entry keys are introduced.

[Sensor platform](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/sensor.py) still conditionally creates entities based on library properties: battery percent, oxygen saturation, heart rate, battery minutes, signal strength, temperature, movement/bucket and conditional sleep/oxygen-average entities. Existing charging availability and serial-property unique IDs remain. [Binary sensors](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/binary_sensor.py) retain charging, alerts, sock status and awake handling. [Switch](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/switch.py) still uses `Sock.control_base_station(bool)` and the existing charging availability rule. [Device metadata](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/entity.py) retains serial identifiers and MAC connections. Library-side changes could still affect properties or discovered devices; unchanged integration code does not guarantee identical observable results.

## Complete unique-commit inventory

All SHAs below are unique relative to upstream main. Effects were determined from patches, including intermediate workflow states.

| SHA / title | Effect and final status |
|---|---|
| [`69b8f58f23c9541efe1cb6bdf88727b89d17de24`](https://github.com/batas/owlet/commit/69b8f58f23c9541efe1cb6bdf88727b89d17de24) fix: update integration to 2026.8.1, bump pyowletapi to 2025.4.10, fix HACS workflow, add release workflow | Bumps manifest 2025.4.3 -> 2026.8.1 and dependency 2025.4.1 -> 2025.4.10; updates validation checkout; introduces release zip workflow and changelog. Initial zip had owlet/ prefix, superseded later. |
| [`42f9db04cc05401901d7ddfbb080ed5faf90201b`](https://github.com/batas/owlet/commit/42f9db04cc05401901d7ddfbb080ed5faf90201b) fix: add blank line between changelog entries | Formatting only: blank line after new changelog entry. Retained. |
| [`f9b6116a1bd9448599fc92505d0e7ae5d6949659`](https://github.com/batas/owlet/commit/f9b6116a1bd9448599fc92505d0e7ae5d6949659) Merge pull request #1 from batas/copilot/update-integrations-release | Merge #1; brings first two commits into main. No separate feature or conflict-resolution patch. |
| [`54884d0a0e8b8c980bd38d23358568ac8d28644e`](https://github.com/batas/owlet/commit/54884d0a0e8b8c980bd38d23358568ac8d28644e) fix: update manifest URLs and codeowners to batas/owlet, bump version to 2026.8.7 | Repoints owner/docs/issues to batas and bumps version 2026.8.1 -> 2026.8.7. Metadata-only; retained. |
| [`03e314cdc7e96f9f98534775ecc0b6586ea79ae6`](https://github.com/batas/owlet/commit/03e314cdc7e96f9f98534775ecc0b6586ea79ae6) Merge pull request #2  | Merge #2; integrates metadata commit. No separate runtime change. |
| [`b91dc3e8c88219ce76b8e457cc027d1dfd8dede4`](https://github.com/batas/owlet/commit/b91dc3e8c88219ce76b8e457cc027d1dfd8dede4) Update release.yml | Adds contents: write permission needed for release asset upload. Retained. |
| [`ed77107e98c593b28b55dbadb90c5a9acf97ec20`](https://github.com/batas/owlet/commit/ed77107e98c593b28b55dbadb90c5a9acf97ec20) Update release.yml | Changes zip input from owlet/ to . within custom_components. Intermediate layout superseded. |
| [`0e597156c470561f42cff9219aa28f351cc1055b`](https://github.com/batas/owlet/commit/0e597156c470561f42cff9219aa28f351cc1055b) Update release.yml | Changes output to ../../owlet.zip while still inside custom_components, placing zip above repository root, inconsistent with upload filename. No longer present. |
| [`3d9f3ddbc9323c3427ce07dcbf518b6d50b8b723`](https://github.com/batas/owlet/commit/3d9f3ddbc9323c3427ce07dcbf518b6d50b8b723) Update release.yml | Reverts preceding output-path change back to ../owlet.zip. Exact workflow-tree reversal, though title is generic rather than Revert. |
| [`8f667cc9a947209e073c874214b9a292e6521d10`](https://github.com/batas/owlet/commit/8f667cc9a947209e073c874214b9a292e6521d10) Update release.yml | Uses ./owlet manifest.json from custom_components. Root manifest path is absent there; partial archive risk. Superseded. |
| [`45f706c4d87739b77031d250dedee390dd6767d1`](https://github.com/batas/owlet/commit/45f706c4d87739b77031d250dedee390dd6767d1) Update release.yml | Creates build_dir, copies integration files then repository-root manifest.json. That root file does not exist in the inspected tree, so cp would fail. Superseded. |
| [`b74cc121e43e7056a86308fa23a44bcbcf1754c2`](https://github.com/batas/owlet/commit/b74cc121e43e7056a86308fa23a44bcbcf1754c2) Update release.yml | Replaces build_dir approach with cd custom_components/owlet and zip ../../owlet.zip .; final retained layout. |
| [`2c39d927165bc777b326fe03f1ca456c9b6ae41a`](https://github.com/batas/owlet/commit/2c39d927165bc777b326fe03f1ca456c9b6ae41a) Handle latest pyowletapi auth errors | Removes old exception imports, catches credentials errors in setup, removes email/password branches in user flow, updates changelog and tests. Reauth initially still maps credentials to password/invalid_password; finalized next. |
| [`625b6d02e7521683ca7f6c628c53414848647d61`](https://github.com/batas/owlet/commit/625b6d02e7521683ca7f6c628c53414848647d61) Finalize pyowletapi auth compatibility | Changes reauth credentials mapping to base/invalid_credentials; removes obsolete separate email/password tests, renames generic credentials tests and adjusts expected error. Retained. |
| [`6b36398ffd326b5eb2908cdf52b003a107534a17`](https://github.com/batas/owlet/commit/6b36398ffd326b5eb2908cdf52b003a107534a17) Merge pull request #3 from batas/copilot/fix-imports-for-pyowletapi | Merge #3; integrates auth compatibility pair. No separate runtime feature. |

There are no explicitly titled revert commits and no standalone version-only commit: the metadata bump also changes ownership URLs. There is one effective workflow reversion and several overwritten packaging experiments. All three merges have the same resulting tree as their merged topic tip, so they add history rather than extra resolved code.

## Compatibility and migration implications

Existing config entries retain region, username, api_token, expiry and refresh; the password still is not stored in entry data. Domain, config-flow version, entity unique IDs and device identifiers are unchanged. No delete/re-add or registry migration is indicated by the integration diff. Reauthentication remains the recovery path for rejected stored credentials. Error wording becomes less specific but matches a consolidated credentials exception model.

This fork occupies the same custom_components/owlet path and domain as upstream; these are replacement implementations, not independently installable parallel integrations. Preserve config entries when replacing files. The library upgrade should be validated as part of the same change as exception handling: applying only the initial dependency bump leaves old imports in place until the later auth commits. The chronological gap contains an internally inconsistent compatibility attempt.

## Concrete findings and risks

### Medium: inherited polling auth failure raises KeyError instead of intended auth failure

[`OwletCoordinator._async_update_data`, lines 50–53](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/coordinator.py#L41-L55) catches OwletAuthenticationError but formats its message using `entry.data[CONF_EMAIL]`. Entries created by this integration use CONF_USERNAME, not CONF_EMAIL ([creation](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/config_flow.py#L77-L85)). On a normal stored entry lacking email, that branch raises KeyError before ConfigEntryAuthFailed is constructed. Intended reauthentication routing is lost. This is inherited upstream code, not newly introduced by batas. Fix: use CONF_USERNAME consistently; test a polling-time auth error using a realistic entry.

### Medium, conditional dependency-contract gap: credentials failures during polling are not explicitly routed to reauth

Setup now treats both authentication and credentials errors as auth failures, but the unchanged coordinator only explicitly catches OwletAuthenticationError. If the new library raises an OwletCredentialsError during `Sock.update_properties()` that is not also an authentication-error subclass, it reaches the generic OwletError handling (if a subclass) or escapes. That can mark the poll failed without starting reauth. The integration-side asymmetry is proven; actual exception hierarchy and emission require library inspection. Fix after verifying hierarchy: route both auth classes consistently, with regression coverage.

### Low: inherited reauth unexpected errors give no visible explanation

[`async_step_reauth_confirm`, lines 133–141](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/custom_components/owlet/config_flow.py#L133-L142) logs generic exceptions without assigning an error, and an authenticate() result of None similarly redisplays an error-free form. A connectivity failure can look like a password submission doing nothing. This is inherited control flow; the fork changes only the explicit credential branch. Add an appropriate base error, and decide how no-token success responses should be handled after checking the dependency contract.

### Low: release identity is ambiguous

The auth fix changes code and changelog under the existing 2026.8.7 manifest version introduced earlier. Multiple release tags exist with differently named tags and the same possible manifest version. This makes installed-version diagnosis weaker. It is not proof that HACS updates fail. Give each shipped implementation a distinct manifest version and verify the release asset against its tag.

## Tests and verification limits

[Updated flow tests](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/tests/test_config_flow.py#L56-L71) assert generic invalid_credentials; [reauth test](https://github.com/batas/owlet/blob/6b36398ffd326b5eb2908cdf52b003a107534a17/tests/test_config_flow.py#L140-L158) expects the same base error. Two obsolete email/password-specific tests are deleted, rather than replaced with new end-to-end library tests. Existing tests cover setup, coordinator, sensors, binary sensors and options with mock API responses; no switch test file is present. `tests/test_init.py` was not updated to cover the newly caught OwletCredentialsError.

The tests import and patch `homeassistant.components.owlet`, while shipped source lives in `custom_components/owlet`. They also depend on Home Assistant's `tests.common` and fixture-loading conventions. There is no standalone pyproject/requirements/conftest harness in this tree to establish that these tests exercise this custom integration as checked out. Thus their presence must not be represented as a green runnable suite.

Verification performed: full branch diff and every nonmerge patch inspected, surrounding setup/config/coordinator/platform source read, all Python files parsed with ast.parse successfully, git diff --check passed. No pytest execution, HA startup, cloud login, physical-device test, dependency source audit, release-asset inspection or GitHub workflow run verification was performed. Nothing here proves real-world authentication, minimum-HA compatibility or measurement correctness.

## Candidate ports to mLupine

1. Port the consolidated exception handling together with an explicitly selected and inspected pyowletapi version, if mLupine still imports removed email/password errors. The useful change is the contract alignment, not blindly copying a 2025 library pin.
2. Port the final flat owlet.zip release build if mLupine uses HACS zip releases and lacks equivalent packaging. Keep its own URLs, owner and release scheme; discard the seven intermediate workflow experiments.
3. Port checkout-before-HACS-validation if absent. Keep current project action policies rather than copying mutable action refs without thought.
4. Fix the inherited coordinator username/email bug and align polling credentials handling while integrating the auth work. Add tests against the actual custom_components import path and real dependency exception types.
5. Preserve entity/config schemas unless the other fork has an explicit reason to change them. There is no new entity feature in batas to port.

No mLupine source was inspected in this report, so these are conditional candidates rather than claims that changes are missing there.
