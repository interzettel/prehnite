# Prehnite — cutout capability progress

> Fixed 2026-10-18 scope: local proof to reusable public source to real-world validation. This is NOT the release-roadmap percentage or a product-quality score.

**Focused cutout capability: 8/13 (61.5%)** · 2 blocked · 3 planned.

**Separate release criteria:** [42/61 original delivery units](STATUS.md) and [14/73 atomic unfinished-scope tasks](ATOMIC.md) remain independently governed. No credits are transferred between trackers.

**Evidence standard:** a done outcome links to a merged PR, merged test, or a dated index of explicitly labeled private operator/independent visual evidence. Source implementation does not imply a second real-object acceptance.

**Counting policy:** Count each named outcome once only when its acceptance is met and linked evidence exists. Local operator-reported execution is labeled separately from public merged code and independent artifact review. Planned and blocked are zero credit. Scope and denominator cannot be silently reset.

## Local proof — 4/4

| ID | Outcome | State | Required acceptance | Evidence or blocker |
| --- | --- | --- | --- | --- |
| LP01 | Native-1K source created and reviewed | done | One identified local source, its byte hash and authorization evidence are retained | [Private operator report](https://github.com/interzettel/prehnite/blob/main/docs/LOCAL_LAB_MILESTONE_2026-10-18.md) |
| LP02 | Compatible private GPU cutout runtime demonstrated | done | Pinned GroundingDINO/SAM2 nodes execute with a process-isolated compatibility overlay | [Private operator report](https://github.com/interzettel/prehnite/blob/main/docs/LOCAL_LAB_MILESTONE_2026-10-18.md) |
| LP03 | Real local segmentation mask produced | done | One actual non-synthetic mask with exact prompt, source and mask identity is documented | [Private operator report](https://github.com/interzettel/prehnite/blob/main/docs/LOCAL_LAB_MILESTONE_2026-10-18.md) |
| LP04 | One refined RGBA candidate independently visually accepted | done | Visual decision specifies a particular candidate hash, viewing scale and limited scope | [Independent artifact review](https://github.com/interzettel/prehnite/blob/main/docs/LOCAL_LAB_MILESTONE_2026-10-18.md) |

## Merged software — 4/4

| ID | Outcome | State | Required acceptance | Evidence or blocker |
| --- | --- | --- | --- | --- |
| SW01 | Read-only fail-closed resource preflight merged | done | An explicit policy assesses RAM, commit and VRAM without authorizing inference | [Merged public PR](https://github.com/interzettel/prehnite/pull/159) |
| SW02 | Configurable CPU cutout refinement and technical QA merged | done | Reusable candidate generation, mask topology and alpha checks have public source tests | [Merged public PR](https://github.com/interzettel/prehnite/pull/161) |
| SW03 | Create-only evidence-bound independent acceptance CLI merged | done | Cutout review record verifies candidate/evidence bytes without owner journal promotion | [Merged public PR](https://github.com/interzettel/prehnite/pull/161) |
| SW04 | Resource readiness to QA interface regression on main | done | Public tests cover pass, blocked and unknown observations without implicit startup | [Merged regression test](https://github.com/interzettel/prehnite/blob/main/tests/test_resource_cutout_integration.py) |

## Real-world validation — 0/5

| ID | Outcome | State | Required acceptance | Evidence or blocker |
| --- | --- | --- | --- | --- |
| VL01 | Rights-cleared non-lamp local source recorded | blocked | Original file on local disk with verified licence, exact path, SHA256 and dimensions | Awaiting original JPEG download and local rights/hash verification |
| VL02 | Second real-object Engine to QA trial independently reviewed | blocked | One bounded non-lamp segmentation feeds merged CPU QA and receives explicit human review | Requires VL01, a passing resource preflight and one authorized inference |
| VL03 | Bound real-model execution and compatibility receipt | planned | Execution receipt binds actual run/source/mask/workflow/model identity, not just file presence | Not yet demonstrated |
| VL04 | Optional journal-safe Engine to QA orchestration | planned | Engine may opt into CPU QA with preserved journal/recovery and no implicit inference | Not yet demonstrated |
| VL05 | Diverse material cutout quality benchmark | planned | Independent real gold-reference masks and reviews cover multiple object/material categories | Not yet demonstrated |

## Interpretation

This percentage measures a fixed cutout workstream, not how much of Prehnite is finished. The public CLI and QA contracts are merged; the next rights-cleared non-lamp image, resource-safe execution, bound execution receipt, Engine integration and diverse quality benchmark remain incomplete. Never promote them based on a synthetic test or one lamp.

Source: [progress/cutout_capability.json](../../progress/cutout_capability.json). Regenerate with python scripts/cutout_capability_progress.py --write and verify with --check.
