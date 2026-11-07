# Superseded validation snapshots

Archived on 2026-11-07 before the cross-family behavior corrections. Every result, package hash, default, and pending-review statement below belongs to an earlier source snapshot. None describes the current package. [validation.md](validation.md) is the sole current status.

# Superintegration validation

Verified on 2026-11-07 in `/Users/maciej/.t3/worktrees/owlet/t3-e4a2cced`, branch `feat/owlet-superintegration`. No new commit, push, PR, release, external message, live Owlet login or installed HA/device change was made. The parent owns beads issue `owlet-ocq`; it remains open for review and shipping.

## Installed HA test profiles

| Profile | Python | Home Assistant | Custom-component plugin | pytest | Result |
|---|---|---|---|---|---|
| Minimum | 3.11.16 | 2024.1.2 | 0.13.88 | 7.4.4 | 153 passed in 3.73 s |
| Intermediate | 3.13.15 | 2024.12.5 | 0.13.195 | 8.3.3 | 153 passed in 1.77 s |
| Current test profile | 3.14.5 | 2026.10.2 | 0.13.373 | 9.0.3 | 153 passed in 2.26 s |

These runs followed `uv pip sync --require-hashes` using the corresponding lock. `uv pip check` passed for all three environments, with 101, 129 and 154 installed packages respectively. The standalone external pyowletapi package was removed from the current environment by lock synchronization; the tests exercise the bundled implementation.

The original imported/fixture-adapted baseline had 19 failures and 11 passes before runtime changes. Its main failures included unsupported modern options assignment and HA-Core fixture assumptions. The retained tests now import `custom_components.owlet` and load local fixtures. Registry unique IDs replace generated-name assumptions, so the tests work on both area-prefix conventions. Invalid old unload calls and obsolete entity counts were corrected.

Minimum-profile DNS dependencies pin pycares 4.5.0. A newer unconstrained pycares 5.2.1 starts a native shutdown thread which the old plugin's cleanup assertion rejects. This is an environment compatibility pin, not a suppressed cleanup check. The old HA runtime also found a real missing `@callback` on historical-position expiry; that implementation defect was fixed.

## Reproduce

Run these commands in the isolated checkout:

```sh
uv venv --python 3.11.16 .venv-2024-1
uv pip sync --python .venv-2024-1/bin/python --require-hashes requirements-test-2024-1.lock
.venv-2024-1/bin/python -m pytest
uv venv --python 3.14.5 .venv
uv pip sync --python .venv/bin/python --require-hashes requirements-test.lock
.venv/bin/python -m pytest
uv venv --python 3.13.15 .venv-min
uv pip sync --python .venv-min/bin/python --require-hashes requirements-test-min.lock
.venv-min/bin/python -m pytest
.venv/bin/ruff check custom_components tests scripts
.venv/bin/ruff format --check custom_components tests scripts
.venv/bin/python scripts/build_release.py
```

Exact final pytest output is in [test-results-current.txt](test-results-current.txt) , [test-results-minimum.txt](test-results-minimum.txt) and [test-results-2024-1.txt](test-results-2024-1.txt). Full dependency lock generation commands are recorded at the top of each lock. Runtime source parses using Python's 3.11 grammar. Ruff check and format check passed across all 31 Python files.

## What the tests establish

- HA loads the actual custom component and all three platforms. Both regional endpoint selections run through the real aiohttp client against an ephemeral loopback HTTP server.
- V1 migration and v2 upgrades preserve entry IDs, credentials, unknown options, serial device IDs, user entity IDs/names/icons, the switch registry entry, existing recorder rows and one recorder metadata ID across repeated reloads.
- Invalid/missing/future/colliding migrations are refused. Normalized duplicate detection also catches legacy v2 account IDs containing whitespace without rewriting their identities. Region reconfiguration updates the same entry.
- An options UI save changes actual elapsed-time polling. Credential saves do not reload platforms or repeat authentication. Missing/malformed legacy intervals recover to five seconds.
- Actual Firebase/mini-token/sign-in HTTP-response contracts, concurrent expiry refresh, concurrent rejected tokens, one-retry rejection, 429/5xx classification, Retry-After and token persistence through setup/poll failures are exercised. Failed polls never become faster than a long configured interval.
- V2 mixed-age vitals, independent V3 statuses, event timestamps, nearest expiry, missing timestamps, repair recovery and charging semantics are tested. Malformed fields, JSON, bool-as-number, nonfinite numbers and unknown sleep codes cannot manufacture valid readings. Missing-first/later-present entities appear once.
- Switch service success requires matching readback; mismatches raise an HA error. The original command payload and restricted supported writes are verified. Activation publication and cancellation are separate from primary reads.
- Diagnostics omit identifiers, tokens, unknown options and raw future fields. Body-position tests cover exact DSN association, ambiguity rejection, cached profiles/identity, configured timezone, bounded codes, sample pairing/age, independent polling, expiry and cancellation on unload.
- HA's blueprint and automation schemas accept the expanded examples on all three runtimes. Template tests cover off-to-on, unavailable/unknown recovery and explicit startup policy. Dashboard YAML parses. Device notification delivery and browser rendering are not asserted.

## Package evidence

`dist/owlet.zip` contains 28 component files at archive root. [package-inventory.txt](package-inventory.txt) lists them. It contains the switch, manifest, all three existing locales, local brand provenance, Apache license, NOTICE and bundled-client MIT license. It excludes bytecode, virtual environments, tests, account state and extra directory prefixes.

