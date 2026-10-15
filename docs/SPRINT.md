# Prehnite — agile iteration board

> Generated from [`project/board.json`](../project/board.json); use `python scripts/board.py --write` to refresh. GitHub issues and PRs are the authoritative live evidence. This is an offline planning snapshot, **not** a native GitHub Projects board.

**Iteration:** I-01 — Reliability and project governance  
**Planning window:** 2026-10-16 → 2026-10-30 (review, **not** release deadline)  
**Goal:** Make the local-first engine dependable and give every future change traceable issue, PR, version, and evidence.

## Flow overview

| Lane | Cards |
| --- | ---: |
| Backlog | 5 |
| Ready | 1 |
| In progress | 2 |
| In review | 1 |
| Blocked | 1 |
| Done | 1 |

**WIP limits:** In progress ≤ 2; In review ≤ 3. Counts are issue/PR cards, not unique completed engineering features or a percentage.

## Backlog

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P2 | [Issue #2 — ComfyUI integration on real hardware](https://github.com/interzettel/prehnite/issues/2) | Local GPU | Generic adapter exists; hardware and actual workflow integration remain. |
| P1 | [Issue #3 — Reliable segmentation and matting](https://github.com/interzettel/prehnite/issues/3) | Quality | Blocked downstream on model contracts and sample corpus. |
| P2 | [Issue #4 — Local quality judges and crop QA](https://github.com/interzettel/prehnite/issues/4) | Quality | Must calibrate before quality gates use local scores. |
| P2 | [Issue #6 — Offline visual reports and exports](https://github.com/interzettel/prehnite/issues/6) | Delivery | Need contact sheets, per-asset comparators and analytics. |
| P2 | [Issue #8 — Windows MCP lifecycle and packaging](https://github.com/interzettel/prehnite/issues/8) | Runtime | Process cancellation, reconnection and Windows tests. |

## Ready

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P1 | [Issue #12 — Mocked fal API conformance contract](https://github.com/interzettel/prehnite/issues/12) | Providers | No credentials or paid calls; use recorded fixture schemas. |

## In progress

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P0 | [Issue #5 — Crash recovery, pricing and billing hardening](https://github.com/interzettel/prehnite/issues/5) | Reliability | Safety tranche in PR #10; remainder stays open. |
| P1 | [Issue #11 — Agile tracking and release governance](https://github.com/interzettel/prehnite/issues/11) | Governance | This change on chore/agile-version-governance. |

## In review

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P0 | [PR #10 — Fail-closed paid recovery and evidence chart](https://github.com/interzettel/prehnite/pull/10) | Reliability | Tests pass; awaiting review and merge. |

## Blocked

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P1 | [Issue #7 — Real fal/Haiku credentialed integration](https://github.com/interzettel/prehnite/issues/7) | Providers | Owner must authorize actual paid/API calls separately. |

## Done

| Priority | Work item | Stream | Handoff / blocker |
| --- | --- | --- | --- |
| P0 | [PR #1 — Initial MIT engine foundation](https://github.com/interzettel/prehnite/pull/1) | Foundation | Merged; synthetic demo CI passed. |

## How to update this board

1. Update the relevant issue/PR and post an A2A handoff on [#9](https://github.com/interzettel/prehnite/issues/9).
2. Move the card's `lane` (or add a new card) in `project/board.json`; keep tickets unique by `(type, number)`.
3. Run `python scripts/board.py --write` then `python scripts/board.py --check`, commit both files in the same PR.
4. CI verifies that status snapshot matches the machine-readable board and WIP caps.
5. Track **release evidence** separately in `docs/PROGRESS.md` (introduced by PR #10); this board tracks workflow, not model performance.

**Release policy:** No tags, releases or uploads have been authorized. See [versioning](VERSIONING.md), [changelog](../CHANGELOG.md) and [release process](RELEASING.md).
