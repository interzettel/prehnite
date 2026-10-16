# Changelog

All notable changes to Prehnite are documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and intends to use [Semantic Versioning](https://semver.org/) for published releases, with PEP 440 development versions for Python packaging.

## [Unreleased]

### Added
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
