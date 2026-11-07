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


## Superseded dbe6f6c roadmap baseline

### Superintegration validation

Verified 2026-11-07. All three installed Home Assistant runtimes execute the actual custom component. Tests use synthetic HTTP responses and local loopback HTTP, not a live Owlet account.

| Home Assistant | Python | Result | Command |
|---|---|---|---|
| 2024.1.2 | 3.11.16 | 181 passed | `.venv-2024-1/bin/python -m pytest` |
| 2024.12.5 | 3.13.15 | 181 passed | `.venv-min/bin/python -m pytest` |
| 2026.10.2 | 3.14.5 | 181 passed | `.venv/bin/python -m pytest` |

Reproduce dependency installation with `uv pip sync --python ENV/bin/python --require-hashes LOCK`, using requirements-test-2024-1.lock, requirements-test-min.lock, or requirements-test.lock respectively.

Ruff check and format check passed for custom_components, tests and scripts. The unslop-code scan found zero findings. The intermediate pytest plugin emits an existing fixture-loop-scope deprecation warning; no tests are skipped or weakened.

Coverage includes v1 migration, v2 identity and recorder continuity, regional accounts, live options rescheduling, rotated credentials, malformed and late-arriving properties, source-specific expiry, command acceptance/delayed confirmation/timeout/unload, optional historical position, diagnostics redaction, translations and optional automations.

The original independent coder and cross-family reviews identified defects subsequently fixed and covered by regressions. The parent independently reran all three standard test profiles with the checked-in socket restrictions and timeout settings, verified archive members against source, and requested fresh coder and cross-family reviews of the settled implementation. Final review verdicts remain pending. See cross-family-review-decisions.md for dispositions and validation-history.md for earlier evidence.

## Packaging

Build with `python3 scripts/build_release.py`. The deterministic flat HACS ZIP retains licenses, notices, translations, icons and the switch platform. Optional examples are packaged separately. Current checksums:

```text
248fee04cf7a7a2368658e02dfd6dfd9c3f921162923ab01b7b4bbff215c4d63  owlet.zip
a46c97d77e30b378805ade39b1b8a5c8d65918823c2b8296e078de73bd27f5d5  owlet-examples.zip
```

## Delivery and limits

Main commits 343843b and 9bfc92d passed GitHub Hassfest, HACS and the full compatibility matrix. The final consolidation requires a new CI result after its push. No new PR is required. No release/tag or live installation is performed by this consolidation.

HA 2024.1.2 is the tested minimum; reconfigure UI requires HA 2024.4 or newer. Other intermediate versions are not individually tested. Source timestamps and command readback do not prove clinical correctness or physical actuation. Historical body position remains experimental and opt-in, with no verified tummy-code mapping. Real cloud acceptance, phone notification delivery, production database restoration and live HACS upgrade remain unverified.

## Final cross-family lifecycle corrections

F1 and F2 were reproduced using real entity-registry renames. Switch re-add clears its removal latch; body-position removal clears the cached listener target so re-add subscribes again. Regressions verify commands after rename, subsequent position updates, and unload cleanup.

L1: persisted intervals above 3600 seconds remain effective, and can be retained in the options form. New entries still use the normal 5–3600-second range. L2: an HTTP error invalidates both the historical profile and its expiry, allowing resolution on the next cycle instead of waiting for the former five-minute cache deadline.

All 181 tests pass with the standard configuration on all three profiles. Ruff/format and unslop-code pass; packages were rebuilt and checked against source. L3 (late poll after unload) and L4 (service cancellation during unload) remain unconfirmed concerns, not claimed fixes. No speculative cancellation behavior change was made. Independent verification of these corrections remains with the parent reviewer.


## Roadmap implementation and review history

# Validation evidence

Verified 2026-11-07 in the implementation worktree, starting at `dbe6f6c`. The parent owns independent reviews, hosted CI, publication and live HA. This run did not access HA, log in to Owlet or actuate a device.

## Runtime matrix

| Home Assistant | Python | Result | Lock |
|---|---|---|---|
| 2024.1.2 | 3.11.16 | 263 passed in 4.80s | requirements-test-2024-1.lock |
| 2024.12.5 | 3.13.15 | 263 passed in 3.98s | requirements-test-min.lock |
| 2026.10.2 | 3.14.5 | 263 passed in 4.03s | requirements-test.lock |

