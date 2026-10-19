# Prehnite | Product progress

**Engineering tasks verified: 60/80 (75.0%).**  
**Outcome milestones accepted: 1/9 (11.1%).**

Engineering task completion includes original reviewed implementation receipts. Outcome acceptance additionally requires real laptop tests, usable images, and human review. Neither percentage alone is a product-quality certificate.

## Prioritized workstreams

| Priority | Workstream | Work evidenced | Completion | Outcome | Next missing task |
| --- | --- | ---: | ---: | --- | --- |
| P0 | P1-M01: Model and provider selection | 4/6 | 66.7% | Open | P1-M01-R01 |
| P1 | P1-M02: Real 8 GiB inference evidence | 6/8 | 75.0% | Open | P1-M02-E01 |
| P1 | P1-M04: Batch and recovery | 22/25 | 88.0% | Open | P1-M04-B01 |
| P2 | P1-M03: Memory and throughput | 0/3 | 0.0% | Open | P1-M03-R01 |
| P2 | P1-M05: Quality and delivery | 17/19 | 89.5% | Open | P1-M05-A01 |
| P3 | P2-M01: LoRA research | 0/2 | 0.0% | Open | P2-M01-R01 |
| P3 | P2-M02: Controlled style variants | 0/3 | 0.0% | Open | P2-M02-B01 |
| P3 | P2-M03: Private appearance trials | 0/3 | 0.0% | Open | P2-M03-B01 |
| P4 | P1-M00: Foundation and project tooling | 11/11 | 100.0% | Accepted | All gates evidenced |

## What is needed next

Listed by priority, not by number of commits or the size of a previous release.

- **P0 · P1-M01 · Research decision: model and runtime on 8 GiB**: Compare ComfyUI + fal.ai typed contracts with a reproducible model choice. Next: P1-M01-R01 (research); 2 outstanding.
- **P1 · P1-M02 · 8 GiB reproducible baseline**: Separate consent needed for physical three-run benchmark. Next: P1-M02-E01 (experiment); 2 outstanding.
- **P1 · P1-M04 · Useful 10-image batch**: Close the first real ten-image local batch and resume path. Next: P1-M04-B01 (implementation); 3 outstanding.
- **P2 · P1-M03 · Measure one useful optimization**: Profile only after accepted real baseline. Next: P1-M03-R01 (research); 3 outstanding.
- **P2 · P1-M05 · Human-accepted local workflow**: Human acceptance of images, cutouts and installation. Next: P1-M05-A01 (acceptance); 2 outstanding.
- **P3 · P2-M01 · Research: LoRA and conditioning options**: Research lawful local adapters when Phase 1 evidence permits. Next: P2-M01-R01 (research); 2 outstanding.
- **P3 · P2-M02 · Reproducible style and LoRA variation**: Implement then measure same model, adapters and seeds. Next: P2-M02-B01 (implementation); 3 outstanding.
- **P3 · P2-M03 · Private appearance experimentation**: Consented local reference and human consistency checks. Next: P2-M03-B01 (implementation); 3 outstanding.

## Detailed task evidence

Each row is one work item counted once. Imported technical achievements are scoped to the originally verified implementation, never to new physical or human acceptance.

### P1-M00 · Verified installable application foundation (11/11; 100.0%)