Final SHA-256 values:

```text
4aee0444e3bb86c0a005375973f7a2a96430396b902224484c06b03c81bb16a1  owlet.zip
48a0616a8c5834ea31b27cab354ba843c8df8ea71e33c220ab1598bd7ad536dc  owlet-examples.zip
```

Two builds from the final component source have identical checksums. ZIP integrity and required paths are checked by the builder. HACS retains `zip_release: true`, filename `owlet.zip`, and the tested HA minimum 2024.1.2. The release workflow checks tag/manifest agreement and requires the test matrix before attaching packages. Workflows were prepared locally, not executed on GitHub.

## Source and quality checks

All nine live public branch heads match the archived reports. Selected commit authors were read from GitHub's Git commit metadata. The [adoption ledger](fork-adoption.md), [SHA inventory](fork-adoption.tsv), [decisions](superintegration-decisions.tsv) and NOTICE document attribution and exclusions.

The unslop-code scan of the integration reports zero findings and score zero. A tokenize-based audit found no Python comments after the local no-comments pass; docstrings remain. No review subagent was spawned, as instructed. The parent still needs the independent coder/cross-family review.

No commits were created because the session developer hook explicitly states `Git authority: no git operations in this context`. This also prohibited git ref refresh. Live GitHub commit endpoints and exact-SHA source archives were used instead. The parent must stage coherent units and create attributed commits before shipping.

## Limits

The tests prove HA behavior, synthetic HTTP contracts and loopback client behavior. They do not establish public Owlet service acceptance, physical actuation, clinical correctness, real phone delivery, actual HACS upgrade execution, production database restore or compatibility with every HA/Python version between the tested endpoints.

The optional historical position labels remain source-derived and experimental. No verified bounded tummy-code mapping exists, so unknown codes remain unknown. Epoch seconds and aware ISO sample times are supported; millisecond epochs are rejected. Cached DSN/profile associations are rechecked after five minutes, so account reassignment can take that long to be reflected.

Serial identity remains the compatibility contract. Separate regional accounts returning the same serial share the existing HA identity. Distinct physical devices with a duplicate serial cannot be represented independently without a separately reviewed registry migration. No new namespace or cleanup is introduced here.

## Parent review corrections

The initial package and 148-test evidence above predate review corrections. The parent fixed change-only V2 state handling, never-observed vital health, optional Firebase identity acquisition blocking primary access, and noncontiguous coauthor trailers. Added five regression cases; 87 focused tests passed. All three final profiles pass 153 tests; package hashes above include these corrections and the compatibility adjustments below.


## HA 2024.1 compatibility correction

The verified floor is HA **2024.1.2**, using Python **3.11.16** and pytest-homeassistant-custom-component **0.13.88**, whose published metadata pins that HA version. HA 2024.1.0 and 2024.1.1 are untested; HACS and optional blueprint metadata honestly declare 2024.1.2. The advertised 2024.1.0 baseline had the same missing ConfigFlowResult export and was not proof of support.

The runtime now uses `homeassistant.data_entry_flow.FlowResult`, exported by old and current profiles. Migration checks the supported `async_update_entry` signature: current HA receives `version=2`; old HA assigns the mutable entry version before updating identity through the framework. Existing migration refusal, identity and recorder behavior assertions remain intact. Blueprint singular `trigger`/`action` keys and `platform` declarations validate on all profiles without changing notification policy.

The old recorder plugin requires its database URL fixture before HA construction; a fixture dependency wrapper provides that order only when recorder is requested on 2024.1. The old requirements explicitly include recorder manifest dependencies `fnv-hash-fast==0.5.0` and `psutil-home-assistant==0.0.1`. No behavior assertion was removed, skipped or weakened. The pytest asyncio fixture-loop setting was removed because the oldest plugin predates it; the existing function-scoped default applies. All three suites still pass.

Primary evidence: [HA 2024.1.2 flow result source](https://github.com/home-assistant/core/blob/2024.1.2/homeassistant/data_entry_flow.py), [config-entry source](https://github.com/home-assistant/core/blob/2024.1.2/homeassistant/config_entries.py), [recorder requirements](https://github.com/home-assistant/core/blob/2024.1.2/homeassistant/components/recorder/manifest.json), and [plugin release metadata](https://pypi.org/pypi/pytest-homeassistant-custom-component/0.13.88/json). Installed exact-version source was inspected for framework signatures and fixture behavior.

CI now explicitly includes Python 3.11.16 with `requirements-test-2024-1.lock`. Local `uv pip check`, Ruff check and format checks pass. Two final package builds match byte for byte. CI itself and live vendor/hardware behavior remain unverified.

## Second parent review correction

Fixed invalid-but-present vitals being considered healthy, preserved discovered generation across empty first telemetry, and cancelled/joined optional body-position work during failed multi-device setup. Added five regression cases. The original unknown sleep-state behavior remains intact. Updated packages supersede all prior hashes; see dist/SHA256SUMS.

Parent independently ran the full post-correction matrix: HA 2024.1.2: 158 passed in 2.63s; HA 2024.12.5: 158 passed in 2.09s; HA 2026.10.2: 158 passed in 2.26s. Ruff passed. Rebuilt component SHA-256: a72ad194c022600f2b465e4ce0a465389cf09784286973536d1f44b6aba06ad6. Independent final re-review remains pending.
