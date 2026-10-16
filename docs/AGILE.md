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

## Evidence-ledger milestones

[progress/ledger.json](../progress/ledger.json) defines stable, independently completable units with dependencies, execution lanes and evidence. [scripts/progress.py](../scripts/progress.py) generates [the SVG dashboard and work report](progress/STATUS.md). **Only done with evidence counts; issue cards, active work and PRs under review do not.** A milestone is reached only when named gate units are done. CI rejects unknown/duplicate dependencies, cycles, false completion and generated-file drift. The separate [production-readiness gate matrix](PROGRESS.md) is not a release claim.

One human maintainer owns priorities, provider spend and final acceptance; agents own isolated implementation changes and write #9 handoffs. Hardware-heavy work stays in a local lane so a cloud agent cannot fabricate GPU measurements.

## Version and releases

Do not conflate the current *working tree version* with a shipped release. See [VERSIONING.md](VERSIONING.md), [RELEASING.md](RELEASING.md), and [CHANGELOG.md](../CHANGELOG.md). Tags, public release pages and PyPI uploads require a separate owner-approved release PR.
