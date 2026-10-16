# Changelog

All notable changes to Prehnite are documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and intends to use [Semantic Versioning](https://semver.org/) for published releases, with PEP 440 development versions for Python packaging.

## [Unreleased]

### Added
- On-demand private native-pixel inspection CLI (`prehnite inspect --asset ...`) for verified single-slot images and alpha cutouts (#93); fit/1:1 CSS toggle, original bytes, SHA256 double-check, 64-MiB cap, no JavaScript or external resources, default gallery/ZIP unchanged.
- Strictly opt-in local Parquet export for typed aggregate metrics and anonymous per-slot observations (#91), with optional PyArrow dependency, CLI/MCP switches, decimal USD and nullable timing, ZSTD, atomic publication marker, stale/tampered digest checks and Windows/Ubuntu test coverage. No model API/network, raw identifiers, mandatory dependency or default ZIP change.
- Offline production analytics tranche (#6/#89): new self-contained responsive no-script dashboard panels in gallery.html, versioned aggregate-only analytics.json/analytics.csv, delivery/source/aspect cohorts, provider/stage observed-local p95/unknown timing, retry distribution, estimated spend and failure states; ZIP digest/replay verified on synthetic jobs. No claims of calibrated visual quality, actual invoices, Parquet or a public share-safe gallery.
- Proposed batch-objective and Pareto evaluation RFC distinguishing distinct-deliverable production from creative exploration and controlled experiments; specifies offline chart provenance, comparable benchmark metrics and human-quality limitations (#81; planning only, no runtime or readiness credit).
- Versioned typed failure and recovery classification for stage/asset journal entries and offline JSON/CSV/HTML telemetry (#86 / C10): distinguish unrecoverable missing remote receipts from inspectable saved request IDs, never automatically resubmit paid calls, and preserve legacy export contracts.
- Reproducible 90-slot synthetic dry run on Windows/Ubuntu CI: 60 generated local sources, 30 demo-provider generations, 18 named cutouts, injected per-asset failure, safe pause at slot 30, actual child-process crash after slot 65, explicit resume, 108-image ZIP SHA256 receipt and byte-stable local replay; JSON evidence and clearly hypothetical cost projections (#41). No real image-quality or invoice claims.
- Durable detached MCP job ownership, reconnect-safe status, cooperative pause/cancel/explicit resume, OS-backed launch/worker locking and stage-boundary stop checkpoints; no PID-based process killing and no claims of immediate remote cancellation (#38, development PR).
- Explicitly opt-in, privacy-scoped immutable stage cache keyed by exact input/model/version/options and SHA256; cached paid inference requires extra consent and pinned revision, with no retry of ambiguous prior paid requests (#18).
- Offline batch economics and attempt-timing telemetry: append-only SQLite attempt evidence, per-stage retries/p95 local durations, reserved USD per accepted asset and explicitly unknown provider invoices (#34). Synthetic 90-asset regression fixtures; no paid runs.
- Deterministic local provenance.json with verified output geometry/SHA256, provider-stage trace, requested seeds and privacy-minimized source/prompt hashes; changed original source bytes block unsafe resume (#35).
- Clean wheel/sdist metadata and isolated wheel-install smoke checks on Ubuntu and Windows CI, including init/doctor/validate/run, optional-extras isolation and development-only packaging (#39).
- No-overwrite `prehnite init` demo scaffolding and secret-safe `prehnite doctor` checks, including an opt-in localhost-only ComfyUI health probe (#37); no GPU/Windows installation certification.
- Controlled fixed-rubric A/B then B/A positional-bias audit with identity-remapped scores, abstention tracking, deterministic JSON and synthetic zero-cost demonstration (#63); does not claim calibrated judge quality.
- Self-contained offline `gallery.html` visual result browser, with hashed accepted-image thumbnails, checkerboard cutouts, intermediate previews and escaped rejection notes; packaged in the ZIP without CDN/JavaScript or network dependencies (#33).
- Native 1:1 pixel crop evidence (corners, center, optional manual focal anchor), annotated downsampled overview, hash-verified PNG/JSON manifest and offline `prehnite crops` CLI (#26). Crops are evidence, not automatic quality scores.
- Offline ComfyUI API-format generation/upscale/segmentation node-map fixtures and fake local HTTP queue tests (#22); invalid graph mappings now fail before uploading a local source image.
- Typed model-provider capability registry and fail-fast preflight checks for required stages, supported tiers/options, upload permissions and unimplemented adapters; user-managed prices explicitly marked non-live (#21).
- MIT-licensed Prehnite Python package and command-line interface.
- Strict manifest/profile contracts, output validation, persistent batch journal, opt-in inference routing and estimated cost tracking.
- Synthetic demo provider with offline tests, JSON/CSV/HTML reports and verified ZIP export.
- Optional ComfyUI API, fal inference, Haiku judging and local MCP adapters (real-model behavior remains unverified).
- Agent coordination issue, documented development roadmap and initial CI.
- GitHub Issues-based agile tracker, contributor templates, canonical package version source and release-process documentation (governance PR).
- Granular 61-unit evidence ledger with validated dependencies, generated progress dashboard and GitHub-linked work packages.
- Original Prehnite vector mark, improved first-run documentation and truthful provider status matrix.

### Fixed
- Deterministic ZIP ordering, fixed metadata timestamps and SHA256 archive receipt cover accepted outputs and bundled reports; repeated export no longer varies with local file mtimes (#36).
- Validate optional judge verdicts as complete finite numeric schemas with consistent winners/ties, reject malformed cached decisions and abstain on independent-rubric disagreement; fake position-bias tests added (#25, offline only).
- ComfyUI prompt IDs are persisted before queue dispatch, with fail-closed history recovery after connection loss, cancelled/interrupted job recognition, and bounded atomic downloads; no unverified local-model quality claims (#23).
- Validate SAM 3.1 mask geometry and grayscale/alpha semantics before cutout acceptance; reject ambiguous multiple masks and undocumented endpoint aliases (#20; mocked only).
- Atomic staging/promotion for provider images, selected images and ZIP delivery; SHA256 verification on accepted stage reuse and exports; invalid accepted assets fail closed instead of silently shipping corrupted bytes (#16). Legacy batches without output digests require revalidation.
- fal generation uses model-specific size payloads (Klein explicit image_size vs FLUX.3 Image ratio/tier); queue fixtures validate response parsing, unknown-model refusal and resume without re-uploading source images (#19).
- Offline subprocess crash-injection tests cover paid-call journal boundaries, safe resume and cross-process lock release (#15); real provider billing is not tested.
- Fail-closed recovery of uncertain paid calls, single-batch worker locking, and mandatory positive pricing estimates ([PR #10](https://github.com/interzettel/prehnite/pull/10)).

- Reconciled progress evidence after the README and tracker merge; modernized Node 24 GitHub Actions and removed Pillow alpha-coverage deprecation.

### Security
- Default no-paid-inference policy; cloud uploads are opt-in.
- Strict output path confinement, model-licensing separation and untrusted input handling.

### Known limitations
- No production-verified real-model quality gates, 4K GPU benchmark or invoice reconciliation yet.
- This section is a development log, **not release notes for a published v0.1.0**.
- No GPU-validated and paid-model integration has been completed.

<!-- Move entries into a dated [X.Y.Z] section only after a real release is approved. -->
