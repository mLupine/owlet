# Validation evidence

Candidate `2026.11.0b3` requires **Home Assistant 2026.10.2 or newer**. The supported automated profile is HA 2026.10.2 / Python 3.14.5, pinned in `requirements-test.lock`. Both 2024 profiles and their locks were removed at the user's request. Historical results and prior release evidence remain in `validation-history.md`.

## Verification

All **283 tests pass** on the retained profile after removing the old migration API fallback, private options-entry constructor, legacy recorder fixture ordering and conditional blueprint/icon/concurrent-poll assertions. The long-interval options regression now enters through HA's real options-flow manager. Existing migration, registry/recorder continuity, reauth, token, polling, lifecycle and device tests remain in the suite.

Ruff check/format and whitespace checks pass. The integration still uses Python 3.11+ syntax; the test project's Python minimum is 3.14 because the selected HA baseline requires it. No unrelated syntax rewrite or runtime ownership refactor was introduced.

Reproduce:

```sh
uv venv --python 3.14.5
uv pip sync --require-hashes requirements-test.lock
.venv/bin/python -m pytest
.venv/bin/ruff check custom_components tests scripts
.venv/bin/ruff format --check custom_components tests scripts
python scripts/build_release.py --tag 2026.11.0b3
```

The deterministic component and examples archives have these SHA256 hashes:

```
517fec2486a1bb849bfe835262c746c6d22f95e6aa54507f7ee969445707ae2e  owlet.zip
ab5c79a26b63d8922ed912060484ab2295a24f00676b6742abb1ae7263edcfde  owlet-examples.zip
```

The package builder validates runtime/example inventories and manifest/tag agreement. `package-source-sha256.tsv` records source member hashes. Final independent review and hosted CI results are reported separately.

## Compatibility and limits

The v1-to-v2 account migration remains: old Owlet installations can upgrade on supported HA without recreating entries or changing entity IDs. This is distinct from compatibility with old HA APIs. Existing custom options and recorder history remain preserved. HACS and both notification blueprints declare 2026.10.2 as their minimum.

The earlier live installation evidence concerns dbe6f6c on HA 2026.11.0, not this candidate. Long-term cloud/device behavior, physical actuation, all regional variants and rendered dashboards remain unverified. The published HA 2026.11 test plugin is incompatible, so no green 2026.11 suite is claimed. `dependency-advisories.tsv` is the historical audit of complete HA/test environments, including retired profiles; dropping old profiles does not remediate advisories in users' HA hosts. This integration adds no pip runtime dependencies.

Both independent reviewers approved the runtime/API cleanup at e52ecf1. The cross-family reviewer required correcting the HACS info.md minimum; that is fixed and a regression now enforces version agreement across HACS metadata, README, info.md and both blueprints. The long-interval options test now saves through HA and checks persisted custom options. Final suite:284 passed. No live HA deployment was performed.
