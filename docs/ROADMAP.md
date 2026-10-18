# Roadmap (issues should reference acceptance tests)

**Progress and agent tasks:** [Verified 61-unit release ledger](progress/STATUS.md) · [Atomic task dashboard and acceptance criteria](progress/ATOMIC.md) · [Frozen PR-sized register](../progress/atomic.json) · [Current iteration board](SPRINT.md). The atomic percentage is scoped only to the 19 unfinished release units from its initial baseline, not overall project progress.

## Latest real-machine evidence (2026-10-18)

**One local source-to-cutout case succeeded and Candidate A was independently visually accepted.**
See [the measured local lab case study](LOCAL_LAB_MILESTONE_2026-10-18.md) for prompt/asset hashes, version compatibility, the failed first attempt, the single successful segmentation job, observed GPU/RAM telemetry and approval scope. The private launcher, model files and CPU-refinement implementation are **not yet shipped in the public Prehnite package**. The frozen 61-unit and 73-atomic ledgers remain unchanged pending their distinct acceptance conditions.

**Productization Sprint 1 has now implemented the first reusable step locally**:
the publicly submitted [draft PR #161](https://github.com/interzettel/prehnite/pull/161)
(branch `feature/local-cutout-productization`, head `9949367`) adds opt-in CPU `cutout-qa` / `cutout-accept` commands,
configurable alpha candidates, seven-stage evidence and create-only visual
review receipts; the private lab consolidates its runtime launcher as
`prehnite_local_runtime.py`. The local runner's review-resolution pass reports **21 passing cutout tests**
and **872 host full-suite passes / 15 skipped / 1 Windows symlink-privilege
failure**; GitHub Actions [run 39152075877](https://github.com/interzettel/prehnite/actions/runs/39152075877)
finished with **25/25 successful jobs**. The previous five focused code-review
findings were corrected in commit `9949367`; the updated contracts were
independently source-inspected. **None of this is merged into public `main`
yet, Engine QA is still opt-in and a second real-object test has not run.**
[Evidence and source boundaries](LOCAL_LAB_MILESTONE_2026-10-18.md#subsequent-productization-sprint-and-public-review-same-date).

**Immediate work:** obtain maintainer review/merge decisions for the corrected
[PR #161](https://github.com/interzettel/prehnite/pull/161), finish
independent review of [PR #159](https://github.com/interzettel/prehnite/pull/159)
and [documentation PR #160](https://github.com/interzettel/prehnite/pull/160),
then seek separate authorization for a diverse next-object test.

## Local productization review checklist (2026-10-18)

- [x] Private lab implements a reusable CPU cutout-quality module, two additive CLI commands, candidate/approval receipts and local-runtime wrapper; local offline tests reported as passing.
- [x] Resolve initial independent code-review findings on **[draft PR #161](https://github.com/interzettel/prehnite/pull/161)** (execution evidence, PR #159 observation, topology, CLI runbook, RGB operation facts); head `9949367`, CI 25/25. This checkbox is for the **review fixes only**, not merge/release approval.
- [ ] Obtain final maintainer merge approval and reconcile branch interactions with PR #159/#160; maintain separate integration and GPU acceptance boundaries.
- [ ] Integrate reviewed cutout QA optionally with the existing Engine and journal semantics; no new job engine.
- [ ] Verify behavior against a second distinct real object under separate GPU authorization, with visual review; no automatic acceptance.
- [ ] Evaluate gold-reference alpha scoring, material diversity, multiple instances and long-running/batch operations before marketing production readiness.

## v0.1: executable architecture, no mandatory cloud costs
- [x] Strict manifest/profile validation and output path safety
- [x] Demo provider and documented opt-in fal generation/upscaling
- [x] Journaled stage execution and estimated budget reservations
- [x] Selectable image variants and bounded generation retry
- [x] Optional Haiku pair judgments and cutout QA
- [x] PNG cutouts from mask outputs with technical validation
- [x] JSON/CSV/HTML reports and ZIP containing accepted deliverables
- [x] CLI and stdio MCP entrypoint
- [ ] End-to-end paid API smoke test with actual model schemas and billing (requires credentials)
- [ ] Production validation on Windows AORUS RTX 4070 Laptop (one successful native-1K lamp + independently visually accepted cutout observed 2026-10-18; multi-run/operational/4K release validation remains open — [evidence](LOCAL_LAB_MILESTONE_2026-10-18.md))

## v0.2: robust production
- [x] Generic ComfyUI API graph/queue/history adapter (not hardware-validated)
- [ ] Tested ComfyUI graphs, model offloading, GPU resource management and cancellation
- [ ] Local ESRGAN/SAM/BiRefNet adapters with version-pinned checkpoints
- [ ] Local HPS/Q-ReAlign judges and crop-aware 4K QA
- [ ] Region-level detection, multi-object instance handling and proper alpha matting
- [ ] Structured corrective plans (segment alternate, refine, edit versus regenerate)
- [ ] Provider schema conformance tests, measured cost estimation and invoice reconciliation
- [ ] Shadow-mode evaluations, category thresholds and calibration tools
- [ ] Deterministic task-key/content-addressed cache, transaction-safe output writes
- [ ] Robust cancellation, job locking, concurrent readers and interrupted process recovery

## v0.3+: production ergonomics
- [ ] Inspectable HTML dashboard with image comparison / masks
- [ ] Native Parquet report export and performance/cost comparisons
- [ ] Cross-batch benchmark report and accepted-asset efficiency
- [ ] Optional HTTP MCP deployment with auth and threat model
- [ ] Provider packs and reusable workflow registry
- [ ] Installer and reproducible Windows/Linux integration tests

## Model Recipes workstream — versioned micro/macro (October 2026)

This is a **new, separately tracked architecture scope** under [issue #132](https://github.com/interzettel/prehnite/issues/132), not new credit in the frozen [61-unit release ledger](progress/STATUS.md) or [73-task atomic register](progress/ATOMIC.md). This checklist tracks implementation slices, **not** release readiness, demonstrated output quality or laptop VRAM compatibility. Details: [recipe specification](MODEL_RECIPES.md), [local execution contract](RECIPE_EXECUTION.md), [current board](SPRINT.md).

**Completed engineering groundwork (not proof of real-model inference):**
- [x] Versioned `prehnite-micro`/`prehnite-macro` blueprint schemas, capability DAG/cycle and policy validation, stable fingerprints ([#138](https://github.com/interzettel/prehnite/pull/138))
- [x] Offline read-only hardware inventory with unknown/unprobed accelerator states; no VRAM tier certification ([#139](https://github.com/interzettel/prehnite/pull/139))
- [x] Local micro ComfyUI workflow/checkpoint digest resolver with explicit operator terms acknowledgement; no download or legal approval ([#140](https://github.com/interzettel/prehnite/pull/140))
- [x] Opt-in micro-to-engine local ComfyUI execution bridge with per-batch recipe/config/input identity in SQLite, replay refusal and synthetic cross-OS tests ([#141](https://github.com/interzettel/prehnite/pull/141))
- [x] Documentation/board closeout and #133 scoped acceptance recorded ([#142](https://github.com/interzettel/prehnite/pull/142))

**Unverified milestones / next product work:**
- [ ] Rights-aware verified checkpoint sourcing, optional installer/offline import, terms receipts and disk requirements; no bundled weights or automatic downloads ([#135](https://github.com/interzettel/prehnite/issues/135))
- [x] **First artifact-level local proof:** owner-authorized 768×1024 SDXL lamp source → one successful GroundingDINO/SAM2 cutout → conservative CPU alpha refinement → independently accepted Candidate A; measured 8.994 s cutout job and 2,533 MiB sampled VRAM ([2026-10-18 lab evidence](LOCAL_LAB_MILESTONE_2026-10-18.md)). This checks off **only the case study**, not the recipe/release acceptance task below.
- [ ] **First fully integrated and reproducible `prehnite-micro` acceptance run:** make the validated private launcher/refinement a maintainable opt-in public workflow, preserve exact source/model/decision receipts in Prehnite's own journal, pass independent review and reproduce on supported hardware. The current successful workflow is a **private local lab experiment**; an owner-signed journal promotion is still absent ([#132](https://github.com/interzettel/prehnite/issues/132), [#32](https://github.com/interzettel/prehnite/issues/32)).
- [ ] Record reproducible GPU/OS/driver, exact runtime/checkpoint hashes, peak VRAM/RAM, cold/warm stage latency, OOM/recovery behaviour and output-quality evidence on identified physical hardware before claiming any 4/6/8/12 GB `micro` tier ([#134](https://github.com/interzettel/prehnite/issues/134))
- [ ] Model residency/unload, memory-aware scheduling, tiling, bounded failure fallback and measured per-human-accepted-cutout throughput ([#136](https://github.com/interzettel/prehnite/issues/136)); **draft observation-only resource preflight [PR #159](https://github.com/interzettel/prehnite/pull/159)** is not an operational watchdog or an approved production scheduler.
- [ ] Operationalize versioned `prehnite-macro` with independently cleared rights, explicitly consented hosted APIs/budgets where applicable, and distinct benchmark evidence ([#132](https://github.com/interzettel/prehnite/issues/132))
- [ ] Nontechnical installation/recipe selection and real-model end-to-end reproducibility on supported operating systems, with manual release approval ([#132](https://github.com/interzettel/prehnite/issues/132))

**Current boundary:** `prehnite-micro` offers an experimental, operator-configured local execution **path**, not a preinstalled or benchmarked executable model bundle. `prehnite-macro` is still blueprint-only. No mandatory subscription/hosted workflow service and no paid inference without explicit owner authorization.

## Definition of done
The repo is only production-ready after a 90-asset mixed-resolution run, paid-call reconciliation, restart recovery tests, image/cutout visual auditing, security testing, licensing review and reproducible benchmark documentation.
