# Agile development workflow

Prehnite follows **issue-driven Kanban with two-week planning reviews**, not a promise of delivery every two weeks. No commercial project-management tool, account or subscription is required. [GitHub Issues](https://github.com/interzettel/prehnite/issues) and PRs record work and decisions; [A2A issue #9](https://github.com/interzettel/prehnite/issues/9) is the cross-agent communication log.

## Agile board

The tracked issue/PR list and its planning metadata live in [project/board.json](../project/board.json), which generates [docs/SPRINT.md](SPRINT.md) via \`python scripts/board.py --write\`. CI runs \`python scripts/board.py --check\`. It is a maintained *snapshot*: inspect GitHub links for live state, and update the board in the same PR as any lane change. The owner has created [organization GitHub Project #1](https://github.com/orgs/interzettel/projects/1). Automatic bidirectional field synchronization is **not** connected; follow [issue #44](https://github.com/interzettel/prehnite/issues/44) and verify the live project rather than treating a generated snapshot as a live update.

Columns: **Backlog → Ready → In progress → In review → Done**, with **Blocked** when a dependency prevents progress. A GitHub issue and the PR implementing part of it may appear separately; don't treat card counts as features or percent complete.

| Lane | Entry / exit rules |
|---|---|
| Backlog | Relevant request, clearly stated outcome, can await refinement |
| Ready | Acceptance criteria, dependency/licensing/billing check, feasible offline test plan |
| In progress | A2A ownership claim, isolated branch, one bounded PR; WIP max **2** cards |
| In review | PR open with test evidence; review WIP max **3** |
| Blocked | Exact blocker and unblocking action recorded, including paid API authorization |
| Done | Merged with green CI, outcome documented and acceptance evidence linked |

**Default work size:** one reviewable change per PR. Split long-running stories into independently testable issues; don't mark an entire epic complete when one tranche is merged.

## Planning cadence and responsibilities

- **Review every ~2 weeks**, beginning 2026-10-16; timebox is a planning checkpoint, not a release deadline.
- Revisit Ready/Blocked first, then capacity. Order work primarily by safety and dependencies.
- Keep at most two concurrent In-progress work cards; the independent PR review lane may contain three.
- Each issue owns acceptance criteria, dependencies, provider/OS limitations and an evidence link. Every PR closes or advances an issue.
- Post a dated A2A handoff on [#9](https://github.com/interzettel/prehnite/issues/9) after meaningful work; include tests, CI status, commit and unverified areas.
- Record meaningful user-visible additions, fixes and breaking changes in the **Unreleased** section of [CHANGELOG.md](../CHANGELOG.md).
- If a blocker needs paid inference, halt that path and work on offline mocked tests instead; never spend without specific approval.

## Definition of ready

A ticket identifies an owner (or claim), a concise problem, user-value/reliability rationale, objective acceptance criteria, external dependencies, any additional model license constraints, and a test plan that does not use paid inference by default.

## Definition of done

A PR is reviewable, linked to its issue, implements its scoped acceptance criteria, includes tests, has passed CI on the PR head, updates docs/changelog/sprint status, and describes remaining gaps. If security-sensitive: threat model and boundary tests. If paid-capable: explicit cost gate and fail-closed recovery. Release readiness is **separate**; see [docs/PROGRESS.md](PROGRESS.md) in [PR #10](https://github.com/interzettel/prehnite/pull/10) until merged.

## Triage taxonomy

Suggested optional GitHub labels, once created by a repository maintainer:
- Status: \`status:ready\`, \`status:in-progress\`, \`status:blocked\` (open PR = review, closed/merged = done).
- Type: \`type:bug\`, \`type:feature\`, \`type:maintenance\`, \`type:security\`, \`type:docs\`.
- Priority: \`priority:p0\` (safety/blocker), \`priority:p1\` (critical path), \`priority:p2\` (planned), \`priority:p3\` (ideas).

GitHub labels aren't provisioned automatically here. **Do not label an issue with an imaginary label or claim a native Projects board exists.** The checked-in board and live issue/PR links work without labels.

## One canonical roadmap (v2)

**The single active source of truth is [progress/roadmap.json](../progress/roadmap.json).**
[Generated current status](progress/STATUS.md) comes from
`python scripts/roadmap.py --write` and CI checks it with `--check`.
Phases contain outcome milestones; milestones contain independently evidenced tasks.
A milestone is verified only when all its tasks and prerequisites are verified.

Work kinds have different evidence gates:

- **Research:** primary-source comparison and independently reviewed conclusion (no code required).
- **Owner decision:** an explicit recorded scope/configuration or quality acceptance decision.
- **Implementation:** independently reviewed merged PR, final-head CI, scoped tests, changelog/docs.
- **Experiment:** separately authorized physical model run, machine/recipe telemetry and independent review. Synthetic CI alone cannot satisfy it.
- **Human acceptance:** owner-reviewed real outputs, preset quality criteria, rights/privacy checks and recorded outcome.

One v2 task ID must be claimed on issue #9 and linked to an existing issue before implementation. No automatic GPU tests, image uploads, paid provider calls, restricted weights or releases from a roadmap approval. The current hardware benchmark target is the actual RTX 4070 Laptop 8 GiB with observed host RAM. There is no 4/6 GiB certification program. ComfyUI is reused rather than replaced.

**Historical v1 ledger:** [61-unit archive](../progress/archive/v1/ledger.json) and [73-task archive](../progress/archive/v1/atomic.json) are read-only snapshots, not active progress statistics. [Migration and all 18 unresolved v1 unit crosswalks](ROADMAP_MIGRATION_V2.md) retain provenance, original gates and deferred paid/90-asset obligations. No other active counter should be advertised.

## Version and releases

Do not conflate the current *working tree version* with a shipped release. See [VERSIONING.md](VERSIONING.md), [RELEASING.md](RELEASING.md), and [CHANGELOG.md](../CHANGELOG.md). Tags, public release pages and PyPI uploads require a separate owner-approved release PR.