| Task | Kind | State | Evidence / required outcome |
| --- | --- | --- | --- |
| P1-M00-V1-R05 | implementation | verified | Previously verified source unit R05: [evidence](https://github.com/interzettel/prehnite/pull/45) |
| P1-M00-V1-R04 | implementation | verified | Previously verified source unit R04: [evidence](https://github.com/interzettel/prehnite/pull/45) |
| P1-M00-V1-R03 | implementation | verified | Previously verified source unit R03: [evidence](https://github.com/interzettel/prehnite/issues/9) |
| P1-M00-V1-R02 | implementation | verified | Previously verified source unit R02: [evidence](https://github.com/interzettel/prehnite/pull/13) |
| P1-M00-V1-R01 | implementation | verified | Previously verified source unit R01: [evidence](https://github.com/interzettel/prehnite/pull/13) |
| P1-M00-F01 | implementation | verified | MIT repository and installable Python package; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M00-F02 | implementation | verified | Strict manifest/output path validation; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M00-F03 | implementation | verified | Free synthetic batch generator and 2-tier orchestration; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M00-F04 | implementation | verified | SQLite stage journal and basic resume; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M00-F05 | implementation | verified | JSON/CSV/HTML reports and checked ZIP export; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M00-F06 | implementation | verified | Offline pytest + CLI validation on GitHub Actions; original evidenced v1 work scoped to installable synthetic foundation, not real generation quality: [evidence](https://github.com/interzettel/prehnite/pull/1) |

### P1-M01 · Research decision: model and runtime on 8 GiB (4/6; 66.7%)

| Task | Kind | State | Evidence / required outcome |
| --- | --- | --- | --- |
| P1-M01-V1-P05 | implementation | verified | Previously verified source unit P05: [evidence](https://github.com/interzettel/prehnite/pull/55) |
| P1-M01-V1-P04 | implementation | verified | Previously verified source unit P04: [evidence](https://github.com/interzettel/prehnite/pull/53) |
| P1-M01-V1-P03 | implementation | verified | Previously verified source unit P03: [evidence](https://github.com/interzettel/prehnite/pull/50) |
| P1-M01-V1-P01 | implementation | verified | Previously verified source unit P01: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M01-R01 | research | planned | Compare a pinned lawful model, stock ComfyUI, other applicable runtimes and opt-in image APIs with source-linked applicability/rights and explicit unknowns. |
| P1-M01-R02 | decision | planned | Approve model, image size, objective quality criteria, host-RAM/VRAM stops and apples-to-apples benchmark protocol; no inference implied. |

### P1-M02 · 8 GiB reproducible baseline (6/8; 75.0%)

| Task | Kind | State | Evidence / required outcome |
| --- | --- | --- | --- |
| P1-M02-VA-P08-A04 | implementation | verified | Original atomic work P08-A04: Publish compatibility profile by model size. Decision table states actually measured versus unknown VRAM configurations. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/170) |
| P1-M02-VA-P08-A02 | implementation | verified | Original atomic work P08-A02: Run bounded 8GB model load and forward pass. Measure peak VRAM, cold/warm latency and failure behavior on actual laptop. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/177) |
| P1-M02-VA-P08-A01 | implementation | verified | Original atomic work P08-A01: Record local GPU environment and free VRAM. Reproducible OS, CUDA, driver and installed weight licensing record. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/166) |
| P1-M02-V1-P07 | implementation | verified | Previously verified source unit P07: [evidence](https://github.com/interzettel/prehnite/pull/59) |
| P1-M02-V1-P06 | implementation | verified | Previously verified source unit P06: [evidence](https://github.com/interzettel/prehnite/pull/57) |
| P1-M02-V1-P02 | implementation | verified | Previously verified source unit P02: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M02-E01 | experiment | blocked | With separate fresh permission, execute only the exact bounded one-startup/three-run P08-A03 contract; retain true machine/recipe/timing hashes and honest failure evidence. |
| P1-M02-A01 | acceptance | planned | Independent review of real receipt, run provenance, outcomes, peak sampling limitations, safety/rights and whether the specific 8 GiB configuration is actually repeatable. |

### P1-M03 · Measure one useful optimization (0/3; 0.0%)

| Task | Kind | State | Evidence / required outcome |
| --- | --- | --- | --- |
| P1-M03-R01 | research | planned | Choose ONE supported optimization after baseline, with hypothesized memory/time impact and downside/quality test plan; do not pretend it is already faster. |
| P1-M03-B01 | implementation | planned | Implement reversible opt-in scheduling/offload/tiling configuration with capability checks, synthetic tests and no hidden GPU/API work. |
| P1-M03-E01 | experiment | blocked | Compare unchanged model/seed/size/steps on actual 8 GiB laptop before/after; report VRAM, host RAM/commit, elapsed time, failures and blinded quality judgment. |

### P1-M04 · Useful 10-image batch (22/25; 88.0%)

| Task | Kind | State | Evidence / required outcome |
| --- | --- | --- | --- |
| P1-M04-VA-S05-A04 | implementation | verified | Original atomic work S05-A04: Wire the bounded repair into production Engine.cutout. Real stage transition uses journal, protects selected artifacts and can abstain. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/129) |
| P1-M04-VA-S05-A03 | implementation | verified | Original atomic work S05-A03: Hard-case refusal and one-attempt coverage. Oversized leak, multiple objects and material uncertainty safely refuse. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/120) |
| P1-M04-VA-S05-A02 | implementation | verified | Original atomic work S05-A02: Idempotent journal-backed local repair executor. Stable operation receipt, atomic candidate, integrity-verified crash replay. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/119) |
| P1-M04-VA-S05-A01 | implementation | verified | Original atomic work S05-A01: Typed zero-spend repair decision plan. Policy authorizes local repair separately from uncertain paid submission. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/117) |
| P1-M04-V1-R07 | implementation | verified | Previously verified source unit R07: [evidence](https://github.com/interzettel/prehnite/pull/84) |
| P1-M04-V1-D10 | implementation | verified | Previously verified source unit D10: [evidence](https://github.com/interzettel/prehnite/pull/84) |
| P1-M04-V1-D09 | implementation | verified | Previously verified source unit D09: [evidence](https://github.com/interzettel/prehnite/pull/72) |
| P1-M04-V1-D08 | implementation | verified | Previously verified source unit D08: [evidence](https://github.com/interzettel/prehnite/pull/83) |
| P1-M04-V1-D07 | implementation | verified | Previously verified source unit D07: [evidence](https://github.com/interzettel/prehnite/pull/71) |
| P1-M04-V1-D06 | implementation | verified | Previously verified source unit D06: [evidence](https://github.com/interzettel/prehnite/pull/76) |
| P1-M04-V1-D05 | implementation | verified | Previously verified source unit D05: [evidence](https://github.com/interzettel/prehnite/pull/74) |
| P1-M04-V1-D04 | implementation | verified | Previously verified source unit D04: [evidence](https://github.com/interzettel/prehnite/pull/78) |
| P1-M04-V1-D03 | implementation | verified | Previously verified source unit D03: [evidence](https://github.com/interzettel/prehnite/pull/67) |
| P1-M04-V1-D02 | implementation | verified | Previously verified source unit D02: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M04-V1-D01 | implementation | verified | Previously verified source unit D01: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M04-V1-C10 | implementation | verified | Previously verified source unit C10: [evidence](https://github.com/interzettel/prehnite/pull/87) |
| P1-M04-V1-C07 | implementation | verified | Previously verified source unit C07: [evidence](https://github.com/interzettel/prehnite/pull/80) |
| P1-M04-V1-C05 | implementation | verified | Previously verified source unit C05: [evidence](https://github.com/interzettel/prehnite/pull/52) |
| P1-M04-V1-C04 | implementation | verified | Previously verified source unit C04: [evidence](https://github.com/interzettel/prehnite/pull/49) |
| P1-M04-V1-C03 | implementation | verified | Previously verified source unit C03: [evidence](https://github.com/interzettel/prehnite/pull/10) |
| P1-M04-V1-C02 | implementation | verified | Previously verified source unit C02: [evidence](https://github.com/interzettel/prehnite/pull/10) |
| P1-M04-V1-C01 | implementation | verified | Previously verified source unit C01: [evidence](https://github.com/interzettel/prehnite/pull/10) |
| P1-M04-B01 | implementation | planned | Expose minimal pip-installable local recipe run -> manual selection -> ZIP/report for 10 real generated images without manual source edits or a new graph editor. |
| P1-M04-B02 | implementation | planned | Implement/verify bounded journal resume, interruption handling, model/source identity and no silent re-generation of completed items for this small batch. |
| P1-M04-E01 | experiment | blocked | Run a separately authorized 10-image local batch on 8 GiB laptop; retain exact recipe, failures/retries, time, peak sampled resource use, output hashes and candidate gallery. |

### P1-M05 · Human-accepted local workflow (17/19; 89.5%)

| Task | Kind | State | Evidence / required outcome |
| --- | --- | --- | --- |
| P1-M05-VA-R06-A02 | implementation | verified | Original atomic work R06-A02: Audit optional model checkpoints and training restrictions. Separate weight/source terms recorded; no implicit MIT relicensing. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/131) |
| P1-M05-VA-R06-A01 | implementation | verified | Original atomic work R06-A01: Inventory Python dependencies and transitive licenses. CycloneDX SBOM, exact installed-version snapshot (not hashed lock), and named unresolved license exceptions. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/130) |
| P1-M05-VA-S07-A02 | implementation | verified | Original atomic work S07-A02: Implement strict human-review feedback ingestion. Import approved/needs-work/skip plus RGBA edits without gold-label claims. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/125) |
| P1-M05-VA-S06-A03 | implementation | verified | Original atomic work S06-A03: Inspect owner-provided 84-image source-only pilot. 50 front images get unreviewed baseline masks without false accuracy claims. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/123) |
| P1-M05-VA-S06-A02 | implementation | verified | Original atomic work S06-A02: Add private RGB/mask reference scoring CLI. WebP/JPEG source and PNG alpha validated with SHA, geometry and rights attestation. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/122) |
| P1-M05-VA-S06-A01 | implementation | verified | Original atomic work S06-A01: Build withheld-reference synthetic alpha challenge suite. 20 deterministic cases report independent alpha IoU and boundary MAE. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/120) |
| P1-M05-VA-S03-A03 | implementation | verified | Original atomic work S03-A03: Implement true color spill edge decontamination. Pixel-level tests prove removal without deleting background-colored product regions. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/164) |
| P1-M05-VA-S03-A02 | implementation | verified | Original atomic work S03-A02: Prove unsafe scene/material abstention. 20-case challenge matrix verifies transparent, hair, gradient and multi-object refusal. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/120) |
| P1-M05-VA-S03-A01 | implementation | verified | Original atomic work S03-A01: Demonstrate bounded synthetic product alpha correction. Offline flat-background leak pixels removed against withheld reference. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/119) |
| P1-M05-VA-Q06-A01 | implementation | verified | Original atomic work Q06-A01: Register owner-authorized product photo cohort. 84 private AI-generated JPEGs inventoried and source privacy preserved. Previously independently accepted under its original narrow v1 task criteria, not proof that the parent product outcome or current real-image acceptance is complete.: [evidence](https://github.com/interzettel/prehnite/pull/123) |
| P1-M05-V1-S04 | implementation | verified | Previously verified source unit S04: [evidence](https://github.com/interzettel/prehnite/pull/176) |
| P1-M05-V1-S02 | implementation | verified | Previously verified source unit S02: [evidence](https://github.com/interzettel/prehnite/pull/53) |
| P1-M05-V1-S01 | implementation | verified | Previously verified source unit S01: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M05-V1-Q04 | implementation | verified | Previously verified source unit Q04: [evidence](https://github.com/interzettel/prehnite/pull/65) |
| P1-M05-V1-Q03 | implementation | verified | Previously verified source unit Q03: [evidence](https://github.com/interzettel/prehnite/pull/70) |
| P1-M05-V1-Q02 | implementation | verified | Previously verified source unit Q02: [evidence](https://github.com/interzettel/prehnite/pull/61) |
| P1-M05-V1-Q01 | implementation | verified | Previously verified source unit Q01: [evidence](https://github.com/interzettel/prehnite/pull/1) |
| P1-M05-A01 | acceptance | planned | Human-score the real 10-image batch against success criteria recorded before its run; disclose accepted yield, quality failure modes and seconds per accepted image. Compare practical Prehnite value against the same ComfyUI-only work (manual steps, reproducible selection/resume), without claiming image quality speedups that actually come from changed model settings. |
| P1-M05-A02 | acceptance | planned | Accept/reject documented local install instructions, checkpoint/LoRA rights and honest limitations; explicitly separate this local product acceptance from the old 90-image/paid-billing release obligations. |

### P2-M01 · Research: LoRA and conditioning options (0/2; 0.0%)

| Task | Kind | State | Evidence / required outcome |
| --- | --- | --- | --- |
| P2-M01-R01 | research | planned | Choose one legal compatible local base model and LoRA combination; research scale/order/loading, measured-memory requirements, provenance and source license. |
| P2-M01-R02 | decision | planned | Approve controlled style and user-reference editing experiments and privacy boundaries; identify what identity consistency tests can and cannot prove. |

### P2-M02 · Reproducible style and LoRA variation (0/3; 0.0%)

| Task | Kind | State | Evidence / required outcome |
| --- | --- | --- | --- |
| P2-M02-B01 | implementation | planned | Pin base/LoRA hashes, scales, prompt/seeds and backend compatibility in recipe/journal; refuse missing/changed adapter files. |
| P2-M02-B02 | implementation | planned | Generate a controlled local parameter grid/contact sheet where one studied dimension changes at a time; preserve all provenance. |
| P2-M02-E01 | experiment | blocked | Run owner-authorized multiple-seed style experiments on 8 GiB GPU; measure memory/load latency and blind human consistency rating. |

### P2-M03 · Private appearance experimentation (0/3; 0.0%)

| Task | Kind | State | Evidence / required outcome |
| --- | --- | --- | --- |
| P2-M03-B01 | implementation | planned | Provide local-only opt-in self-owned reference import, no implicit uploads, no mandatory external account and explicit original-image retention policy. |
| P2-M03-E01 | experiment | blocked | Run a small approved set of haircut/beard/hair-color variations with locally stored inputs; preserve source model/LoRA/edit-strength/seed provenance. |
| P2-M03-A01 | acceptance | planned | User reviews requested variation adherence and identity consistency; outputs labeled simulations, never predicted actual changes; verify no external transmission. |

## Evidence and permission rules

A research review, merged implementation, hardware experiment, and human quality decision are different types of evidence. An unapproved CUDA run, unverified API billing, and a synthetic image cannot complete those gates.

[Canonical machine-readable roadmap](../../progress/roadmap.json) · [Milestone acceptance definitions](../PRODUCT_MILESTONES.md).
