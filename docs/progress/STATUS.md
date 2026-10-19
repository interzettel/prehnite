# Prehnite — one canonical product roadmap

> Generated from progress/roadmap.json by scripts/roadmap.py. The original
> 61-unit release scope and 73-task register are archived historical evidence,
> not competing active project percentages.

**Product outcomes:** 1/9 milestones verified.  
**Scope:** 8 GiB RTX 4070 laptop, measured host RAM; two phases; no 4/6 GiB program.  
**Evidence rule:** research != code != GPU observations != owner acceptance.

| Phase | Milestone | State | Evidence gates | Next work |
| --- | --- | --- | ---: | --- |
| P1 | P1-M00 — Verified installable application foundation | verified | 6/6 | Milestone evidenced |
| P1 | P1-M01 — Research decision: model and runtime on 8 GiB | planned | 0/2 | P1-M01-R01 |
| P1 | P1-M02 — 8 GiB reproducible baseline | planned | 0/2 | P1-M02-E01 |
| P1 | P1-M03 — Measure one useful optimization | planned | 0/3 | P1-M03-R01 |
| P1 | P1-M04 — Useful 10-image batch | planned | 0/3 | P1-M04-B01 |
| P1 | P1-M05 — Human-accepted local workflow | planned | 0/2 | P1-M05-A01 |
| P2 | P2-M01 — Research: LoRA and conditioning options | planned | 0/2 | P2-M01-R01 |
| P2 | P2-M02 — Reproducible style and LoRA variation | planned | 0/3 | P2-M02-B01 |
| P2 | P2-M03 — Private appearance experimentation | planned | 0/3 | P2-M03-B01 |

## Research, implementation, experiment, acceptance

Every gate task has one question to answer and one accepted evidence type.
The kinds are not interchangeable; an offline CI success cannot prove visual quality.

### P1 — Efficient 8 GiB image generation and useful batches

#### P1-M00 — Verified installable application foundation

Installable local Python CLI, validated input safety, synthetic zero-cost batch, persistent journal, reports and CI demonstration; NOT a verified local model-quality or GPU performance claim

