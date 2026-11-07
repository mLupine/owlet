# Validation evidence

Release candidate: `2026.11.0b2`, verified 2026-11-07. The independent coder and cross-family reviews both returned SHIP for `0150ea2`. The parent then broadened discovery isolation from 403 to device-level 400/404, parameterized the HTTP and actual HA setup/reload tests, and changed the version. No account/entity IDs or schema changed.

## Final checks

All three full standard profiles pass **283 tests**: HA 2024.1.2 / Python 3.11.16, HA 2024.12.5 / Python 3.13.15, and HA 2026.10.2 / Python 3.14.5. The parent ran each from the final main checkout, using `python -m pytest` with checked-in socket restrictions and assertions. Ruff check/format and whitespace validation pass.

Reproduce with the corresponding hash-pinned `requirements-test-2024-1.lock`, `requirements-test-min.lock`, or `requirements-test.lock`, then run `python -m pytest`. The intermediate pytest plugin emits an existing fixture-loop-scope deprecation warning.

Both independent reviewers independently ran 277 tests per profile before the six added discovery-status cases. The cross-family reviewer additionally ran nine scratch probes per profile for retry recovery, explicit 429, authentication propagation and discovery cleanup. The parent reproduced five discovery failures and eleven activation/cleanup failures against their respective prior sources before fixing them. Tests exercise HA entries, services, registries and recorder rows; HTTP tests include local loopback traffic as well as mocked cloud sessions.

## Packages

Two builds produced identical bytes. The builder enforces the exact runtime/example inventories, license and brand assets, tag/manifest agreement and source archive equality. Member hashes are recorded in `package-source-sha256.tsv`.

```
8b14f1b44564c3cd3ba60436487b22fc9c24e3b8556175e7e3e6fdf57f1595f5  owlet.zip
09b632e43bd9e349cf55e222f5563286dbce96953717f6520fe38135804537fd  owlet-examples.zip
```

Verify the committed source with:

```sh
git archive --format=zip --output=/tmp/owlet-source.zip HEAD
python scripts/build_release.py --tag 2026.11.0b2 --source-archive /tmp/owlet-source.zip
```

## Support and evidence limits

HA 2024.1.2 remains the tested compatibility floor, not a security recommendation. `dependency-advisories.tsv` records unsuppressed audit findings in the complete HA/test environments. Owlet adds no pip runtime dependencies and cannot upgrade HA-owned packages. The exploratory HA 2026.11 environment had no audit findings, but its published test plugin could not collect because of incompatible HA imports and an exact-version mismatch. No successful 2026.11 suite is claimed; details remain in `validation-history.md`.

The earlier dbe6f6c installation was verified live on HA 2026.11.0, retaining 62 existing live entity IDs, adding 12 diagnostics and keeping five-second polling. That is evidence for the previous version, not this candidate. Long-term cloud/token behavior, physical actuation, all regional/device variants, rollback of this candidate, rendered dashboards and phone delivery remain unverified. Dashboard tests render HA templates, not the frontend.

Existing user titles and identifiers can still appear in HA-owned logs. Integration error handlers log useful categories/type names without raw exception payloads. Ukrainian translation remains excluded. See `roadmap-coverage.md` for all 24 issue dispositions and `roadmap-decisions.tsv` for the implementation decisions. Hosted CI and publication status are reported separately, rather than inferred from local tests.