Each standard run used `python -m pytest` from `/Users/maciej/.t3/worktrees/owlet/t3-a2b49c89`. The interpreters are the existing environments under `/Users/maciej/.t3/worktrees/owlet/t3-e4a2cced`; no files in that checkout were changed. Import inspection confirmed this worktree's `custom_components/owlet/__init__.py` in all three profiles. Each environment passes `uv pip check`. Baseline HA 2026.10.2 passed 181 tests before edits. No tests were skipped, weakened or marked expected failure. The socket guard, Unix-socket permission and 30-second per-test timeout remain in pyproject.toml.

Exact commands, run from the implementation worktree:

```sh
/Users/maciej/.t3/worktrees/owlet/t3-e4a2cced/.venv-2024-1/bin/python -m pytest
/Users/maciej/.t3/worktrees/owlet/t3-e4a2cced/.venv-min/bin/python -m pytest
/Users/maciej/.t3/worktrees/owlet/t3-e4a2cced/.venv/bin/python -m pytest
/Users/maciej/.t3/worktrees/owlet/t3-e4a2cced/.venv/bin/ruff check custom_components tests scripts
/Users/maciej/.t3/worktrees/owlet/t3-e4a2cced/.venv/bin/ruff format --check custom_components tests scripts
```

Reproduce environments with `uv pip sync --python ENV/bin/python --require-hashes LOCK`. The existing intermediate pytest plugin emits its fixture-loop-scope deprecation warning; no assertion is suppressed.

## Reproductions and functional evidence

`tests/test_roadmap_lifecycle.py` reproduces late polls recreating repairs/timers after unload and retained runtime after failed or cancelled platform forwarding. HA 2024.1 permits overlapping manual polls; an event-driven test failed with a single tracked task and passes when all active polls are cancelled and joined. The newer HA coordinator serializes these calls. Cancellation during switch services already propagated correctly and was retained.

`tests/test_roadmap_retry.py` initially reported seven failures and five passes. It now proves account cooldown for 429/5xx/network failures, one failed refresh exchange for waiting callers, Retry-After handling, bounded increasing delays/reset, malformed credential retention, sibling discovery cleanup, deduplicated devices and two-sock request counts. A synthetic discovery performs three GETs for two distinct socks. Three subsequent two-sock cycles add six GETs and only two activation POSTs at one controlled clock time. This is a code request count, not a vendor rate-limit measurement.

`tests/test_roadmap_contracts.py` drives HA flows/services, real registries and the bundled parser. It covers constructor errors, actionable initial/reauth forms, entry-linked polling reauth, exact diagnostic output, nested exception privacy, false-command rejection, partial access exchange, cancellation after refresh rotation, JSON reconstruction from HA's entry serialization, missing/returning devices and a synthetic battery charging spike. This is storage serialization/reconstruction, not a full process restart. Existing upgrade tests still use actual recorder rows and assert unchanged registry identity and metadata IDs.

Two expected error-classification regressions surfaced during implementation: an initial test invoked first refresh outside HA's entry context, and a broad setup sanitizer initially remapped ConfigEntryAuthFailed to retry. The test now uses HA's entry operation, and known HA auth/retry exceptions propagate unchanged. The original auth assertion is retained and passes on all profiles.

`tests/test_api_contract.py` includes actual aiohttp traffic to a local loopback HTTP server through HA platforms in both configured regions. Other cloud tests use queued synthetic HTTP sessions or method mocks. None establishes real Dream/European firmware, physical commands, long-term refresh or clinical correctness. Dashboard tests render HA Jinja templates for disabled, unknown, stale, failed and active states; they do not render the frontend.

## HA 2026.11 attempt

PyPI's newest published pytest-homeassistant-custom-component, 0.13.375, pins HA 2026.10.4. An exploratory hash-locked environment with HA 2026.11.0 and that plugin cannot collect tests. Normal startup fails because httpx is imported before HA's httpx2 alias. Importing HA first reaches a second failure: the plugin imports `_clear_logger_overwrites`, removed from HA's logger component. `uv pip check` also reports the exact-HA plugin mismatch. No assertion, socket guard, plugin source or installed HA source was changed to force a pass. This incompatible experimental lock is not advertised as a supported profile or added to CI.

Temporary evidence: `/tmp/owlet-requirements-current-attempt.lock`, `/tmp/owlet-current-tests.log`. The supplied parent report of a dbe6f6c upgrade on HA 2026.11.0 is separate live evidence; it is not a pass for this new candidate.

