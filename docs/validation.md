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
