# Owlet superintegration implementation plan

Owner: isolated implementation checkout. Parent tracks owlet-ocq and owns review/shipping.

## Acceptance contract

Existing mLupine schema-v2 entries retain entry ID, credentials, options, serial-based device identifiers and every existing entity unique ID, including switches. Migration changes only valid v1 account identities, refuses collisions and future schemas, and never invents region/identity. No registry cleanup. No live account/device or installed HA mutation.

## Ordered implementation

1. Preserve baseline contract and establish runnable HA custom-component test harness. Inspect all nine reports and refreshed public source metadata; compare bundled and external clients. Capture baseline descriptions and test fixtures. Adapt Wiggi26/bypatrick harness to actual custom_components.owlet.
2. Core lifecycle/auth/options/migration fixes. Keep five-second fallback and minimum. Preserve unknown options. Apply options to active coordinators without token-triggered reloads. Persist credentials in failure paths and serialize shared refresh. Verify upgrades and HA registry/history continuity.
3. Robust API client/normalization and freshness/diagnostics plus extra device capabilities. Prefer bundled MIT client if source inspection confirms ownership of parsing/timestamps is necessary. Preserve command protocol and verify readback. Source-specific timestamps, nearest expiry, unknown freshness, tolerant field parsing, bounded retry/backoff, allowlisted diagnostics and dynamic capabilities.
4. Body-position feature and useful optional dashboard/notification artifacts, with known defects fixed. Opt-in historical API, exact DSN/profile association, bounded timestamp/code parsing, cached credentials/profile, separate slow coordinator. Optional examples never installed automatically; explicit startup/recovery notification policy.
5. Compatibility matrix tests, packaging, attribution, final validation. Run installed HA runtimes, fixture HTTP contracts and compatibility regressions. Pin environments. Build and inspect flat HACS ZIP. Record source authors/SHAs, adaptations and exclusions for every fork/change. Run unslop-code and comment audit locally; parent performs independent reviews.

## Evidence and delivery

Decisions: docs/superintegration-decisions.tsv. Adoption: docs/fork-adoption.md. Validation: docs/validation.md. No pushes, releases, PRs, external messages or extra checkouts.

Runtime verification proves HA behavior and synthetic HTTP contracts only. Cloud/device correctness and ambiguous vendor position semantics remain explicitly unverified.
