# RFC — Batch objectives and Pareto evaluation

**Status:** Proposed, not implemented · **Date:** 2026-10-16 · **Issue:** [#81](https://github.com/interzettel/prehnite/issues/81)

## Executive product decision

Prehnite should be an **MIT-licensed, local-first visual production engine** that uses a common audited pipeline for three different **jobs to be done**:

| Mode | Unit of demand | Selected output | Optimization target | Proposed order |
| --- | --- | --- | --- | --- |
| **Produce** | Distinct, required asset *slots* in a brief | One validated output (plus named derivatives) **per slot** | Maximize complete-brief coverage at agreed quality and bounded cost/effort | **Current focus / first release** |
| **Explore** | One brief or concept with competing candidates | Diverse shortlist and/or chosen champion(s) | Maximize preference-qualified discoveries and shortlist coverage under a budget | Follow-on |
| **Experiment** | Controlled parameter combinations / replicate seeds | Traceable observations and comparison datasets | Maximize valid information/parameter coverage per resource | Later; specialized |

These are **workflow policies, not different providers**. All must reuse manifest validation, typed adapters, journaling, provenance, fail-closed paid recovery, cache privacy boundaries, spend consent, retries and deterministic exports. No mandatory SaaS or platform fees.

**What is real today:** a manifest lists distinct named assets; each generated asset may be compared as `enhanced_2k` versus `native_4k`, with bounded seed retries and optional two-rubric pair judgment. Candidates are chosen **within that asset**, and a final report tracks accepted deliverables. There is no general combinatorial exploration planner, multiobjective policy optimizer, calibrated aesthetic scoring, or comparative Pareto report. The demo is synthetic; the actual 90-asset live production benchmark is not certified. Refer to [architecture](ARCHITECTURE.md), [evaluation](EVALUATION.md), [economics](ECONOMICS.md), and [evidence ledger](progress/STATUS.md).

### Positioning

Suggested description:

> **Prehnite turns creative briefs into inspectable sets of usable visual assets. Explore alternatives or fulfill a batch with provider-independent generation, bounded repair and honest cost reporting — without a workflow-platform subscription.**

The current slogan “Make the batch. Keep the best.” is compelling for **Explore** but incomplete for **Produce**: choosing five excellent pictures does not fulfill a contract for ninety *different* images. Evaluate messaging with users before replacing the public tagline. Avoid unsubstantiated claims of real 4K quality, fully autonomous approval, verified billing or production readiness.

## Why the batch modes must differ

For a 90-slot production brief, an outstanding candidate for slot 1 **does not substitute** for missing slot 41. A production planner should allocate extra generations to failed or high-priority slots, not blindly concentrate the budget on whichever images score highest.

For Explore, a 20-image set of near-duplicates may be less useful than five excellent alternatives with genuinely different compositions. Thus per-image quality alone is inadequate; shortlist *coverage and diversity* matter. Diversity must be evaluated on an explicit semantic/visual notion of difference, not simply different seeds.

For Experiment, a 4-concept × 3-lighting × 4-material sweep implies 48 *configured observations* only if controls were actually held fixed; with stochastic generators, replicate seeds may be required. It supports comparative hypotheses, not automatic causal claims. For synthetic training data, evaluate downstream task utility, distribution/coverage and rights/privacy separately; photorealism alone is insufficient.

Advertising A/B tests belong to the **downstream deployment** of variants. Prehnite can produce traceable treatments, but cannot infer click/conversion lift without an appropriately randomized experiment and observed outcomes.

## Objective model: feasibility before Pareto ranking

For alternatives `x` and `y` in the **same comparison group**, using compatible metric definitions:

- Specify metric directions (minimize cost, latency, defect rate; maximize calibrated preference or completion coverage).
- First apply **hard constraints**: valid output geometry and filenames, appropriate rights/consent, required content checks, budget authorization, and any mandatory human review. Unknown mandatory constraints do **not** mean passing.
- A feasible `x` **dominates** `y` when `x` is no worse on *every* measured objective and strictly better on at least one. A **Pareto frontier** contains observed feasible alternatives not dominated by any other observed feasible alternative.
- Dominance applies to **finite, measured or explicitly labeled hypothetical** comparable values; do not coerce unknowns to zero, change judge versions/scale silently, or rank across different briefs/slots.
- A frontier is a **set of trade-offs, not one globally best choice**. Humans can choose a point using priorities, cost ceilings and quality floors. The true global frontier is generally unknown; call the output the *observed non-dominated set*.

### Comparison levels (critical)

1. **Candidate-level:** options serving **the same exact asset slot**, with equivalent requirements and judging rubric. Compare their fully burdened processing costs and quality (when calibrated); selection can still be subject to style/brand constraints.
2. **Policy/batch-level:** pipeline/provider/retry configurations run on the **same frozen 90-slot benchmark**. Compare complete-brief coverage, total run cost, eligible human-accepted quality, elapsed time and review effort. This is the right level for provider recommendations and benchmark Pareto frontiers.
3. **Set-level exploration:** rank **sets/shortlists** rather than isolated images when diversity and coverage are coupled. The best quality candidate set is not the same as the highest average score.
4. **Experiment-level:** trade information gained, completed combinations and repeatability against cost. Do not confuse aesthetic scores with research utility.

**Do not rank unrelated asset slots against one another.** An asset missing the brief is never repaired by selecting a stronger candidate for a different slot. Keep per-slot success and final batch success distinct.

### Toy illustration (NOT Prehnite results)

Candidates below share one hypothetical slot and the same fictional calibrated-quality scale, with cost measured on the same illustrative basis. Neither values nor calibration have been observed in Prehnite:

| Candidate | Cost USD | Quality / 100 | Observed-frontier status |
| --- | ---: | ---: | --- |
| A | 0.08 | 78 | Non-dominated: cheapest |
| B | 0.12 | 84 | Non-dominated: middle |
| C | 0.20 | 90 | Non-dominated: highest quality |
| D | 0.16 | 80 | **Dominated by B** |
| E | 0.24 | 87 | **Dominated by C** |

For the same deliverable and fixed hard requirements, a cost ceiling of $0.13 would select B among these options if maximizing measured quality. For a different slot, judge, or uncalibrated score, the comparison does not follow.

## Metrics: never optimize a misleading proxy alone

| Level | Primary measures | Qualification |
| --- | --- | --- |
| Brief fulfillment | Completed mandatory slots / required slots; *all-required-slots-done* boolean; human-accepted coverage with explicit unknown state | Keep rejected, skipped, awaiting-review separate; cutout and output requirements count for the relevant slot |
| Quality | Human rubric pass rate and preference distribution; judge/human agreement and calibrated per-category error; edge/alpha metrics for cutouts with ground truth | Technical validation is not perceptual quality. Judges' current 0..1 rubric values are **not calibrated probabilities** |
| Exploration | Number of acceptable distinct concepts; top-k human preference; pairwise redundancy, semantic and compositional coverage | Diversity vs consistency is a deliberate tension; quality/diversity should be scored at shortlist level |
| Experiment | Valid cells / prescribed combinations, replicates, parameter sensitivity, confidence intervals and observed downstream utility | Stochastic output and uncontrolled changes limit causal inference |
| Economics | Reservation by unique call and per final accepted slot; estimated total; partial provider-reported; independently **verified invoice**; GPU energy/human review as separate ledgers | Never call reservations an invoice or treat cache hit as erasing historic costs; zero accepted gives undefined cost/accepted |
| Throughput | End-to-end batch wall time, assets/hour, p50/p95 per slot and stage, queue wait, GPU seconds and failed/unknown timing coverage | Existing measured stage latency is **local invocation+publish only** |
| Reliability and operations | Restart-safe completion, uncertain-submission count, duplicate paid requests, bounded attempts, privacy/safety failures | A fail-closed uncertain submission must halt; zero unapproved spend is invariant, not a quality objective |

**Recommended first-release north star:** **human-accepted brief coverage under declared spend and quality limits**, with total spend, completion time and human intervention reported alongside. **Cost per accepted asset** is a useful diagnostic, not sufficient on its own: shipping 2 easy slots out of 90 may make the ratio look excellent while failing the job.

### A safer decision sequence

1. Enforce rights/security/validity and user approval for paid uploads.
2. Establish acceptable floors: required slot coverage, per-slot quality and cutout constraints, spend cap.
3. On alternatives satisfying those floors, show Pareto trade-offs for quality / cost / elapsed time / labor (or mode-specific objectives).
4. Select using the human's expressed preferences; **do not auto-infer** a universal exchange rate from 0.1 quality points to $1.
5. Bound exploration and repair: stop on hard budget/attempt ceilings, or once marginal *verified* gain becomes inadequate. Uncertain billable requests never self-retry to explore a frontier.

## Future evaluation event contract (proposal, not existing schema)

Favor an **append-only event stream / offline versioned derived report**, without modifying the v0.1 manifest or export compatibility until design acceptance:

```json
{
  "evaluation_schema_version": 1,
  "mode": "produce",
  "comparison_group": {
    "type": "batch_policy",
    "benchmark_id": "rights-cleared-90-v1",
    "benchmark_sha256": "<SHA256>",
    "rubric_id": "human-review-v1"
  },
  "alternative_id": "policy-local-A",
  "feasibility": {
    "state": "passed",
    "failed_constraints": [],
    "unknown_constraints": []
  },
  "objectives": [
    {"id": "accepted_slot_coverage", "direction": "maximize",
     "value": 0.9, "unit": "fraction", "basis": "human_review",
     "sample_size": 90, "status": "illustrative"},
    {"id": "estimated_reserved_usd_total", "direction": "minimize",
     "value": 2.4, "unit": "USD", "basis": "reserved_estimate",
     "sample_size": 90, "status": "illustrative"}
  ],
  "data_lineage": {
    "manifest_sha256": "<SHA256>", "profile_sha256": "<SHA256>",
    "judge_version": null, "provider_revision": null
  }
}
```

**The example is intentionally fictional and must not be ingested as a benchmark.** Real report records should include units, metric protocol/version, directions, whether a value is `observed` / `estimated` / `human_review` / `hypothetical` / `unknown`, evidence/sample counts, cohort IDs, observation timestamps, provenance hashes, review rubric and model version, and missingness/uncertainty. Avoid raw prompts, private images, source paths, credentials, request IDs and individual reviewer identities in automatically shared reports.

Calculation checks: duplicate alternatives, incompatible denominators, mismatched metric versions, nonfinite values, unapproved spend, impossible coverage (greater than 1), incorrectly directed objectives, and arbitrary cross-benchmark comparisons must be rejected or excluded with a reason. Cache hits must preserve historical attempt and expense accounting.

## Proposed offline report visualizations

Prioritize *diagnostics first*, Pareto analysis once valid quality/benchmark data exists:

| Chart | Axes / marks | Key decision or failure exposed | Readiness |
| --- | --- | --- | --- |
| **Mandatory-slot completion** | Asset/requirement matrix, colored by accepted/rejected/pending/unknown | What is missing before delivery? | Build with offline 90-slot fixture |
| **Acceptance funnel** | Requested slots → generated → technical-pass → visual-review → complete | Where is capacity and budget lost? | Build with provenance and review-state distinctions |
| **Cost & retries** | Waterfall/stacked estimated reservations by stage, failures, cache, retries; separate actual-invoice panel | Why did the batch cost this amount, and what remains unknown? | Estimate-first; invoice plot only after #17 |
| **Observed Pareto plot** | x total comparable cost (lower better), y calibrated usable coverage/quality (higher better); frontier highlighted, dominated points muted; optional facet for latency | Which provider/policy choices offer meaningful trade-offs? | Disabled as *real quality frontier* until #28/#41/#42 evidence |
| **Best-of-N marginal gain** | Generation attempts or incremental reserved spend vs highest *human-rated* quality / distinct accepted concepts | When should Explore stop purchasing samples? | Human calibration required |
| **Coverage vs diversity/consistency** | Small multiples by brief category or slot family; group-level metrics and cohort sizes | Have we produced duplicates or broken a brand family? | Needs explicit semantic/rubric definitions |
| **Quality disagreement** | Human–judge confusion/calibration by category and score band; disagreement/abstentions | Is automatic rejection safe for this content? | Needs rights-cleared human reference set #28 |
| **Run comparison** | Paired benchmark table/distribution by prompt category, model revision, machine and sample size | Has a change improved 90-slot productivity *without* breaking quality? | Real pilot and repeat runs |

Every chart needs explicit axes, units, observed vs estimated labels, N/sample coverage, missing-data indication, comparison group, evidence link and selection/facet controls. HTML must run **offline without external CDNs**; JSON/CSV (Parquet later) must expose the underlying rows so the dashboard is auditable. No chart should convert ordinal scores into physical quantities, probabilities or dollars.

**Pareto measurement note:** optional hypervolume, knee-point analysis and relative frontier-improvement curves are **secondary**. They require fixed objective normalization, reference point and comparable observed tasks. Hypervolume computed with a moving reference point is not suitable for honest cross-run progress claims. With few candidates, plain scatter and dominance explanation are enough.

## Validation and release evaluation design

### Pre-release fixed 90-asset benchmark

- Freeze a **rights-cleared**, representative 90-slot mixed-resolution/cutout manifest, instructions, acceptance rubric, model/profiles and relevant hardware/driver versions. Mark which are reproducible mocks and which require explicit paid/GPU execution.
- Compare a transparent **one-candidate-per-slot** baseline to bounded retry/variant selection and targeted repair, using the *same slot set and target outputs*. Paired comparisons reduce confounding.
- Record complete coverage, per-requirement correctness, cutout alpha/edge ground truth when available, accepted image quality on full frames and **native 4K crops**, quality-review disagreement, duplicates, reliability/restart outcomes, complete time coverage, and all separately grounded cost bases.
- Require blinded or counterbalanced **human review** before making comparative aesthetic claims. Report denominators, intervals where feasible, per-category differences and uncertainty, not just a single average. If assessors disagree, retain and investigate disagreement.
- Do not claim production readiness from the 90-item **synthetic offline fixture** alone. Live provider pricing/invoices, local RTX 4070 8 GB viability, difficult materials and paid-run reconciliation stay independently gated.
- Quality and operating thresholds must be accepted by the owner based on pilot evidence; do **not** invent universal 0.8 visual pass scores or dollar-per-asset targets.

### First shippable slices and existing issues

1. **Immediate:** approve/iterate this RFC (#81). No counted ledger work unit or production-readiness gate changes; document Produce-first default and comparison semantics.
2. **Offline analytics (#6 and #41):** instrument per-slot required outcomes, comparable policy-run exports, acceptance funnel, cost provenance and 90-slot dry-run. No aesthetic Pareto claims from synthetic fixtures.
3. **Calibrated quality (#28, #27, #31, #32):** anchor visual judgments to humans and alpha-ground-truth tasks before using quality coordinates or automatic policy optimization.
4. **Reliability (#38) and release (#42):** build safe MCP lifecycle and genuinely validate a complete production run; reconcile charges via #17.
5. **Later distinct implementation issues:** Explore candidate-plan syntax, diversity-aware shortlist selection and diminishing-return stopping; Experiment sweep/seed-replicate spec; privacy-safe offline Pareto report with schema tests, comparable cohorts, and optional hypervolume. These should each get **separate** reviewable scopes after RFC decision.

**No release claim:** #81 and this document are a planning/evaluation contribution, not evidence that the runtime implements these modes, provides calibrated human quality or optimizes a Pareto frontier.

## Sources and methodology

- [BoTorch multiobjective documentation](https://github.com/meta-pytorch/botorch/blob/main/docs/multi_objective.md): Pareto non-dominance and trade-offs.
- [pymoo convergence and hypervolume guide](https://pymoo.org/getting_started/part_4.html): objective normalization, reference-point choice and approximate frontiers.
- [Google Research, CVPR 2024: Rethinking FID](https://research.google/pubs/rethinking-fid-towards-a-better-evaluation-metric-for-image-generation/): pitfalls of distribution-level image metrics and disagreement with human assessment.
- [NIST GenAI evaluations](https://ai-challenges.nist.gov/genai): task-specific assessments and human studies.
- [Prehnite #6 reporting](https://github.com/interzettel/prehnite/issues/6), [#28 human calibration](https://github.com/interzettel/prehnite/issues/28), [#38 MCP](https://github.com/interzettel/prehnite/issues/38), [#41 offline 90-slot dry-run](https://github.com/interzettel/prehnite/issues/41), and [#42 owner production acceptance](https://github.com/interzettel/prehnite/issues/42).