## Dependency advisory scope

`pip-audit 2.10.1` queried installed packages in every test environment, including HA and test dependencies. No advisory IDs were ignored and no packages were skipped.

| Installed environment | Packages audited | Affected packages | Advisory findings |
|---|---:|---:|---:|
| HA 2024.1.2 | 101 | 13 | 172 |
| HA 2024.12.5 | 129 | 13 | 223 |
| HA 2026.10.2 | 154 | 2 | 40 |
| HA 2026.11.0 exploratory environment | 157 | 0 | 0 |

[Dependency advisories](dependency-advisories.tsv) records every affected package, version, advisory ID and reported fix version. Findings are not deduplicated across environments. Audit command shape: `uvx pip-audit --path ENV/lib/pythonX.Y/site-packages --progress-spinner off --format json --output REPORT.json`. Nonzero advisory exits are findings, not successful security gates. The bundled Owlet client adds no pip runtime dependency. Old HA pins cannot be updated by this component without changing the host's dependency contract. Keeping the tested 2024.1.2 floor is a compatibility decision and does not endorse its dependency security. The zero-result exploratory environment still has an incompatible test plugin and no successful suite.

## Package and source checks

`scripts/build_release.py` requires the exact 30-file runtime inventory, calendar version, bundled-client requirement list and optional matching tag. It rejects extra household files, missing icons, symlinks and source-byte drift. Twelve package tests exercise those contracts. Licenses, NOTICE, brand provenance and all four existing locales remain installed.

```sh
git archive --format=zip --output=/tmp/owlet-roadmap-source.zip HEAD
python3 scripts/build_release.py --tag 2026.11.0b1 --source-archive /tmp/owlet-roadmap-source.zip
```

The exact Git source ZIP was checked against candidate runtime bytes, and two builds produced identical archives. Every member also matches its source; [member hashes](package-source-sha256.tsv) record that comparison.

```text
8d5e27926ce9ad14929c4344939eb84e87c39f331480f728cbaaa4b2278a0cc0  owlet.zip
09b632e43bd9e349cf55e222f5563286dbce96953717f6520fe38135804537fd  owlet-examples.zip
```

No tag or release was created. The manifest remains `2026.11.0b1` for parent publication decisions.

## Audits and remaining acceptance

Ruff check/format pass. Python tokenization found zero ordinary comments across component, tests and scripts. The unslop-code scanner reports six broad-exception sites and descriptive-name cosmetics. Each exception site was read: four convert errors into sanitized HA errors or flow feedback, one cleans partial setup and reraises, and one logs failed optional activation. No failure is silently discarded. Those boundary catches prevent the reproduced nested-secret leaks. Names include HA's own imported APIs and explicit behavioral test names; shortening them would contradict the requested descriptive naming. No scanner suppressions were added. Independent coder and cross-family review remain with the parent, as requested.

[Roadmap coverage](roadmap-coverage.md) records all 24 dispositions. HA-owned entry-title and registry logs can expose existing identifiers; preserving user titles and IDs rules out claiming universal Core log redaction. No title rewrite, global logger filter, registry cleanup, recorder purge or runtime_data migration is introduced.

Owner-run acceptance remains separate: preserve a private configuration/recorder backup; update the existing entry without deleting it; inspect options and reauth feedback; compare exact entity bindings and effective polling after restart; observe ordinary regional authentication/refresh/recovery privately; verify rollback on the chosen release. Record only versions, region category, anonymous device counts and pass/fail outcomes. Do not deliberately interrupt official monitoring or exercise physical controls for this checklist. Long-term V2/V3, Dream/European, phone delivery and rendered mobile/tablet/theme acceptance remain unverified by this run.

## Parent discovery review corrections

The five new discovery regressions all fail against cf61a6c and pass with bounded workers and device-permission isolation. Full standard suites independently pass 268 tests per profile from `/Users/maciej/Code/owlet`. The frozen cross-family review still targets cf61a6c; final package hashes above predate these corrections and must be regenerated before publication.

## Parent cross-family corrections

All three standard profiles independently pass 277 tests after activation/device-error isolation and platform-cleanup corrections. Eleven focused cases failed against b1a7e27 before the correction; all pass afterward. Unexpected error types are observable without exception payloads. Ruff, formatting and whitespace checks pass. Earlier hashes identify the implementation handoff only, not this corrected candidate; final packages are rebuilt for review/publication.
