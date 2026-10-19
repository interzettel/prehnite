# v1 → v2 roadmap migration — single canonical product scoreboard

**Migration intent authorized:** 2026-10-19 (owner requested one canonical product roadmap).  
**Implementation:** reviewable [PR #183](https://github.com/interzettel/prehnite/pull/183); becomes authoritative on merge, not before.  
**Active source after merge:** [progress/roadmap.json](../progress/roadmap.json).  
**Generated dashboard:** [docs/progress/STATUS.md](progress/STATUS.md), by `python scripts/roadmap.py --write`.

## Why this is a migration, not a new parallel percentage

v1 measured original release and infrastructure obligations (43/61 verified) and an independent scoped atomic backlog (21/73 done). Those scopes do not directly answer whether an **8 GiB laptop user gets useful, reproducible image results**.

v2 is one hierarchy only: **Phase → Outcome milestone → Evidence-gated task → Actual proof**. It covers Phase 1 (efficient 8 GiB generation and batches) and Phase 2 (LoRA/controlled appearance experimentation); no Phase 3. There is no 4 GiB/6 GiB qualification program. Experimental GPU runs, private images and paid API calls always require separate owner authorization.

## Historical preservation and measurable credit

These original exact v1 artifacts have been frozen by Git blob identity, not silently rewritten:

| Archived artifact | Purpose |
| --- | --- |
| [progress/archive/v1/ledger.json](../progress/archive/v1/ledger.json) | 61 original release units, 43 complete, 18 open; all original evidence/conditions |
| [progress/archive/v1/atomic.json](../progress/archive/v1/atomic.json) | Frozen 73-task register, 21 done, 52 unfinished |
| [docs/archive/v1/STATUS.md](archive/v1/STATUS.md) | Original release-status report |
| [docs/archive/v1/ATOMIC.md](archive/v1/ATOMIC.md) | Original atomic-status report |
| [docs/archive/v1/progress.svg](archive/v1/progress.svg) and [atomic.svg](archive/v1/atomic.svg) | Original generated charts |
| [scripts/archive/v1/progress.py](../scripts/archive/v1/progress.py) and [atomic_progress.py](../scripts/archive/v1/atomic_progress.py) | Original generators retained for provenance, no longer run as active CI progress |

**Transfer policy:** The six original F01–F06 units independently verify an installable, safe **synthetic** foundation. They are carried to **P1-M00**, with the unchanged linked merged PR evidence. This yields **1/9 verified product milestones and 6/26 verified tasks**. Those values are *not* numerical conversions of 43/61 or 21/73.

The other 37 previously done v1 units are **not discarded**: their merged PR evidence persists in the archive and live code. They are also **not automatically credited** as full new outcomes just because their IDs sound similar. As the team reaches a new gate, it may evaluate and reference the old work, alongside any new real-machine and human-acceptance evidence the gate requires.

A ten-image local batch is a useful v2 acceptance target. It does **not** silently close the original 90-image live pilot, cost reconciliation or full release criteria.

## Crosswalk: every one of the 18 unfinished original units

| Original ID | Relevant v2 milestone | Relationship | Remaining original obligation |
| --- | --- | --- | --- |
| C06 | P1-M05 | legacy release only | Actual billed quote reconciliation is separate from optional-free local use. |
| C08 | P1-M04 | partial overlap | 10-image interruption test does not satisfy the legacy 90-image gate. |
| C09 | P1-M05 | legacy release only | Real-provider billed cost evidence still required for legacy release. |
| P08 | P1-M02 | direct | Actual 8 GiB local baseline; original P08 criteria remain independent. |
| P09 | P1-M05 | legacy release only | Hosted paid live pilot remains a separate authorized release gate. |
| P10 | P1-M01 | partial overlap | Research helps provider-choice plan; original acceptance separately assessed. |
| Q05 | P1-M05 | partial overlap | Human selection does not magically certify optional local AI judges. |
| Q06 | P1-M05 | partial overlap | Ten-image real references do not necessarily fulfill rights-cleared diverse reference-set contract. |
| Q07 | P1-M05 | partial overlap | Human batch acceptance differs from calibrated quality thresholds. |
| Q08 | P1-M05 | partial overlap | Batch review not sufficient for robust cross-judge/repair validation. |
| S03 | P1-M04 | partial overlap | Soft matte real hard-material solution remains distinct from generation/batching. |
| S05 | P1-M04 | partial overlap | 10-image interruption does not prove full targeted repair acceptance. |
| S06 | P1-M05 | partial overlap | Alpha scoring gold references remain separate evidence. |
| S07 | P1-M05 | partial overlap | One batch cannot guarantee acceptance of all difficult materials. |
| R06 | P1-M05 | partial overlap | Final rights audit must still be accepted against original unit. |
| R08 | P1-M05 | legacy release only | Original 90-image live pilot is not replaced by a 10-image local pilot. |
| R09 | P1-M05 | legacy release only | Package tag/first release always requires explicit owner approval. |
| R10 | Historical / separate obligation | separate administration | GitHub Projects synchronization is non-product-critical but stays in legacy 61-unit ledger. |

These historical obligations are explicitly mapped for traceability. For some, completion is **outside** the new two-phase first-product scope. That means *deferred or separately considered*, never falsely marked done or erased from historical record. A later decision to reintroduce an obligation requires a new reviewed v2 gate and clearly identified acceptance criteria.

## What counts as research, implementation, experiment and acceptance

A verified **research** task needs credible primary sources, comparison and a reviewed decision. A verified **implementation** task needs merged reviewed code and exact-head CI. A verified **real experiment** needs explicit owner permission, measured and inspectable real-device receipts and independent review (synthetic CI alone does not suffice). **Owner/human acceptance** requires an explicit review of the appropriate real outputs or rights/privacy decision. The roadmap validator enforces the kind of evidence required.

Review P1-M01 research and the current PRs #181/#182 first; neither is automatically marked v2 verified by this migration. For P1-M02, the fixed P08-A03 bounds and real-run authorization rules still apply. No blanket execution permission is inferred by signing off on roadmap governance.

## Governance and future changes

- **Single current dashboard:** [docs/progress/STATUS.md](progress/STATUS.md). No live 61-unit or 73-task percentages are displayed in main navigation or generated output headers.
- **Single source:** [progress/roadmap.json](../progress/roadmap.json). Agents claim these v2 task IDs on coordination [issue #9](https://github.com/interzettel/prehnite/issues/9).
- **Versioned audit:** Git preserves old v1 snapshots; `scripts/roadmap.py --check` rejects archive count drift, missing migrated foundation evidence, unknown dependencies, premature milestone verification and untracked legacy obligations.
- **No artificial resets:** the verified base is recognized; unfinished objectives remain unverified rather than awarded imaginary points.
- **Governance boundary:** Owner approval to merge PR #183 is distinct from authorization to run CUDA, spend money or publish a package.

This document states migration policy; it does not claim that any withheld experiment, unreviewed PR, licensing or product-quality gate is complete.
