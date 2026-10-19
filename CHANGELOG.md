# Changelog

All notable changes to Prehnite are documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and intends to use [Semantic Versioning](https://semver.org/) for published releases, with PEP 440 development versions for Python packaging.

## [Unreleased]

### First real local image/cutout and source productization (2026-10-18)

- Record one local owner-authorized **768×1024 SDXL lamp source**, real GroundingDINO/SAM2 segmentation (8.994 s including load/inference; 2,533 MiB sampled peak VRAM), CPU-only alpha refinement and **independent artifact-specific visual acceptance of Candidate A**. Original rejected-generation and failed-segmentation history is intact. No private weights/images/reports were committed ([dated public evidence](docs/LOCAL_LAB_MILESTONE_2026-10-18.md)).
- **Merged source only**: [PR #159](https://github.com/interzettel/prehnite/pull/159) adds fail-closed, read-only resource observations; [PR #161](https://github.com/interzettel/prehnite/pull/161) adds opt-in `cutout-qa`/`cutout-accept` CLI, configurable CPU alpha candidates, true mask topology and evidence-bound review records. The three synthetic pass/blocked/unknown resource→QA tests from temporary [PR #162](https://github.com/interzettel/prehnite/pull/162) were retained in #161 before merge. Post-merge `main` CI run [39153867726](https://github.com/interzettel/prehnite/actions/runs/39153867726) passed **25/25 jobs**.
- Update README, roadmap, release matrix, handover and runbooks to distinguish **private demonstrated real-model execution**, **reusable merged development source** and the **still-unreleased, unbundled local model/runtime configuration**. The historical accepted alpha file is not byte-identical to the new QA module's CPU candidate; no approval was reassigned. The frozen 61-unit and atomic acceptance trackers stay unchanged pending their broader evidence.
- Remaining: opt-in Engine→QA end-to-end trial on a separately authorized different object, independent visual review, genuine execution/compatibility receipt, Windows symlink host-permission limitation, existing Ruff debt, model rights and representative hardware/batch evidence. No automatic inference authorization, PyPI version publication or general production-readiness claim.

### P08-A01 environment and installed-weight rights evidence (2026-10-19)

- Add a sanitized, read-only [#24](https://github.com/interzettel/prehnite/issues/24) evidence record for the local segmentation environment: Windows/WSL identities, GPU and driver observations, distinct driver/PyTorch CUDA versions, installed package versions, and verified SHA256/source revisions for GroundingDINO, SAM 2.1, BERT tokenizer/encoder and the pinned ComfyUI-SAM2 node. Official model cards and repository licences support Apache-2.0 terms; this is provenance review, not legal clearance.
- This evidence was captured when the frozen atomic tracker was **15/73**. Subsequent independent [S04-A02 credit](https://github.com/interzettel/prehnite/pull/168) raised development `main` to **16/73**, and independently reviewed [P08-A01 evidence](https://github.com/interzettel/prehnite/pull/166) subsequently earns one more original atomic completion, reaching **17/73 (23.29%)**. The P08 parent remains blocked on actual hardware benchmarks. No model was loaded, inference or GPU benchmark performed, or private paths/weights published. See [P08-A01 evidence](docs/P08_A01_ENVIRONMENT_AND_RIGHTS.md).

### P08-A04 compatibility profile by model size (2026-10-19)

- Add a versioned public compatibility decision table and machine-readable profile ([`docs/COMPATIBILITY_PROFILE.md`](docs/COMPATIBILITY_PROFILE.md), [`docs/compatibility-profile.v1.json`](docs/compatibility-profile.v1.json)) that separates one historical **observed successful** RTX 4070 Laptop 8,188 MiB run from a later **observed blocked** system-RAM preflight, and records larger SAM/detector variants, quantization, SDXL segmentation, other GPU tiers, WSL execution and repeated runs as **unknown**. The 2,533 MiB sampled peak is not presented as a minimum VRAM requirement; no runtime estimate is promoted to measurement.
- Add CPU-only consistency tests preventing unmeasured configurations from being labelled successful. This is a decision-record change only: no model load, inference, GPU benchmark, package install or atomic progress edit. The original P08-A04 acceptance was independently reviewed and its [evidence PR #170](https://github.com/interzettel/prehnite/pull/170) merged. The separately recorded original-task credit advances the **unchanged 73-task register to 19/73 (26.03%)**, after unrelated S04-A03 had reached 18/73. The P08 parent and measured-repeatability tasks remain open.

### P08-A02 bounded benchmark blocked at startup (2026-10-19)

- Record a sanitized blocked-attempt page ([`docs/P08_A02_BENCHMARK_BLOCKER.md`](docs/P08_A02_BENCHMARK_BLOCKER.md)): preflight passed and the CC0 backpack source was verified, but the one authorized ComfyUI startup never opened `/system_stats`; the supervisor timed out at **122.703 s**, no checkpoint loaded, **0 prompts** were submitted, peak sampled VRAM was **117 MiB**, and cleanup left no listener. This is not an OOM or model-rights failure and produces no cold/warm inference measurements.
- No completion credit, atomic edit, model/package change, release or historical-artifact change. P08-A02 remains blocked; P08-A03 is not started. A fresh, separately authorized attempt after startup diagnosis is required.

### P08-A02 benchmark session blocked in SAM2/yapf startup import (2026-10-19)

- Record a sanitized blocked benchmark-session page ([`docs/P08_A02_BENCHMARK_YAPF_BLOCK.md`](docs/P08_A02_BENCHMARK_YAPF_BLOCK.md)): preflight passed, but the startup never reached `/system_stats` (timeout **122.469 s**, child return **124**, **0 prompts**, **0 model loads**, peak startup VRAM **559 MiB**, no listener/remaining processes).
- The diagnostic stack capture at 30/60/90 s repeatedly showed the `ComfyUI-SAM2` custom-node import blocked in `local_groundingdino/util/slconfig.py` → yapf → lib2to3 grammar dump → `tempfile.NamedTemporaryFile`. The immediate/proximate cause is proven; the underlying OS temporary-file stall and the nondeterministic earlier successful startup are not. No cold/warm metrics exist, no atomic credit, no P08-A03, no release or tracker change.

### P08-A02 final cold/warm benchmark evidence (2026-10-19)

- Record a sanitized final benchmark page ([`docs/P08_A02_FINAL_BENCHMARK_EVIDENCE.md`](docs/P08_A02_FINAL_BENCHMARK_EVIDENCE.md)): one startup, exactly two prompts, no retry/third prompt. Ready **10.0 s**; cold **7.562 s**, warm **0.727 s**; observable cold model-load interval **4.0 s**; cold post-load derived **3.562 s**; sampled peak VRAM **2,582 MiB**; no OOM/traceback.
- The Windows YAPF cache stall was avoided with a child-scoped disposable writable platformdirs cache; validation passed (`YAPF_IMPORT_OK`, `CACHE_WRITE_OK`), parent environment restored, original cache preserved. Prompt IDs, output hashes, all required node types and clean shutdown are recorded. The narrow P08-A02 metric acceptance was independently reviewed and [evidence PR #177](https://github.com/interzettel/prehnite/pull/177) merged. The laptop's historical **19/73** snapshot preceded unrelated [S04-A04 #178](https://github.com/interzettel/prehnite/pull/178) at 20/73; independently awarded P08-A02 credit now moves the original tracker to **21/73 (28.77%)**. No P08-A03, release or additional inference is authorized by this documentary evidence. See [evidence](docs/P08_A02_FINAL_BENCHMARK_EVIDENCE.md).

### P08-A03 offline repeatability preparation (2026-10-19)

- Add a hardware-free, fail-closed P08-A03 contract: one-startup/three-identical-run plan, profile and telemetry schema, no-retry/no-duplicate/no-overwrite run controller, and simulated fallback scenarios for insufficient RAM/VRAM/commit, startup timeout, missing nodes, inference failure/termination, unknown outcome and cleanup failure. Review hardening now validates actual measured preflight floors, one-supervised-startup receipts, timezone-aware chronology, 120/300/900/60-second ceilings, cleanup evidence and hash-provenance boundaries; missing fields, booleans, NaN/infinity, duplicate indexes and unsafe reported passes fail closed.
- Add `scripts/p08_a03_offline.py` with read-only `plan`, `simulate-fallbacks` and `validate` commands, a synthetic fixture and **98** offline tests, including equality/one-step-beyond thresholds and adversarial missing/provenance cases. The public validator always reports that private bytes were not independently rehashed and marks synthetic-origin evidence as hardware-ineligible; real-origin evidence requires a separate attestation declaration. No ComfyUI startup, model load, CUDA inference, prompt or real OOM occurred. This is preparation, not P08-A03 completion; the task remains **blocked**, the tracker remains **21/73 (28.77%)**, and real hardware execution requires fresh owner authorization. See [preparation](docs/P08_A03_OFFLINE_PREPARATION.md).

### Added
- Reusable post-segmentation cutout contract: explicit source/target/workflow/model bindings, configurable CPU alpha candidates with nearest-foreground RGB decontamination, seven separate evidence stages, technical QA, and create-only independent visual acceptance records. Existing Engine remains the job lifecycle owner; no automatic visual acceptance or inference is added (`docs/LOCAL_CUTOUT_PIPELINE.md`).
- Optional strict operator-declared implicit segmentation dependency SHA256 manifest for human-reviewed source cutout batches. Hashes privately staged GroundingDINO/SAM2/BERT weights, configs and tokenizer files without loading them; binds receipt to new batch identity and rechecks before cutout. Legacy handoffs unchanged, runtime-loaded bytes/graph completeness/licensing not certified (#156).

### Added
- Explicit hash-bound, generation-disabled human-reviewed source handoff: verifies original PNG, original review document and structured typed receipt before new batch journal creation; performs one local cutout with the actual target phrase, preserves original rejected batch, and stages output as `review_pending` rather than accepted. No cloud/paid/automatic retry or model install (#134).


### Fixed
- Allow an explicit ComfyUI segmentation `target_input` (`text` default, `prompt`, or `value`) consistently through graph preflight, recipe-bound verification and local adapter, rejecting unknown fields or missing graph inputs before local uploads. This unblocks real GroundingDINO/SAM2 target routing once separately licensed nodes and weights are installed; no runtime proof or model download (#134/#135).

### Added
- Explicit schema-v2 multi-file ComfyUI model bindings for owner-selected transformers, text encoders, VAEs and auxiliary weights; SHA256 and exact graph-reference coverage for recognized weight file extensions, changed-byte resume refusal, private create-only manifest and stable legacy schema-v1 receipts. Runtime-loaded weights, undiscoverable custom-node dependencies and third-party rights remain unverified (#135).

### Added
- Separate native-1K local ComfyUI `prehnite-micro` preview.2 recipe and one-asset fixtures, true 768×1024 at 3:4 (not a renamed 4K output), exact target/output geometry checks, no silent resize, paid-provider fallback or changed preview.1 batch receipts (#134/#132). Actual 8 GB GPU/model runtime remains unverified.

### Added
- Private create-only `prehnite trial-evidence`: verifies real generated/cutout image geometry, RGBA alpha transparency, file SHA256, hardware observations and optional **operator-supplied** time/VRAM readings while explicitly withholding independent cutout quality/model-rights certification (#134/#32). No inference, file mutation or network calls.

### Changed
- Start the next development series at `0.1.0a2.dev0` after the immutable public `0.1.0a1` release. Version change alone does not publish a new package; subsequent alpha requires a new reviewed release candidate and guarded publishing workflow.


### Added
- Offline create-only `prehnite micro-setup` for SHA256-bound, owner-supplied ComfyUI workflow/model input bindings and explicit local-use term acknowledgement; strict micro profile compatibility and tamper/overwrite guards, without model downloads or inference (#135).
- One-asset no-provider-call `prehnite trial-plan` for local and opted-in fal.ai smoke tests with explicit maximum operator budget, attempt/variant restrictions and clearly **unverified** price assumptions; owner first-GPU/API runbook and reusable YAML examples (#134/#132).

### Changed
- Documented the successful first public alpha release and added cross-platform clean-install verification against the actual PyPI wheel and its audited SHA256; source version remains 0.1.0a1.

## [0.1.0a1] - 2026-10-17

**First public developer alpha.** [Published on PyPI](https://pypi.org/project/prehnite/0.1.0a1/) and [released on GitHub](https://github.com/interzettel/prehnite/releases/tag/v0.1.0a1) on 2026-10-17 using manually authorized Trusted Publishing, with the exact same checked wheel/sdist hashes. This is an installable local-first orchestration engine and synthetic quality-evidence stack, not a production-ready image generator or certified 4K model pipeline. Physical GPU/third-party model rights, human-accepted cutout quality and real hosted API billing remain unverified.


### Changed
- Consolidated the Riso identity commentary into `docs/BRAND_PALETTE.md`, made Changelog/Versioning accessible from README navigation, and updated the recipe architecture/roadmap/status to match the merged experimental local micro execution bridge. Physical GPU/model rights/quality gates remain open (#143).
- Separated public PyPI alpha publishing from ordinary CI: dedicated manually dispatched, same-SHA CI-artifact-verified `publish.yml`, owner-reviewed `pypi` environment, annotated tag, short-lived OIDC upload and GitHub prerelease after success; requires updating the owner's existing pending PyPI publisher from `ci.yml` to `publish.yml` before first upload. No new license, inference quality claims or automatic publishing.

### Added
- Manual, tokenless PyPI publishing preparation (#144): PyPI-specific accurate release description/project metadata, offline wheel/sdist content and version audit, strict Twine validation and inspectable candidate artifacts in ordinary CI; OIDC release job requires owner-dispatched main-only alpha, existing annotated matching tag, all CI gates and a GitHub `pypi` environment reviewer before the first authorized upload. The packaging-preparation PR itself did not tag, publish or bump the version; the separate release workflow subsequently completed the first alpha upload.
- Experimental local ComfyUI recipe/engine bridge (#133): upfront and pre-run SHA256 checks, strict recipe/profile and graph model-reference compatibility, atomic SQLite per-batch recipe identity and refusal of changed/unbound/legacy resumes; no hardware or live-model performance claims.
- Read-only offline micro recipe resolver: operator-supplied ComfyUI API graph and checkpoint file hashing, explicit local-use terms acknowledgement, reproducible resolved-input digest and refusal of unsafe paths/mismatched bytes (#135). No downloads, model execution, verified rights or per-batch journal integration.
- Read-only offline hardware doctor (`prehnite hardware`) with source-labeled OS/CPU/RAM/disk and optional NVIDIA-SMI VRAM observations, explicit unsupported/unknown accelerator states and synthetic platform tests (#134). No weight download, GPU benchmark, performance tier certification or inference.
- Versioned read-only `prehnite-micro` and `prehnite-macro` recipe blueprints (#132/#133), strict registry/DAG/maturity/privacy/budget validation, canonical SHA256 identity, and offline CLI/test coverage; no inference, weights, downloads or hardware quality claims.
- Source-dated external model/weight rights inventory and deterministic registry coverage checker (#40, R06-A02), distinguishing hosted API access, software licenses, optional checkpoint terms and training restrictions; all model and redistribution permissions remain unapproved pending human review.
- Offline CycloneDX dependency SBOM and exact installed-version snapshot with transitive Python package closure, known license-review exceptions and separate Windows/Ubuntu synthetic CI artifacts (#40, R06-A01). A metadata signal never certifies third-party rights or universal hash-pinned builds.
- Offline WEARHOUSE Review Studio result intake (#28/#32): untrusted ZIP or autosave-folder schema/status/counter validation, SHA256 receipts and reviewed RGBA alpha PNG verification; create-only private JSON + text repair-triage without user photos or private notes, independently annotated gold or false mask-quality claims. Synthetic security/round-trip tests on Windows and Ubuntu.
- Explicit opt-in, per-target opaque product cutout repair staging (#31, S05-A04): connect existing journal-backed local fringe repair to Engine.cutout without nested locks, preserve selected source/cutout outputs, journal review-only SHA receipts and fail closed for unqualified materials; no image-quality acceptance, extra provider spending or release gate credit.
- Frozen 73-task, 19-parent atomic delivery register (#126) with PR-sized acceptance criteria, separate verified-parent/atomic progress dashboard, recent merge evidence and CI guards against false completion, denominator drift and stale generated SVG/Markdown; original 61-unit milestone score unchanged.
- Owner-authorized AI-generated JPEG apparel pilot QA: source-only inventory of 84 images, 50 exploratory zero-inference product mask candidates with no false ground-truth scores; add a private ZIP inspection CLI, explicitly opt-in OpenCV GrabCut probe and cross-platform safety regressions (#32).
- Owner-authorized AI-generated apparel R2 pilot technical intake (#32): 23 object metadata records inspected (18 front WebPs, 5 care-label WebPs), with no raw image redistribution. Added private exact-byte SHA256/size/decoder preflight, WebP input support and cross-platform synthetic refusal tests; real cutout IoU remains unmeasured without independent alpha references.
- Local rights-aware real-photo alpha benchmark intake (#32): SHA256-bound private photo/reference/candidate matching, owner-attested processing permission and third-party provenance checks, per-category IoU/continuous alpha MAE/SAD/boundary error, local-only text receipts and cross-platform synthetic fixture regression tests. No bundled real images, automatic licensing judgments, hosted inference or human-rated quality claims.
- Experimental 20-case synthetic cutout challenge matrix (#29/#32) with masked gold-reference IoU, alpha MAE and boundary error; distinct product/portrait/mixed-material synthetic controls, immutable fixture receipts, standalone local report and Windows/Linux validation. Strictly benchmark evidence, not human-rated dataset credit.
- Full-resolution 2020 × 779 owner-supplied Riso PNG README hero with transparent rounded corners and original-size textured composition. Removed obsolete 680 × 262 WebP and nonmatching wordmark SVG; retained separate reusable mineral mark. GitHub CSS sanitization no longer prevents visibly rounded corners (branding follow-up).
- Experimental zero-network synthetic self-correction demonstration (#31/#29): one journal-backed idempotent logical product fringe repair, strict uniform-background and image/alpha guards, immutable source and mask, SHA256-verified isolated publication and crash replay; offline before/after/reference-mask HTML/JSON evidence and portrait safe refusal. Technical demo acceptance only; not a calibrated production matte or production Engine integration.
- Provider-neutral offline typed decision evidence and bounded local candidate reject/repair action planner for separate synthetic product and portrait cohorts (#116). Capability, abstention, model-calibration, immutable accepted-output and zero-paid-spend guards; no provider transport or repair executor connected yet.
- Deterministic offline Noul binary visual-gold evaluation (#111): Brier/ECE, explicit abstention/coverage, false-accept/reject and Wilson intervals, private aggregate reports, and quoted reservation-cost evidence. Synthetic labels are not real visual-quality certification.
- Local-only official-shape Jev 1.14 request/response **fixtures** (#111): preserve Noul probabilities, Choice categorical distributions, Score level-weighted positions and presence-gated Box coordinates; image references and experimental headers remain inert, without network transport or automatic acceptance.
- Experimental Jev visual judgment Stage A (#109): offline-only typed mock decisions, presence-gated Box, historically SHA256-verified metadata-stripped PNG/JPEG prep, explicit danger-zone consent and Decimal token-budget preflight. No TypeSafe transport, API keys, paid calls or automatic quality acceptance.
- Opt-in, read-only validation of SHA256-provenance-bound v2 operator-attested affine registration contracts (#105); forward/inverse consistency, bounded matrix and continuous overlap-domain checks, CLI command and synthetic Windows/Ubuntu tests. No resampling, perceived-quality rating, network use or new mandatory dependencies.
- Opt-in operator-attested, SHA256-bound integer translations and streamed tiled 4K+ pixel/alpha difference reports up to 24 MP (#100), with explicit source/candidate overlap fractions and frame/provenance receipts. No auto-alignment, interpolation, model inference or aesthetic scoring; Pillow decoder memory remains separately bounded by 24MP cap.\n- Owner-selected Prehnite Riso wordmark replaces the README hero with forest-green/coral ink and warm paper; shared accessible light/dark palette embedded locally into gallery/native/pixel reports, documented color roles and retained recolored SVG fallback. No new service or model inference.\n- Strictly opt-in same-grid technical image diagnostics (#98): verified historical original or named cutout, explicit operator registration attestation, profile/orientation/geometry refusal, black/white alpha-composited pixel deltas, private difference heatmap/HTML/JSON, no inference, provider invoice or quality-score claims.
- Private source-to-output native-pixel inspector comparison with explicit trusted `--inputs`, saved SHA256 verification, read-only per-slot stage/attempt/reservation drilldowns and no-JS alpha checkerboard toggle; leaves ordinary gallery and ZIP unchanged (#95).
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
- Local repair now requires an explicitly declared opaque material and refuses ambiguous masked interior background colors or disconnected internal transparency before trying an alpha cleanup; synthetic negative controls cover holes, matching-color product areas and unqualified translucent inputs (#29).
- Empty masks no longer get scheduled for ineffective local morphology: repair planner sends them to human review instead (#31).
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
