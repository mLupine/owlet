# Superintegration validation

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
