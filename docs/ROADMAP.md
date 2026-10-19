# Roadmap (issues should reference acceptance tests)

**Proposed product retargeting (owner review pending, 2026-10-19):** [Low-VRAM-first two-phase image-workbench strategy](PRODUCT_STRATEGY_LOW_VRAM.md). This proposes Phase 1 practical low-memory generation/batching and Phase 2 LoRA/appearance-consistency experiments, with ComfyUI reused as first runtime and hosted image APIs optional. **It does not change the 61-unit release ledger, frozen 73-task register, acceptance gates, completed features, task ownership, current priorities or hardware authorization until separately approved.** Existing model-recipe epic [#132](https://github.com/interzettel/prehnite/issues/132) is the discussion home.


**Progress and agent tasks:** [Verified 61-unit release ledger](progress/STATUS.md) · [Atomic task dashboard and acceptance criteria](progress/ATOMIC.md) · [Frozen PR-sized register](../progress/atomic.json) · [Current iteration board](SPRINT.md). The atomic percentage is scoped only to the 19 unfinished release units from its initial baseline, not overall project progress.

## Latest real-machine and integration evidence (2026-10-18)

**First artifact-level success:** one local 768×1024 SDXL lamp source was
processed with GroundingDINO/SAM2, CPU alpha-refined, and Candidate A received
independent visual approval at the inspected scale. The private launcher and
checkpoints are **not** bundled in Prehnite, and the image has not received an
owner-signed Prehnite journal promotion. [Exact evidence and limitations](LOCAL_LAB_MILESTONE_2026-10-18.md).

**Reusable public source merged:** [PR #159](https://github.com/interzettel/prehnite/pull/159)
provides read-only, fail-closed resource observations; [PR #161](https://github.com/interzettel/prehnite/pull/161)
provides CPU-only cutout QA, alpha candidates, separate integrity/execution
states and create-only review receipts. The three #159→#161 synthetic
interface tests from temporary [integration PR #162](https://github.com/interzettel/prehnite/pull/162)
were preserved in the merged source. The temporary branch passed 25/25
GitHub Actions checks but should **not** be merged again. This is development
`main` functionality, **not** a newly published package version, model-run
authorization, live next-object proof or a production hardware tier.

**Next engineering steps:** independently validate one new object under
separate inference authorization, bind a truthful execution receipt to the
real Engine→QA handoff, keep alpha review and owner journal approval distinct,
and qualify repeatability on more than one material/scene. This does not
require revisiting the accepted lamp or reopening the original Gate 3 batch.

## Local productization integration checklist (2026-10-18)

- [x] First real local desk-lamp cutout and artifact-level independent visual acceptance, with immutable historical evidence.
- [x] Public source merges of resource observations (#159) and opt-in cutout QA/acceptance (#161).
- [x] Preserve pass/blocked/unknown readiness-to-QA integration regression tests from #162 in development `main`.
- [x] Independently review original QA evidence/status contract, topology and CLI-runbook findings; corrections merged in #161.
- [ ] Live second-object Engine → optional `cutout-qa` run and independent visual review (requires separate, bounded GPU authorization).
- [ ] Model execution receipts binding actual run to source/target/mask/workflow/model identity.
- [ ] Gold-reference alpha scoring, diversity, long-running/batch operations and model/weight rights clearance before release claims.

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
- [ ] Model residency/unload, memory-aware scheduling, tiling, bounded failure fallback and measured per-human-accepted-cutout throughput ([#136](https://github.com/interzettel/prehnite/issues/136)); **merged observation-only resource preflight [PR #159](https://github.com/interzettel/prehnite/pull/159)** is not an operational watchdog or an approved production scheduler.
- [ ] Operationalize versioned `prehnite-macro` with independently cleared rights, explicitly consented hosted APIs/budgets where applicable, and distinct benchmark evidence ([#132](https://github.com/interzettel/prehnite/issues/132))
- [ ] Nontechnical installation/recipe selection and real-model end-to-end reproducibility on supported operating systems, with manual release approval ([#132](https://github.com/interzettel/prehnite/issues/132))

**Current boundary:** `prehnite-micro` offers an experimental, operator-configured local execution **path**, not a preinstalled or benchmarked executable model bundle. `prehnite-macro` is still blueprint-only. No mandatory subscription/hosted workflow service and no paid inference without explicit owner authorization.

## Definition of done
The repo is only production-ready after a 90-asset mixed-resolution run, paid-call reconciliation, restart recovery tests, image/cutout visual auditing, security testing, licensing review and reproducible benchmark documentation.
