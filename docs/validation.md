# Superintegration validation

Verified 2026-11-07. All three installed Home Assistant runtimes execute the actual custom component. Tests use synthetic HTTP responses and local loopback HTTP, not a live Owlet account.

| Home Assistant | Python | Result | Command |
|---|---|---|---|
| 2024.1.2 | 3.11.16 | 177 passed | `.venv-2024-1/bin/pytest -o addopts='' -q` |
| 2024.12.5 | 3.13.15 | 177 passed | `.venv-min/bin/pytest -o addopts='' -q` |
| 2026.10.2 | 3.14.5 | 177 passed | `.venv/bin/pytest -o addopts='' -q` |

Reproduce dependency installation with `uv pip sync --python ENV/bin/python --require-hashes LOCK`, using requirements-test-2024-1.lock, requirements-test-min.lock, or requirements-test.lock respectively.

Ruff check and format check passed for custom_components, tests and scripts. The unslop-code scan found zero findings. The intermediate pytest plugin emits an existing fixture-loop-scope deprecation warning; no tests are skipped or weakened.

Coverage includes v1 migration, v2 identity and recorder continuity, regional accounts, live options rescheduling, rotated credentials, malformed and late-arriving properties, source-specific expiry, command acceptance/delayed confirmation/timeout/unload, optional historical position, diagnostics redaction, translations and optional automations.

The original independent coder and cross-family reviews identified defects subsequently fixed and covered by regressions. The consolidation owner inspected those findings against the final code; no new independent reviewer was spawned. See cross-family-review-decisions.md for dispositions and validation-history.md for earlier evidence.

## Packaging

Build with `python3 scripts/build_release.py`. The deterministic flat HACS ZIP retains licenses, notices, translations, icons and the switch platform. Optional examples are packaged separately. Current checksums:

```text
d083e1ba74734a2dacd6903a3cf71c700e35236bc1e59bb66a63b3c207916a04  owlet.zip
a46c97d77e30b378805ade39b1b8a5c8d65918823c2b8296e078de73bd27f5d5  owlet-examples.zip
```

## Delivery and limits

Main commits 343843b and 9bfc92d passed GitHub Hassfest, HACS and the full compatibility matrix. The final consolidation requires a new CI result after its push. No new PR is required. No release/tag or live installation is performed by this consolidation.

HA 2024.1.2 is the tested minimum; reconfigure UI requires HA 2024.4 or newer. Other intermediate versions are not individually tested. Source timestamps and command readback do not prove clinical correctness or physical actuation. Historical body position remains experimental and opt-in, with no verified tummy-code mapping. Real cloud acceptance, phone notification delivery, production database restoration and live HACS upgrade remain unverified.
