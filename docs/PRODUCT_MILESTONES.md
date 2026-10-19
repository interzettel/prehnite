# Prehnite — proposed product milestones (8 GiB laptop, v2)

> **This is a proposed milestone system, NOT a replacement progress percentage.**  
> [Machine-readable proposed plan](../progress/product_milestones.v2.proposed.json) · [Product strategy](PRODUCT_STRATEGY_LOW_VRAM.md) · [Original release status](progress/STATUS.md) · [Frozen atomic tracker](progress/ATOMIC.md) · [A2A coordination #9](https://github.com/interzettel/prehnite/issues/9)

**As of:** 2026-10-19 · **Approval:** awaiting owner review in [PR #183](https://github.com/interzettel/prehnite/pull/183). Nothing in this plan authorizes CUDA execution, image uploads, model downloads, bills, real reference-data inspection, merging or publishing.

## Why a third planning view exists

The old **61-unit evidence ledger (43 done)** counts the original release obligations, including billed hosted-pilot and administrative synchronization requirements. The separate **73-task register (21 done)** counts PR-sized work in the originally unfinished scope. Both remain intact, including all blocked units, existing milestone gates and generated charts.

Neither record answers this product question: **Can one person install Prehnite and obtain reproducible useful images from an 8 GiB laptop GPU with realistically constrained system RAM?** Research, implementation and verified experimental outcomes must not look interchangeable.

This v2 **product milestone proposal** is a separate *plan*: its states start at proposed; it does not award any new done credit, cannot inherit a green PR into “GPU qualified”, and does not redefine old release criteria. The new machine-readable register retains an explicit mapping for every one of the 18 originally unfinished release units. Historical evidence is preserved and original acceptance requirements remain in force.

### Two phases; no Phase 3

- **Phase 1 — 8 GiB image engine:** hardware-aware model choice, one tested local pipeline, measured memory/time improvements, useful real-image batch, human acceptance and practical installation.
- **Phase 2 — controlled LoRA and appearance experiments:** pinned LoRA and reference-conditioning research, versioned parameter grids, local private self-image experiments and human-scored consistency.

Only the owner's existing **RTX 4070 Laptop GPU, 8 GiB**, is a near-term hardware testing target. The available **host RAM and system commit** are equally important. No 4/6 GiB test campaign. Larger GPUs and APIs remain optional compatible targets, not an additional mandatory product phase.

## What a milestone means

A milestone is an **observable outcome** proven by all of its named gate tasks—not a period, a PR count or an arbitrary percentage. Its task types are complementary:

| Work type | What the agent actually does | Evidence needed to verify |
| --- | --- | --- |
| **Research** | Read primary sources, compare alternative models/runtimes/licences, formulate measurable trade-offs | Dated comparison/decision record with primary references, invalid assumptions and open unknowns; peer review |
| **Decision** | Owner approves one model/benchmark/consent/quality target | Recorded explicit owner decision with scope and conditions; not inferred from agent drafting |
| **Implementation** | Write bounded code, integration, regression tests and docs | Reviewed merged PR, actual code/tests, final-head CI and evidence of stated feature behavior |
| **Experiment** | Execute only separately authorized real local tests, measure resources and output quality | Real machine+model+workflow provenance, exact run history/failures/cleanup, honest telemetry limits and independent inspection; synthetic tests alone do not suffice |
| **Acceptance** | Judge whether the result is useful, repeatable, rights-cleared, safe and worthy of a claimed outcome | Owner decision and documented review of real outputs and evidence; a checksum is not visual acceptance |

**Work loop:** research/decision → implement → instrument and run → interpret evidence → accept, revise or stop. Not every ticket requires all five activities. An implementation ticket can be independently done without hardware execution, **but it cannot complete a milestone whose real experiment is still blocked**. A research ticket can complete with a credible decision and no code.

**No automatic spending or GPU testing.** The existing P08-A03 bounds (single supervised startup, three identical prompts, RAM ≥6,000 MiB, free VRAM ≥5,000 MiB, commit ≤80%, no retries, strict time/cleanup limits) remain specific to that still-blocked experiment. Approving a roadmap does not authorize it.

## Product milestones and their gates

| Gate | Phase | Outcome and evidence | Existing work to reuse |
| --- | --- | --- | --- |
| **P1-M01** | Research | Compare lawful runtime/model options, select **one** config and predeclare fair same-seed/image benchmark and quality criteria | [#132](https://github.com/interzettel/prehnite/issues/132), [#134](https://github.com/interzettel/prehnite/issues/134) |
| **P1-M02** | Benchmark | Owner-authorized, independently reviewed **repeatable 8 GiB** evidence on the actual laptop. No generic VRAM-tier certificate | [#24](https://github.com/interzettel/prehnite/issues/24), [PR #181](https://github.com/interzettel/prehnite/pull/181) |
| **P1-M03** | Research + build + experiment | Select **one** memory optimization, implement reversible backend-supported option, measure impact against unchanged ComfyUI baseline and quality/host-RAM/time tradeoffs | [#136](https://github.com/interzettel/prehnite/issues/136) |
| **P1-M04** | Build + experiment | Install and execute minimal **ten-image real local batch**, manual selection/export, interruption/resume and detailed receipts | [#132](https://github.com/interzettel/prehnite/issues/132), [#15](https://github.com/interzettel/prehnite/issues/15) |
| **P1-M05** | Acceptance | Human-reviewed ten-image accepted fraction, seconds per accepted result, rights and install clarity; separate remaining release obligations | [#28](https://github.com/interzettel/prehnite/issues/28), [#32](https://github.com/interzettel/prehnite/issues/32), [#40](https://github.com/interzettel/prehnite/issues/40) |
| **P2-M01** | Research | Choose local, lawful LoRA and reference-conditioning approach, document VRAM/RAM constraints and privacy | [#135](https://github.com/interzettel/prehnite/issues/135), [#132](https://github.com/interzettel/prehnite/issues/132) |
| **P2-M02** | Build + experiment | Reproducible LoRA/seed/style variation grids, pinned adapter hashes and scales, measurable consistency and resource costs | [#132](https://github.com/interzettel/prehnite/issues/132), [#136](https://github.com/interzettel/prehnite/issues/136) |
| **P2-M03** | Build + experiment + acceptance | Private personal-reference appearance variations with identity and requested-attribute review; no prediction-of-reality claim | [#132](https://github.com/interzettel/prehnite/issues/132), [#28](https://github.com/interzettel/prehnite/issues/28) |

**Phase 1 exit requires both the measured optimization decision (P1-M03) and the real batch (P1-M04), followed by P1-M05 human acceptance.** A successful technical benchmark by itself is not a useful product, and a useful batch is not proof that its performance is optimized.

This table shows **8 proposed milestones and 20 proposed gate tasks**. It does not mean 0/8 on an adopted scoreboard: the plan is not adopted yet. When accepted, newly verified gates require the specified actual evidence, independently reviewed. Work done previously may be cited as a prerequisite but does not automatically promote a gate.

### Phase 1 success: practical, not a perfect image benchmark

Agree in advance on a ten-image brief and on the owner's **“good enough”** standard. Measure actual accepted count, per-image elapsed time, resources, rejection categories, restart/failure behavior and whether the public workflow is reproducible. Do not invent a universal 90% quality threshold or claim that a fast low-quality configuration beats ComfyUI's actual quality. A target may be updated through a recorded owner decision before a new experiment; it cannot be tuned after viewing outputs to fabricate success.

### Phase 2 success: controllable visual experiments

A tested LoRA/reference recipe can create coherent batches and controlled changes without losing provenance or silently uploading private inputs. Human evaluation distinguishes identity retention, style coherence and requested changes. Changes to hairstyle, beard, hair color or body shape are **illustrative visual simulations**, not predictions about the person's real body.

## How to use this with GitHub Issues and agents

- **Research tickets** require a question, primary sources, alternative hypotheses, rights/compatibility risks, a decision artifact and follow-on experiments. Don't create feature PRs merely to claim research progress.
- **Implementation tickets** require an architecture decision, one acceptance test per bounded PR, tests on actual PR head and explicit backend limitations. The cloud lane cannot claim physical VRAM or human quality from mocked CI.
- **Experimental tickets** require owner authorization separately from issue assignment, concrete RAM/VRAM/time/attempt stops, a failure-preserving log, baseline, declared quality assessment and independent review. Local agent owns hardware execution.
- **Acceptance tickets** require owner review of real artifacts and clear evidence. Good-looking synthetic fixtures or low GPU latency alone are insufficient.
- Before starting, read issue [#9](https://github.com/interzettel/prehnite/issues/9), claim a specific **existing** issue and proposed milestone task, check the active branch/PR, and post dated findings afterward. The v2 register is a planning overlay; the canonical 73-task register continues to determine original atomic credit.
- Keep the two-agent WIP cap and independent PR review. Only the owner chooses final priority, model download/licence, inference budget, GPU experiments and release.

## Legacy ledger crosswalk: no disappearing obligations

The register maps all **18** unfinished original unit IDs to a relevant proposed gate or separate retained release/administrative obligations. Key distinctions:

- **P08** improvements belong near **P1-M02**; no completion before real evidence.
- **C08**, **S03**, **S05** can benefit from **P1-M04** implementation, but a ten-image test does not prove the original 90-image recovery gate, difficult-material matting or all repair behavior.
- **Q05–Q08** and **S06–S07** benefit from **P1-M05** human quality evidence, but original gold-material reference and calibrated judge acceptance remain separate.
- **C06**, **C09**, **P09** retain their original paid-provider/live-reconciliation requirements; free local execution doesn't make them completed.
- **R06**, **R08**, **R09** retain their rights, 90-image pilot and owner-approved release gates, respectively.
- **R10** (GitHub Projects sync) is separate administration. It remains counted in the historical release ledger despite not being necessary for useful image generation.

Do not silently delete, rename or mark complete any original unit/task to inflate the new product score. A future approved migration, if desired, must enumerate exact old→new IDs, carry forward true evidence, explain changed scope and separately version the reports. The proposed register is not itself that migration.

## What happens next

1. Review [PR #183](https://github.com/interzettel/prehnite/pull/183) as **strategy + proposed milestone governance**, not completed work.
2. Owner approves/adapts the eight outcomes and their gates. Only then mark the plan active by a separate reviewed change.
3. Start with **P1-M01 research** under existing #132/#134: choose model, verify legal/runtime availability, and define a realistic 8 GiB + available-host-RAM benchmark. In parallel, finish the already claimed independent PR reviews (#181 and #182).
4. For any subsequently approved P1-M02/P1-M04 real experiment, request new explicit scoped permission. A roadmap decision is never blanket GPU permission.
5. Each two-week planning review asks: **What is newly known? What capability is implemented? What result is independently measured and useful? What is still unknown?** It does not ask only how many PRs closed.

**Recommendation:** retain the original ledgers as release/compliance evidence, and—after owner approval—make this new milestone view the main product planning conversation, with each phase exited only on actual user-visible outcomes.
