# Prehnite — one canonical product roadmap

**Current source:** [progress/roadmap.json](../progress/roadmap.json) · **Current dashboard:** [docs/progress/STATUS.md](progress/STATUS.md) · **Migration:** [v1 → v2](ROADMAP_MIGRATION_V2.md).

Prehnite now uses **one active roadmap**, not separate 61-unit, 73-task and proposed product trackers. The v1 trackers remain frozen in [progress/archive/v1](../progress/archive/v1/) for auditable historical evidence but do not count towards current status.

The product goal is practical local image generation, efficient batches and controlled creative experiments on the owner's **RTX 4070 Laptop 8 GiB**, with measured host RAM limits. Reuse ComfyUI as an existing runtime. Larger GPUs and opt-in APIs remain possible, but there is no mandatory 4/6 GiB certification campaign, video-editor product or third phase.

## What a milestone represents

A milestone is a **product outcome**, not a sprint, a number of PRs or a synthetic demonstration. A verified milestone requires all of its actual task gates and verified dependencies.

Each task has one distinct type:

| Type | Evidence |
| --- | --- |
| Research | Reviewed primary-source comparison and explicit decision |
| Decision | Specific owner-approved configuration, rights or policy decision |
| Implementation | Independently reviewed merged code, tests and exact-head CI |
| Experiment | Separately authorized physical test, measured telemetry and independent review |
| Acceptance | Explicit owner/human judgment using real outcomes and appropriate rights/privacy boundaries |

Green synthetic CI does not certify a model can run on the laptop; a hardware timing does not certify image quality; a beautiful image doesn't establish reliable batches.

## Product outcome milestones

| Phase | Milestone | What success means |
| --- | --- | --- |
| 1 | **P1-M00 · Foundation** | Installed Python CLI, synthetic batch and recoverable/reportable basics verified by original F01–F06 merged evidence |
| 1 | **P1-M01 · Research decision** | Compare candidate model/runtime options and agree one 8 GiB model with a fair experiment |
| 1 | **P1-M02 · Real-machine baseline** | Independently accepted repeatability evidence from an owner-authorized bounded test on the laptop |
| 1 | **P1-M03 · Optimization** | Test one reversible memory/time change against an unchanged ComfyUI baseline; measure RAM/VRAM, time and quality |
| 1 | **P1-M04 · Ten-image batch** | Real locally generated images, human inspection/selection, safe recovery and exported outputs |
| 1 | **P1-M05 · Product acceptance** | Human-reviewed useful-image yield, install clarity, acceptable speed/resource trade-offs |
| 2 | **P2-M01 · LoRA research** | Select lawful, compatible local LoRA/conditioning methods |
| 2 | **P2-M02 · Style variations** | Provenance-bound LoRA/config/seed experiment grids with real quality and resource comparisons |
| 2 | **P2-M03 · Private self-imaging** | Consented local reference studies and human validation of identity/attribute variations |

The [single generated dashboard](progress/STATUS.md) lists the 26 evidence-gated tasks and their present states. **P1-M00 is verified from v1 foundation evidence.** The remaining outcomes require their own new evidence; no other legacy percentage is reused.

## How agents use it

1. Read [AGENTS.md](../AGENTS.md), this document, the current task register and [A2A issue #9](https://github.com/interzettel/prehnite/issues/9).
2. Claim one v2 task ID and existing GitHub issue, specify whether the work is research, coding, real experiment or acceptance.
3. Use one reviewable PR per bounded change, or supply a human research/decision receipt rather than forcing meaningless code commits.
4. For GPU work, request separately scoped owner permission. Respect exact resource/time/cleanup limits and preserve failed-run evidence.
5. After independent review, update **only progress/roadmap.json** with the correct evidence type and regenerate the sole current status using `python scripts/roadmap.py --write`.
6. Run `python scripts/roadmap.py --check` and tests. Do not merge other agents' work without approval.

The first product target is a **useful, repeatable experience on the existing 8 GiB laptop**, not a perfect image, universal device certification or a vanity completion percentage.

## Preserved historical v1 scope

The old **43/61 release units** and **21/73 atomic tasks** still exist as exact read-only snapshots and are cross-referenced in [migration notes](ROADMAP_MIGRATION_V2.md). The original 90-image acceptance, paid provider billing, full licensing and GitHub Projects syncing are not magically completed by a ten-image local pilot; they can be revisited through explicit v2 scope decisions.

**Roadmap governance approval is not permission to run GPU experiments, download weights, upload private photos, spend on providers or publish releases.**
