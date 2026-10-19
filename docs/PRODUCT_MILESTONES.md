# Product milestones

Prehnite has **one active roadmap** at [`progress/roadmap.json`](../progress/roadmap.json) and one [generated progress report](progress/STATUS.md). The dashboard reports both work already evidenced and product outcomes still waiting for physical or human validation.

**Engineering evidence: 43 of 63 tasks (68.3%).**  
**Accepted product outcomes: 1 of 9 milestones (11.1%).**

These are complementary readings of the same source, not separate ledgers. An accepted offline adapter or recovery safeguard is real completed engineering work, but does not independently establish that an image model runs efficiently or produces acceptable work.

## Two phases

Phase 1 makes the engine useful for 8 GiB laptop GPUs and optional explicitly configured hosted backends. Phase 2 adds reproducible LoRA/style variations and local privacy-first appearance experiments.

| Priority | Milestone | Verified supporting tasks | What remains |
| --- | --- | ---: | --- |
| P0 | P1-M01: Model and provider selection | **4/6** | Research and select a model/workflow with fixed benchmark |
| P1 | P1-M02: Reproducible local benchmark | **3/5** | Authorized 8 GiB run and independent evidence review |
| P1 | P1-M04: Batch and recovery | **18/21** | Real ten-image generation, interrupted-run test, useful export |
| P2 | P1-M03: Memory efficiency | **0/3** | Benchmark one optimization against the unchanged runtime |
| P2 | P1-M05: Quality and usability | **7/9** | Reviewed real-image yield, rights and install acceptance |
| P3 | P2-M01: LoRA research | **0/2** | Select legal, locally feasible conditioning and adapter method |
| P3 | P2-M02: Consistent style variations | **0/3** | Implement and measure pinned adapter/seed variation grid |
| P3 | P2-M03: Private appearance experiments | **0/3** | User-approved local reference trial and human review |
| Complete | P1-M00: Installed engineering foundation | **11/11** | Already evidenced and accepted |

## What counts as progress

Every engineering task has its own ID, acceptance criterion, dependencies and evidence in the canonical JSON. The 43 inherited verified tasks retain **exact source PR/issue receipts**, plus their original unit identities. They do not falsely complete the new experiment or acceptance tasks.

An outcome is complete only when **all** required tasks are verified and dependent outcomes have passed. A type-specific receipt matters:

- Research: primary-source comparison and reviewed finding.
- Decision: explicit owner-approved experiment scope or choice.
- Implementation: reviewed merged code and tests, not merely a draft PR.
- Experiment: separately authorized real hardware/API evidence with reproducible parameters and independent review.
- Acceptance: human evaluation of the appropriate real outputs, cost and licensing context.

The progress dashboard is priority-sorted because a nearly complete supporting component might still have a single critical blocker. Percentages are supporting-work coverage, **not** predictions of time remaining or a guarantee of image quality.

## Backend strategy

Prehnite reuses the existing ComfyUI API adapter for local inference and the existing fal.ai adapter for optional remote generation/upscaling/segmentation. Demo and technical-quality/judging components are distinct. No third-party API is mandatory. Provider availability, billing and model licenses need individual verification; adapter code and simulated tests alone do not certify live calls.

This roadmap does **not** authorize additional GPU runs, downloading weights, submitting private photos, paid inference, or package publication. Such experiments require separate scoped decisions.

[Open detailed current status](progress/STATUS.md) · [Read the 8 GiB strategy](PRODUCT_STRATEGY_LOW_VRAM.md) · [Read the code](../src/prehnite/)