| Task | Kind | State | Owner | Acceptance / evidence |
| --- | --- | --- | --- | --- |
| P1-M00-F01 | implementation | verified | Agent cloud | MIT repository and installable Python package; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality; [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M00-F02 | implementation | verified | Agent cloud | Strict manifest/output path validation; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality; [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M00-F03 | implementation | verified | Agent cloud | Free synthetic batch generator and 2-tier orchestration; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality; [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M00-F04 | implementation | verified | Agent cloud | SQLite stage journal and basic resume; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality; [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M00-F05 | implementation | verified | Agent cloud | JSON/CSV/HTML reports and checked ZIP export; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality; [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M00-F06 | implementation | verified | Agent cloud | Offline pytest + CLI validation on GitHub Actions; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality; [evidence](https://github.com/interzettel/prehnite/pull/1) |

#### P1-M01 — Research decision: model and runtime on 8 GiB

Choose one lawful real model/graph and reproducible comparison plan; no claim of model compatibility before an observed run.

| Task | Kind | State | Owner | Acceptance / evidence |
| --- | --- | --- | --- | --- |
| P1-M01-R01 | research | planned | Agent cloud | Compare a pinned lawful model, stock ComfyUI, other applicable runtimes and opt-in image APIs with source-linked applicability/rights and explicit unknowns. |
| P1-M01-R02 | decision | planned | Owner | Approve model, image size, objective quality criteria, host-RAM/VRAM stops and apples-to-apples benchmark protocol; no inference implied. |

#### P1-M02 — 8 GiB reproducible baseline

Obtain correctly authorized, independently inspected repeatability evidence on the current laptop; no generic GPU-tier claim.

| Task | Kind | State | Owner | Acceptance / evidence |
| --- | --- | --- | --- | --- |
| P1-M02-E01 | experiment | blocked | Agent local | With separate fresh permission, execute only the exact bounded one-startup/three-run P08-A03 contract; retain true machine/recipe/timing hashes and honest failure evidence. |
| P1-M02-A01 | acceptance | planned | Owner | Independent review of real receipt, run provenance, outcomes, peak sampling limitations, safety/rights and whether the specific 8 GiB configuration is actually repeatable. |

#### P1-M03 — Measure one useful optimization

Determine whether one backend-supported change improves a predeclared memory/time objective without unacceptable image loss.

| Task | Kind | State | Owner | Acceptance / evidence |
| --- | --- | --- | --- | --- |
| P1-M03-R01 | research | planned | Agent cloud | Choose ONE supported optimization after baseline, with hypothesized memory/time impact and downside/quality test plan; do not pretend it is already faster. |
| P1-M03-B01 | implementation | planned | Agent cloud | Implement reversible opt-in scheduling/offload/tiling configuration with capability checks, synthetic tests and no hidden GPU/API work. |
| P1-M03-E01 | experiment | blocked | Agent local | Compare unchanged model/seed/size/steps on actual 8 GiB laptop before/after; report VRAM, host RAM/commit, elapsed time, failures and blinded quality judgment. |

#### P1-M04 — Useful 10-image batch

Install and run a local generation -> inspect/select -> export path on the owner's real system with receipt-bound failure handling.

| Task | Kind | State | Owner | Acceptance / evidence |
| --- | --- | --- | --- | --- |
| P1-M04-B01 | implementation | planned | Agent cloud | Expose minimal pip-installable local recipe run -> manual selection -> ZIP/report for 10 real generated images without manual source edits or a new graph editor. |
| P1-M04-B02 | implementation | planned | Agent cloud | Implement/verify bounded journal resume, interruption handling, model/source identity and no silent re-generation of completed items for this small batch. |
| P1-M04-E01 | experiment | blocked | Agent local | Run a separately authorized 10-image local batch on 8 GiB laptop; retain exact recipe, failures/retries, time, peak sampled resource use, output hashes and candidate gallery. |

#### P1-M05 — Human-accepted local workflow

Demonstrate a reviewed accepted-image yield and clear resource/recovery report with realistic install instructions and licence boundaries.

| Task | Kind | State | Owner | Acceptance / evidence |
| --- | --- | --- | --- | --- |
| P1-M05-A01 | acceptance | planned | Owner | Human-score the real 10-image batch against success criteria recorded before its run; disclose accepted yield, quality failure modes and seconds per accepted image. Compare practical Prehnite value against the same ComfyUI-only work (manual steps, reproducible selection/resume), without claiming image quality speedups that actually come from changed model settings. |
| P1-M05-A02 | acceptance | planned | Owner | Accept/reject documented local install instructions, checkpoint/LoRA rights and honest limitations; explicitly separate this local product acceptance from the old 90-image/paid-billing release obligations. |

### P2 — Reproducible LoRA/style and private appearance experimentation

#### P2-M01 — Research: LoRA and conditioning options

Choose legal, locally feasible LoRA and subject-conditioning methods from actual backend capabilities.

| Task | Kind | State | Owner | Acceptance / evidence |
| --- | --- | --- | --- | --- |
| P2-M01-R01 | research | planned | Agent cloud | Choose one legal compatible local base model and LoRA combination; research scale/order/loading, measured-memory requirements, provenance and source license. |
| P2-M01-R02 | decision | planned | Owner | Approve controlled style and user-reference editing experiments and privacy boundaries; identify what identity consistency tests can and cannot prove. |

#### P2-M02 — Reproducible style and LoRA variation

Produce a pinned, controllable experiment grid where each variation has traceable model/LoRA state and measured memory cost.

| Task | Kind | State | Owner | Acceptance / evidence |
| --- | --- | --- | --- | --- |
| P2-M02-B01 | implementation | planned | Agent cloud | Pin base/LoRA hashes, scales, prompt/seeds and backend compatibility in recipe/journal; refuse missing/changed adapter files. |
| P2-M02-B02 | implementation | planned | Agent cloud | Generate a controlled local parameter grid/contact sheet where one studied dimension changes at a time; preserve all provenance. |
| P2-M02-E01 | experiment | blocked | Agent local | Run owner-authorized multiple-seed style experiments on 8 GiB GPU; measure memory/load latency and blind human consistency rating. |

#### P2-M03 — Private appearance experimentation

Safely create and review controlled personal-reference variations locally without claiming accurate real-life prediction.

| Task | Kind | State | Owner | Acceptance / evidence |
| --- | --- | --- | --- | --- |
| P2-M03-B01 | implementation | planned | Agent cloud | Provide local-only opt-in self-owned reference import, no implicit uploads, no mandatory external account and explicit original-image retention policy. |
| P2-M03-E01 | experiment | blocked | Agent local | Run a small approved set of haircut/beard/hair-color variations with locally stored inputs; preserve source model/LoRA/edit-strength/seed provenance. |
| P2-M03-A01 | acceptance | planned | Owner | User reviews requested variation adherence and identity consistency; outputs labeled simulations, never predicted actual changes; verify no external transmission. |

## Historical evidence (archive only)

The previous 43/61 released-scope evidence and 21/73 atomic evidence
remain preserved without being counted as parallel active progress.
[Original 61-unit ledger](../../progress/archive/v1/ledger.json) ·
[Original 73-task ledger](../../progress/archive/v1/atomic.json) ·
[Migration notes](../ROADMAP_MIGRATION_V2.md).

The old 90-image/paid-provider/licensing/administration obligations remain
traceable in the crosswalk. A ten-image local test does not falsely close them.
