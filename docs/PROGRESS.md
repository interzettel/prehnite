# Prehnite — delivery readiness and work limits

**Baseline:** 2026-10-16 · Source of truth: GitHub [issues](https://github.com/interzettel/prehnite/issues), [PRs](https://github.com/interzettel/prehnite/pulls), [CI](https://github.com/interzettel/prehnite/actions), and [A2A log #9](https://github.com/interzettel/prehnite/issues/9).

![Delivery release-gate chart](./progress.svg)

## Reading this chart

There are **16 release gates**, each counted once. **4 have reproducible evidence, 7 have partial implementation, and 5 are unverified.** These are **not equally sized tasks**, so 4/16 is **not** a claim that 25% of engineering work or model quality is complete. In particular, green unit tests on a synthetic demo do *not* prove real image generation, visual correctness or production suitability.

| Gate | Scope | Evidence level | What is actually known / remaining |
|---|---|---|---|
| G01 | MIT package and install/CI | Verified | Public MIT license, Python wheel contract, GitHub Actions passed |
| G02 | Manifest/output security checks | Verified | Path traversal, collisions, ratio and size unit tests |
| G03 | Zero-cost synthetic batch | Verified | Offline two-asset demo end-to-end and repeat-run tests |
| G04 | ZIP/report integrity | Verified | ZIP filenames, CRC and reports tested on demo |
| G05 | Provider-independent hosted APIs | Partial | fal adapter written; current endpoint input/output contracts not smoke-tested |
| G06 | Local ComfyUI support | Partial | Loopback graph API and basic unit tests; no validated local model workflow or VRAM measurements |
| G07 | Model-based image judge | Partial | Haiku rubric implementation; no API validation, image quality calibration or crop checks |
| G08 | Object cutouts and refinement | Partial | Mask-to-alpha demo checks; real SAM/matting accuracy not tested |
| G09 | Durable restart and remote-id recovery | Partial | Mocked replay/uncertain-call tests and exclusive process lock; real crash injection pending |
| G10 | Estimated spending limits | Partial | Offline reserved-cost tests and preflight prices; live rates/invoices not verified |
| G11 | MCP worker and exports | Partial | stdio entrypoint and subprocess implemented; live agent disconnect/cancel not verified |
| G12 | Evaluator calibration and high-res QA | Unverified | Need local judges, test assets and crop/edge evaluation |
| G13 | Real provider billing reconciliation | Unverified | Need documented billing integration and paid pilot |
| G14 | 10-asset credentialed integration pilot | Unverified | Requires separately authorized paid calls |
| G15 | 90-asset mixed-format production pilot | Unverified | Requires quality, cost and restart evidence |
| G16 | Windows GPU, security and operations | Unverified | Hardware verification, threat model, license audit, lifecycle tests |

**Critical path:** #5 recovery/billing → #7 provider conformance pilot → #3 segmentation/matting → #4 typed quality judges → #2 local workflows → #6 analytics → #8 Windows/MCP lifecycle. Other safe tasks can proceed concurrently only if separate agents coordinate via #9.

## Limits of work: binding constraints

| Limit | Operational rule |
|---|---|
| API spend | **$0 unless user explicitly authorizes that particular paid experiment**. No automatic cloud inference, image uploads or judge tokens |
| SaaS / platform fees | **$0**. MIT Python core and optional separately installed open-source tools only |
| Run scope | One bounded, reviewable change per interactive/scheduled execution; no promise of continuous unsupervised work |
| PRs | No unchecked writes to \`main\`; open feature branches, require CI/review, no future auto-merges without approval |
| Cost certainty | Reserves are configured estimates, *not* billing guarantees. Without live provider prices, refuse missing estimates; ambiguous submissions fail closed |
| Retry caps | Per asset, at most configured \`maximum_attempts\` (1–10); no endless judge/generation loop |
| Concurrency | One active batch worker per batch ID via OS-level file lock; different batch IDs can run separately |
| Outputs | Strict archive-relative filenames; source under allowlisted input root; only accepted assets enter delivery ZIP |
| GPU | No promise of 4K local viability on an 8GB GPU until actual VRAM/performance tests |
| Quality | Technical checks ≠ perceptual accuracy. With visual judge absent, acceptance needs explicit \`accept_unverified\` policy |
| Session continuity | GitHub issue #9 and this document are durable memory; no assumption another session inherits scratchpad/context |
| Dependency licenses | No bundled model weights; independently evaluate checkpoints and dependency licenses before release |

## Work log / milestones

- **2026-10-16:** v0.1 foundation merged with CI and MIT license ([PR #1](https://github.com/interzettel/prehnite/pull/1)).
- **2026-10-16:** #5 safety tranche in progress: deny uncertain paid re-submissions; tighten estimate preflight; one-worker batch lock; regression tests (see corresponding PR).
- No live paid model executions have been performed or validated by this project.

For a new session or another agent: read \`AGENTS.md\`, this file and **A2A #9**, check active branches/PRs, then claim a small scoped issue before changing code. Update chart statuses **only with inspectable evidence**, never by intuition.
