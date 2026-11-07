# mLupine/owlet versus ryanbdclark/owlet

Reviewed 2026-11-07 using live GitHub API metadata and a separate temporary clone. Shared project files, refs, remotes and checkout were untouched. No live Home Assistant or Owlet access was performed.

## Practical result

This fork has one functional change: Home Assistant can configure the same email address once per Owlet region, rather than once across the entire integration. Existing entries receive a configuration-entry identity migration. Nothing in the fork adds sensors, changes polling, upgrades the Owlet API library, fixes readings, or changes device commands.

For example, upstream uses `parent@example.com` as the configuration unique ID. Consequently, adding that email for `world` after adding it for `europe` aborts as already configured, before authentication. The fork uses `europe_parent@example.com` and `world_parent@example.com`, permitting both flows to authenticate independently. Repeating the same region and email still aborts. Email case folding remains in place; email whitespace handling is unchanged.

This permits separate regional accounts that happen to use the same email. It does not move an Owlet account between backend regions, establish that both regions contain devices, or provide region-based isolation for entities that report the same serial number. Backend behavior belongs to an unchanged external library and cloud service.

## Exact comparison and complete commit inventory

| Item | Value |
|---|---|
| Fork/default branch | `mLupine/owlet`, `main` (verified repository metadata) |
| Fork head | `2f68ea0c8831039003c1f02d498f67fa53f5a95c` |
| Upstream/default branch | `ryanbdclark/owlet`, `main` (verified repository metadata) |
| Upstream head | `f8e0067a1e74a523b0bb4b0841b25404a6926ca8` |
| Merge base | `f8e0067a1e74a523b0bb4b0841b25404a6926ca8` |
| Ahead / behind | 1 / 0 |
| GitHub comparison status | ahead |
| Changed files | 6; 158 insertions, 5 deletions |

