# Prehnite — agile iteration board

> Generated from [`project/board.json`](../project/board.json); use `python scripts/board.py --write` to refresh. GitHub issues and PRs are the authoritative live evidence. The native [organization GitHub Project #1](https://github.com/orgs/interzettel/projects/1) exists but sync is not automated. This checked-in snapshot may differ from live card fields; see issue #44.

**Iteration:** I-01 — Reliability and project governance  
**Planning window:** 2026-10-16 → 2026-10-30 (review, **not** release deadline)  
**Goal:** Publish credible development milestones, readable onboarding, and a recoverable low-cost batch-engine backlog.

## Flow overview

| Lane | Cards |
| --- | ---: |
| Backlog | 14 |
| Ready | 2 |
| In progress | 1 |
| In review | 1 |
| Blocked | 8 |
| Done | 49 |

**WIP limits:** In progress ≤ 2; In review ≤ 3. Counts are issue/PR cards, not unique completed engineering features or a percentage.

## Backlog

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P2 | [Issue #2 — ComfyUI integration on real hardware](https://github.com/interzettel/prehnite/issues/2) | Local GPU | Generic adapter exists; hardware and actual workflow integration remain. |
| P1 | [Issue #3 — Reliable segmentation and matting](https://github.com/interzettel/prehnite/issues/3) | Quality | Blocked downstream on model contracts and sample corpus. |
| P2 | [Issue #4 — Local quality judges and crop QA](https://github.com/interzettel/prehnite/issues/4) | Quality | Must calibrate before quality gates use local scores. |
| P2 | [Issue #6 — Offline visual reports and exports](https://github.com/interzettel/prehnite/issues/6) | Delivery | Analytics gallery implemented in PR #90; Parquet separately stacked #92. |
| P2 | [Issue #8 — Windows MCP lifecycle and packaging](https://github.com/interzettel/prehnite/issues/8) | Runtime | Process cancellation, reconnection and Windows tests. |
| P0 | [Issue #5 — Crash recovery, pricing and billing hardening](https://github.com/interzettel/prehnite/issues/5) | Reliability | Safety tranche #10 merged; remaining tasks #15–#18, ownership unclaimed. |
| P2 | [Issue #44 — Synchronize canonical issue ledger with organization GitHub Projects v2](https://github.com/interzettel/prehnite/issues/44) | Tracking | GitHub Project #1 sync needs Projects v2 write permission |
| P1 | [Issue #40 — Model, dependency and artifact licensing inventory](https://github.com/interzettel/prehnite/issues/40) | Licensing | Dependency/model weight terms inventory |
| P1 | [Issue #33 — Self-contained offline HTML gallery and comparisons](https://github.com/interzettel/prehnite/issues/33) | Reporting | Offline thumbnail gallery #67 merged; opt-in private original comparisons remain issue #68 |
| P1 | [Issue #31 — Targeted repair planner for failed cutouts](https://github.com/interzettel/prehnite/issues/31) | Cutouts | Bounded repair planner |
| P2 | [Issue #30 — Multi-instance object cutout selection](https://github.com/interzettel/prehnite/issues/30) | Cutouts | Multi-instance target matching |
| P1 | [Issue #29 — Transparent alpha matting and halo removal](https://github.com/interzettel/prehnite/issues/29) | Cutouts | Edge alpha matting |
| P2 | [Issue #27 — Local aesthetic and fidelity judge plugin boundary](https://github.com/interzettel/prehnite/issues/27) | Quality | Optional local weights and licenses |
| P1 | [Issue #68 — Opt-in original-input gallery comparison with privacy consent](https://github.com/interzettel/prehnite/issues/68) | Delivery | Follow-up to #33: never embed private originals without opt-in |

## Ready

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P1 | [Issue #12 — Mocked fal API conformance contract](https://github.com/interzettel/prehnite/issues/12) | Providers | No credentials or paid calls; use recorded fixture schemas. |
| P1 | [Issue #25 — Judge schema and A/B order-bias tests](https://github.com/interzettel/prehnite/issues/25) | Quality | Typed verdict tranche merged in #61; controlled same-rubric A/B positional-bias measurement (Q03) remains unverified |

## In progress

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P1 | [Issue #89 — Offline analytics panels and versioned summary exports](https://github.com/interzettel/prehnite/issues/89) | Delivery | Green cross-platform synthetic dashboard PR #90; merge pending. |

## In review

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P1 | [PR #90 — Offline analytics dashboard and summary exports](https://github.com/interzettel/prehnite/pull/90) | Delivery | Reconciled after failure taxonomy #87; cross-platform CI required. |

## Blocked

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P1 | [Issue #7 — Real fal/Haiku credentialed integration](https://github.com/interzettel/prehnite/issues/7) | Providers | Owner must authorize actual paid/API calls separately. |
| P1 | [Issue #42 — Owner-accepted production benchmark and release gate](https://github.com/interzettel/prehnite/issues/42) | Release | Owner acceptance and authorized live pilot |
| P1 | [Issue #32 — Cutout quality benchmark with difficult materials](https://github.com/interzettel/prehnite/issues/32) | Cutouts | Rights-cleared alpha reference data |
| P1 | [Issue #28 — Reference corpus and human calibration protocol](https://github.com/interzettel/prehnite/issues/28) | Quality | Owner-approved reference images / human calibration |
| P1 | [Issue #24 — 8GB VRAM local inference feasibility benchmark](https://github.com/interzettel/prehnite/issues/24) | Local GPU | Await local RTX 4070 laptop benchmark |
| P1 | [Issue #17 — Persist pricing assumptions and reconcile actual bills](https://github.com/interzettel/prehnite/issues/17) | Economics | Live billing access needs explicit authorization |
| P2 | [Issue #91 — Optional typed Parquet exports for offline analytics](https://github.com/interzettel/prehnite/issues/91) | Delivery | Stacked PR #92 depends on #90; optional PyArrow. |
| P2 | [PR #92 — Typed opt-in Parquet metric and slot datasets](https://github.com/interzettel/prehnite/pull/92) | Delivery | Green prior CI; rebase against main after #90 merge. |

## Done

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P1 | [Issue #11 — Agile tracking and release governance](https://github.com/interzettel/prehnite/issues/11) | Governance | Issue/PR templates, changelog and version policy merged via #13. |
| P0 | [PR #10 — Fail-closed paid recovery and evidence chart](https://github.com/interzettel/prehnite/pull/10) | Reliability | Merged into main; offline safety regression tests passed. |
| P1 | [PR #13 — Agile delivery board and release governance](https://github.com/interzettel/prehnite/pull/13) | Governance | Merged to main; single-source versioning and governance CI. |
| P0 | [PR #1 — Initial MIT engine foundation](https://github.com/interzettel/prehnite/pull/1) | Foundation | Merged; synthetic demo CI passed. |
| P1 | [Issue #43 — Human-centered README, original vector identity and first-run guide](https://github.com/interzettel/prehnite/issues/43) | Onboarding | Merged in PR #45; evidence ledger / README published on main. |
| P1 | [Issue #41 — Pre-release 90-asset dry run and budget projection](https://github.com/interzettel/prehnite/issues/41) | Benchmark | PR #84 merged; 90/90 offline benchmark passed on Ubuntu & Windows, 108 verified ZIP image entries. |
| P1 | [Issue #39 — Cross-platform installer and Python packaging smoke checks](https://github.com/interzettel/prehnite/issues/39) | Packaging | Merged PR #72; validated free CLI and clean Windows/Linux wheel install, GPU not benchmarked |
| P1 | [Issue #38 — MCP cancellation, worker reconnection and status telemetry](https://github.com/interzettel/prehnite/issues/38) | MCP | PR #83 merged as 38113a7; four-job CI green (290 tests), issue closed. |
| P1 | [Issue #37 — Prehnite init and doctor CLI onboarding](https://github.com/interzettel/prehnite/issues/37) | Onboarding | Merged PR #71; validated free CLI and clean Windows/Linux wheel install, GPU not benchmarked |
| P1 | [Issue #36 — Deterministic validated archive and manifest hashes](https://github.com/interzettel/prehnite/issues/36) | Reporting | Implemented and verified in merged PR #76, zero inference spend |
| P1 | [Issue #35 — Versioned provenance and reproducible output manifest](https://github.com/interzettel/prehnite/issues/35) | Reporting | Implemented and verified in merged PR #74, zero inference spend |
| P1 | [Issue #34 — Cost per accepted asset and stage latency report](https://github.com/interzettel/prehnite/issues/34) | Reporting | Offline accepted-asset estimate economics and attempt timings, merged PR #78; invoice audit #17 blocked |
| P1 | [Issue #26 — Full-resolution crops for visual quality gating](https://github.com/interzettel/prehnite/issues/26) | Quality | Merged PR #65: native-pixel 4K crops, lossless PNG and verified hash evidence; 207 CI tests |
| P1 | [Issue #23 — ComfyUI queue resume and error-state contract](https://github.com/interzettel/prehnite/issues/23) | Local GPU | Merged PR #59: offline ComfyUI queue recovery; 163 tests passed |
| P1 | [Issue #22 — ComfyUI reproducible API graph fixtures](https://github.com/interzettel/prehnite/issues/22) | Local GPU | Offline API graph/node mapping and queue fixtures merged in PR #57; no GPU benchmark |
| P1 | [Issue #21 — Provider capability and price registry contract](https://github.com/interzettel/prehnite/issues/21) | Providers | Typed adapter registry and user-estimate provenance merged in PR #55; real quote audit remains #17 |
| P1 | [Issue #20 — Normalize fal segmentation output and mask orientation](https://github.com/interzettel/prehnite/issues/20) | Segmentation | Offline CI tests merged in PR #53; real paid/live validation remains open |
| P1 | [Issue #19 — Mocked FLUX tier and upscale response shapes](https://github.com/interzettel/prehnite/issues/19) | Providers | Mocked and subprocess CI evidence in merged PR #50 |
| P1 | [Issue #18 — Content-addressed cache with privacy isolation](https://github.com/interzettel/prehnite/issues/18) | Runtime | Cache code merged #80; evidence reconciliation #88 merged. |
| P0 | [Issue #16 — Atomic artifacts and integrity-aware resume](https://github.com/interzettel/prehnite/issues/16) | Runtime | Offline CI tests merged in PR #52; real paid/live validation remains open |
| P0 | [Issue #15 — Crash-injection matrix for billed request recovery](https://github.com/interzettel/prehnite/issues/15) | Runtime | Mocked and subprocess CI evidence in merged PR #49 |
| P1 | [Issue #14 — Granular evidence-ledger and generated milestone progress tracker](https://github.com/interzettel/prehnite/issues/14) | Tracking | Merged in PR #45; evidence ledger / README published on main. |
| P1 | [PR #45 — Original identity and evidence-based milestone ledger](https://github.com/interzettel/prehnite/pull/45) | Governance | Merged to main; 47 offline tests passed. |
| P1 | [Issue #46 — Merge-state reconciliation and CI hygiene](https://github.com/interzettel/prehnite/issues/46) | Maintenance | CI warnings resolved with 47/47 passing in merged PR #47. |
| P1 | [PR #47 — Reconcile tracker and modernize CI](https://github.com/interzettel/prehnite/pull/47) | Maintenance | Merged; 47 tests passing without warnings. |
| P1 | [PR #49 — Subprocess crash-recovery matrix](https://github.com/interzettel/prehnite/pull/49) | Runtime | Merged after passing offline tests; no paid inference |
| P1 | [PR #50 — fal generation payload and queue contract fixtures](https://github.com/interzettel/prehnite/pull/50) | Providers | Merged after passing offline tests; no paid inference |
| P0 | [PR #52 — Atomic accepted assets and SHA256 integrity](https://github.com/interzettel/prehnite/pull/52) | Runtime | Merged, 90 offline tests passed |
| P1 | [PR #53 — SAM 3.1 mask geometry and channel contracts](https://github.com/interzettel/prehnite/pull/53) | Cutouts | Merged, 100 offline tests passed |
| P1 | [PR #55 — Typed provider capability preflight](https://github.com/interzettel/prehnite/pull/55) | Providers | Merged to main; 127 offline tests passed; no live pricing |
| P1 | [PR #57 — ComfyUI offline graph and HTTP fixtures](https://github.com/interzettel/prehnite/pull/57) | Local GPU | Merged; 139 offline tests passed, no local model weights |
| P1 | [PR #59 — ComfyUI fail-closed queue recovery and bounded result download](https://github.com/interzettel/prehnite/pull/59) | Local GPU | Merged; 163 offline tests passed. No GPU/model conformance claimed. |
| P1 | [PR #61 — Strict optional judge verdict schemas and rubric disagreement](https://github.com/interzettel/prehnite/pull/61) | Quality | Merged; 185 offline tests passed. Real judge calibration unresolved. |
| P1 | [Issue #63 — Controlled A/B positional-bias protocol and disagreement calibration](https://github.com/interzettel/prehnite/issues/63) | Quality | Offline fixed-rubric positional measurement PR #70; human judge calibration still pending |
| P1 | [PR #65 — Native-pixel crop evidence and offline CLI](https://github.com/interzettel/prehnite/pull/65) | Quality | Merged to main; 207 tests passed. No model-quality certification. |
| P1 | [PR #67 — Self-contained offline asset review gallery](https://github.com/interzettel/prehnite/pull/67) | Delivery | Merged; 212 offline tests. No external web resources or paid calls. |
| P1 | [PR #70 — Fixed-rubric A/B positional-bias protocol](https://github.com/interzettel/prehnite/pull/70) | Quality | Merged; 226 offline tests passed |
| P1 | [PR #71 — Offline init and doctor CLI](https://github.com/interzettel/prehnite/pull/71) | Onboarding | Merged; 239 offline tests passed |
| P1 | [PR #72 — Cross-platform clean wheel/sdist install verification](https://github.com/interzettel/prehnite/pull/72) | Packaging | Merged; Windows + Ubuntu CI clean installs passed |
| P1 | [PR #74 — Privacy-minimized provenance manifest](https://github.com/interzettel/prehnite/pull/74) | Delivery | Merged with green CI and offline regression tests |
| P1 | [PR #76 — Deterministic ZIP and SHA256 receipt](https://github.com/interzettel/prehnite/pull/76) | Delivery | Merged with green CI and offline regression tests |
| P1 | [PR #78 — Evidence-based accepted-asset economics and stage timing](https://github.com/interzettel/prehnite/pull/78) | Reporting | Merged; 264 offline tests and Windows/Ubuntu smoke green; invoices remain unverified |
| P1 | [PR #83 — Durable MCP pause/cancel/reconnect and worker ownership](https://github.com/interzettel/prehnite/pull/83) | MCP | Merged into main; durable MCP controls verified with Windows lifecycle regression. |
| P1 | [PR #84 — 90-slot offline pause/crash/recovery benchmark](https://github.com/interzettel/prehnite/pull/84) | Benchmark | Merged PR #84; cross-platform CI synthetic recovery benchmark evidence; no paid inference. |
| P1 | [Issue #86 — Machine-readable stage failure and recovery taxonomy](https://github.com/interzettel/prehnite/issues/86) | Runtime | Typed error taxonomy code merged PR #87; C10 ledger credit pending. |
| P1 | [PR #87 — Typed fail-closed failure classification and report telemetry](https://github.com/interzettel/prehnite/pull/87) | Runtime | Merged PR #87 with validated CI; ledger credit C10 pending. |
| P1 | [PR #88 — Reconcile C07 merged cache evidence and progress tracker](https://github.com/interzettel/prehnite/pull/88) | Tracking | Evidence PR #88 merged after preserving #87; C07 credited. |
| P1 | [Issue #81 — Batch objective modes and Pareto evaluation RFC](https://github.com/interzettel/prehnite/issues/81) | Product strategy | RFC PR #82 merged; produce-first design only, no runtime gate credit. |
| P1 | [PR #82 — Produce/Explore/Experiment and Pareto reporting RFC](https://github.com/interzettel/prehnite/pull/82) | Product strategy | Documentation RFC integrated; human quality and comparable cohorts still future. |

## How to update this board

1. Update the relevant issue/PR and post an A2A handoff on [#9](https://github.com/interzettel/prehnite/issues/9).
2. Move the card's `lane` (or add a new card) in `project/board.json`; keep tickets unique by `(type, number)`.
3. Run `python scripts/board.py --write` then `python scripts/board.py --check`, commit both files in the same PR.
4. CI verifies that status snapshot matches the machine-readable board and WIP caps.
5. Track **release evidence** separately in `docs/PROGRESS.md` (introduced by PR #10); this board tracks workflow, not model performance.

**Release policy:** No tags, releases or uploads have been authorized. See [versioning](VERSIONING.md), [changelog](../CHANGELOG.md) and [release process](RELEASING.md).
