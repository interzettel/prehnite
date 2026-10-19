# Agent instructions for Prehnite

## Mission
Deliver a reliable local-first image workbench on the owner's RTX 4070 Laptop 8 GiB GPU, with measured system-RAM limits, useful batches and later LoRA/appearance experiments. The project reuses existing inference runtimes; separately licensed model weights and hosted inference remain optional.

## Project governance (read before taking work)
- Read [docs/AGILE.md](docs/AGILE.md), [docs/SPRINT.md](docs/SPRINT.md), [the one canonical product status](docs/progress/STATUS.md), [progress/roadmap.json](progress/roadmap.json), [docs/ROADMAP_MIGRATION_V2.md](docs/ROADMAP_MIGRATION_V2.md), [CHANGELOG.md](CHANGELOG.md) and A2A [issue #9](https://github.com/interzettel/prehnite/issues/9).
- Claim one scope on issue #9, and update an existing GitHub issue before opening a duplicate.
- Work through Backlog → Ready → In progress → Review → Done; flag Blocked separately.
- Do not merge another agent's PR, or auto-merge unfinished work. Every merged user-visible change gets an Unreleased changelog entry.
- Version changes require a dedicated PR and follow docs/VERSIONING.md. Never make a Git tag or publish packages without owner approval.
- Keep docs/SPRINT.md as a current snapshot when moving a ticket between states.
- Claim one current v2 task ID from progress/roadmap.json on A2A issue #9 before work. State whether the deliverable is research, owner decision, implementation, real experiment or human acceptance. Do not claim original v1 task IDs as current credit.
- Verify implementation only after a merged, independently reviewed PR and final-head CI; research needs a reviewed primary-source decision, experiments require separately approved measured real runs, and owner/human gates need explicit approval. In-review is never verified.
- progress/roadmap.json is the **only active canonical milestone/task ledger**. Run python scripts/roadmap.py --write after a reviewed registry change. Every verified task must have the required evidence type and every verified milestone must have all named gates verified. Synthetic tests never certify real image quality or GPU capability.
- Previous 61-unit and 73-task trackers are **read-only archives** at progress/archive/v1/. Their original 43/61 and 21/73 snapshots remain available but never enter the current progress percentage. The v2 crosswalk preserves every open legacy obligation without silently equating it to a new milestone. Review [docs/PRODUCT_MILESTONES.md](docs/PRODUCT_MILESTONES.md).
- The native organization Project #1 exists, but automatic field synchronization is not implemented: compare live cards before claiming agreement.

## Visual identity rules
- Use the user-selected forest-green / coral / warm-paper Riso artwork in the README and the canonical light/dark palette from `src/prehnite/brand.py` and `docs/BRAND_PALETTE.md` for all new branded interfaces and editorial illustrations.
- Keep diagnostic/semantic image-data colors meaningful: never recolor heatmaps or quality/error measurements solely for brand consistency. Bright coral on paper is decorative, not small body text; use the accessible text token instead.

## Engineering invariants
- Never introduce mandatory paid SaaS, platform, database, analytics or hosting dependencies.
- Do not submit a billable request without explicit profile authorization, an operation estimate and a remaining batch budget.
- Never log keys, base64 image inputs, private prompts in public CI, or provider authentication headers.
- Treat paths and remote payloads as untrusted. No archive traversal or arbitrary client-chosen server paths.
- Do not claim an estimated spend is actual billed usage. Distinguish visual judgments from deterministic pixel checks.
- Preserve source artifacts, prompts, seeds, request IDs, intermediate steps and quality decisions.
- Retry a failed stage without invalidating unrelated accepted artifacts. Respect hard maximum attempts.
- Uncertain paid submissions must not be blindly retried. Keep provider request IDs for recovery.
- Client MCP disconnect must not cancel batch execution; jobs use a persistent worker.
- No proprietary or separately licensed model weights are committed to this repository.

## Persistent state and coordination
- Read [docs/PROGRESS.md](docs/PROGRESS.md) for evidence-based release gates and hard work limits.
- Post a dated handoff with v2 task ID, evidence type, exact PR commit, CI and unresolved gates to [A2A issue #9](https://github.com/interzettel/prehnite/issues/9) after meaningful progress.
- Treat a previous paid task lacking a persisted provider ID as ambiguous; never automatically resubmit.
- Do not modify main or auto-merge later PRs without approval. A single batch ID must have only one active worker.

## Development
Run:
    python -m pip install -e ".[dev]"
    python -m compileall -q src
    python scripts/roadmap.py --check
    pytest -q

Use demo mode for CI and integration tests. Never spend API credits in CI.
Any model adapter needs capability metadata, schema validation, licence notes, mocked tests and a documented paid smoke-test procedure.

## Status honesty
If a feature is roadmap-only, document it as such. Some experimental local ComfyUI inference has been observed, but it is not a broadly verified, portable, rights-cleared or production-certified local workflow. The demo renderer is not a photorealistic generator.