[Live branch comparison](https://github.com/mLupine/owlet/compare/ryanbdclark:main...main). [Pinned comparison](https://github.com/mLupine/owlet/compare/f8e0067a1e74a523b0bb4b0841b25404a6926ca8...2f68ea0c8831039003c1f02d498f67fa53f5a95c).

The complete fork-only inventory is:

| SHA | Title | Effect and classification |
|---|---|---|
| [`2f68ea0c8831039003c1f02d498f67fa53f5a95c`](https://github.com/mLupine/owlet/commit/2f68ea0c8831039003c1f02d498f67fa53f5a95c) | Fix duplicate integration entries for same email across different regions (#1) | Region-prefix configuration IDs, raise entry schema version to 2, migrate version-1 entries, update fixture and add three tests. Functional commit dated 2026-02-24; one parent, the exact upstream head. |

There are no fork-only merge commits, reverts, release-only commits, repeated maintenance commits, or fork changes subsequently removed. The `(#1)` suffix does not make this a merge commit; its Git object has one parent. All upstream history is shared. These conclusions follow from GitHub compare metadata and the local parent/range/diff, rather than interpreting the title alone.

## Implementation and source evidence

### New account identity

`OwletConfigFlow.VERSION` changes from 1 to 2. In `async_step_user`, the old `username.lower()` unique ID becomes `f"{region}_{username.lower()}"`. `_abort_if_unique_id_configured()` remains immediately afterwards and before authentication. Region selection was already required and already restricted to `europe` or `world`; the fork changes no input fields or validation rules.

[Fork config_flow.py lines 33–71](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/config_flow.py#L33-L71), compared with [upstream config_flow.py lines 33–69](https://github.com/ryanbdclark/owlet/blob/f8e0067a1e74a523b0bb4b0841b25404a6926ca8/custom_components/owlet/config_flow.py#L33-L69).

Authentication still receives the original username, password and selected region. Created entry data still stores region, original username and returned tokens; title remains the email, and options retain the existing polling default. This means two entries for the same email look alike by title even though their IDs differ. The fork does not label titles with region. [Creation/data path, lines 69–93](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/config_flow.py#L69-L93).

### Existing-entry migration

A new `async_migrate_entry(hass, config_entry)` in `custom_components/owlet/__init__.py` logs the old version, then for version 1 reads `data[region]` with a `world` fallback, prefixes the existing unique ID, and updates `unique_id` and `version=2` together through `hass.config_entries.async_update_entry`. It returns `True` after the conditional. It leaves entry data, options, title and entry ID alone.

[Migration, lines 38–62](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/__init__.py#L38-L62).

The migration uses the old unique ID rather than reconstructing it from the stored username. For entries created through upstream's normal flow, that preserves the already lowercased email. Migration is effectively single-pass for normal data because the version is updated: a subsequent invocation with version 2 does not add another prefix. Unexpected or future versions also return `True` without changes; explicit rejection of unsupported future versions would make this defensive boundary clearer. Exact framework downgrade handling was not inspected here.

The region fallback only changes the new ID. It does not add a missing region into entry data. Setup still requires `entry.data[CONF_REGION]`, so a malformed entry without region would receive a `world_` ID and still fail setup. Upstream's normal schema requires region, making this a malformed-data edge case rather than an established normal-upgrade failure. [Setup, lines 65–75](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/__init__.py#L65-L75).

### Test and fixture changes

`tests/__init__.py:31–35` changes the reusable `MockConfigEntry` to version 2 with `europe_sample@gmail.com`. `tests/const.py` adds the equivalent `world` input. No device fixtures change.

[Test entry helper](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/tests/__init__.py#L24-L44), [input constants](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/tests/const.py).

Two flow tests exercise creating Europe then world with the same email and rejecting a repeated Europe/email combination. The successful cross-region test asserts entry creation and stored region, but not the exact new unique IDs. The migration test creates a version-1 Europe entry, runs integration setup with API mocks, and asserts version 2 and the expected prefixed ID.

[Flow tests, lines 220–290](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/tests/test_config_flow.py#L220-L290), [migration test, lines 148–180](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/tests/test_init.py#L148-L180).

## Dependencies, entities and configuration compatibility

| Surface | Fork delta |
|---|---|
| Entry schema version | 1 → 2 |
| Configuration unique ID | lowercased email → region + underscore + lowercased email |
| Existing-entry migration | New; prefixes stored old ID |
| Manifest package version | Unchanged `2025.4.3` |
| External package requirement | Unchanged `pyowletapi==2025.4.1` |
| User schema, options, translation strings | Unchanged |
| Device support | Unchanged `SUPPORTED_VERSIONS = [2, 3]` |
| Poll interval | Unchanged default 5 seconds, UI minimum 5 seconds |
| Entity inventory and unique IDs | Unchanged |
| Sensor units, state mappings, commands | Unchanged |
| Coordinator/authentication/reauthentication | Unchanged except new migration runs before normal setup |
| HACS metadata, README, changelog, CI | Unchanged |

[Manifest](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/manifest.json#L1-L15), [constants](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/const.py), [options validation](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/config_flow.py#L153-L176).

Device identity remains `(DOMAIN, sock.serial)`. Entity IDs remain serial plus description key: [device_info lines 25–37](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/entity.py#L25-L37), [sensor line 146](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/sensor.py#L146), [binary_sensor line 132](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/binary_sensor.py#L132), [switch line 72](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/switch.py#L72).

Consequently, ordinary upgrade should preserve devices/entities and automations referring to their existing entity IDs: the migration does not rewrite any registry ID. This is a source-level expectation, not a registry migration verified against a real HA installation. Entry IDs continue to key coordinator storage (`__init__.py:118`), so the account unique-ID change itself does not replace those runtime storage keys.

A downgrade to upstream returns to schema version 1 without a reverse migration supplied by this fork. Treat rollback as requiring a configuration backup/restore or explicitly tested downgrade procedure; do not assume dropping old files back over the component is enough. Manifest version remains unchanged despite the persisted schema change, so package-version reporting alone cannot distinguish these installations. The README and manifest still point users to upstream documentation/issues and do not document the fork migration.

## Concrete concerns and recommendations

### Medium: checked-in tests target a different integration module path

The repository implements `custom_components.owlet`, but both inherited and newly added tests import or patch `homeassistant.components.owlet`; they also require HA-core-style `tests.common`. This is directly visible in `tests/__init__.py:7–21`, the new flow tests' patch targets, and the new migration test. The repository contains no test harness/configuration that copies the custom component into the HA core namespace. In an ordinary custom-component test environment, mocks therefore target a different module or imports fail, so these new tests cannot establish this installed custom component works. This is inherited infrastructure debt extended by the fork, not proof that production code is broken.

Fix: provide a custom-component test harness, enable custom integrations, import/patch `custom_components.owlet`, and use the harness's supported fixtures. Alternatively explicitly document and automate a HA-core checkout transplant. Add a CI pytest job; current CI only runs hassfest and HACS validation. [Workflow evidence](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/.github/workflows/cron.yml).

### Medium, conditional: two regional entries can collide on device/entity identity

If both configured regions expose the same serial number, account IDs are different but all device and entity IDs still collide. Separate coordinators can still be created for each entry, each polling its region, while entity identity cannot distinguish them. Exact HA registry collision behavior needs runtime testing; it is not safe to claim both sets of entities operate independently. Evidence is the serial-only identity constructors linked above plus per-entry coordinator construction at `__init__.py:103–120`.

Fix depends on domain intent: either deliberately share one physical device and suppress duplicate discovery/polling, or namespace entity/device identity if regional serials are not globally unique. Blindly prefixing entity IDs would itself require registry migration and could break automations. Verify real backend overlap first. This concern becomes newly reachable through the fork's feature, although the identity implementation is inherited.

### Low: migration accepts missing or unexpected old identities

For a version-1 entry with `unique_id=None`, migration stores `europe_None` rather than reconstructing the email. With missing region it labels the ID `world_...` without repairing required setup data. Imported/manual/corrupted entries could therefore receive misleading identities or remain unloadable. Normal upstream-created entries have required region and an email unique ID, so this is robustness work, not evidence of a widespread regression.

Fix: explicitly validate legacy data or rebuild identity from validated stored username/region, and add malformed-data tests. Do not silently invent a region merely to continue migration.

### Medium, inherited: authentication-error reporting references the wrong data key

`OwletCoordinator._async_update_data` catches `OwletAuthenticationError` but builds its message with `self.config_entry.data[CONF_EMAIL]`. Entry creation stores `CONF_USERNAME`, not `CONF_EMAIL`. For the normal entry data visible in this repository, this error path can raise `KeyError` while trying to raise `ConfigEntryAuthFailed`, obscuring the intended reauthentication signal. This code is identical upstream and is not fixed by the fork.

[Coordinator lines 41–55](https://github.com/mLupine/owlet/blob/2f68ea0c8831039003c1f02d498f67fa53f5a95c/custom_components/owlet/coordinator.py#L41-L55), compared with the creation-data link above. Candidate fix: use `CONF_USERNAME` consistently and test the exception path with actual flow-created data. Whether and when the pinned library raises this exception was not inspected.

## Verification performed and limits

Read the entire six-file patch and surrounding flow, setup, migration, coordinator, entity identity, manifest, constants, test helpers, tests and CI source. Live API compare and local Git agree on the single unique commit and exact parent. `git diff HEAD^ HEAD --check` passed. No pytest suite was executed: `homeassistant` is not installed in the analysis interpreter, and the checked-in tests assume external HA-core test infrastructure absent from this repository. No dependency installation or device interaction was attempted.

The added tests provide useful intended-behavior specifications, but there is no demonstrated green runtime test result here. Missing focused coverage includes world-region migration, migration followed by same-region duplicate rejection, case-insensitive duplicates across setup/migration, preservation of data/options/entry ID, repeat migration, malformed entries, actual entity registry preservation and overlapping devices across regions. CI metadata validation does not substitute for these checks.

The external `pyowletapi` source and Home Assistant framework internals were not inspected. Region routing, backend account semantics, token behavior and serial uniqueness are therefore external assumptions, not verified fork changes.

## Candidate work worth bringing into mLupine

Because mLupine is the fork under review and already contains every upstream commit at the captured heads, there is no missing upstream commit to port. The other eight research reports may identify candidates, but this review cannot endorse unseen changes.

Prioritize a runnable custom-component test harness and migration/duplicate/registry coverage, then the inherited `CONF_EMAIL` exception-path fix. Decide overlapping-device semantics from real evidence before changing entity IDs. Publish a distinguishable package version and migration/rollback note if distributing the fork. Keep the existing region-aware account identity feature: it addresses a precise setup restriction with a small production patch, but its runtime correctness is not established merely by having tests in the tree.
