# Agent instructions for Prehnite

## Mission
Deliver reliable, quality-gated visual assets at low cost. This repository is an MIT-licensed, local-first integration layer. Model weights and external inference are optional and separately licensed.

## Project governance (read before taking work)
- Read [docs/AGILE.md](docs/AGILE.md), [docs/SPRINT.md](docs/SPRINT.md), [docs/progress/STATUS.md](docs/progress/STATUS.md), [progress/ledger.json](progress/ledger.json), [docs/progress/ATOMIC.md](docs/progress/ATOMIC.md), [progress/atomic.json](progress/atomic.json), [CHANGELOG.md](CHANGELOG.md) and A2A [issue #9](https://github.com/interzettel/prehnite/issues/9).
- Claim one scope on issue #9, and update an existing GitHub issue before opening a duplicate.
- Work through Backlog → Ready → In progress → Review → Done; flag Blocked separately.
- Do not merge another agent's PR, or auto-merge unfinished work. Every merged user-visible change gets an Unreleased changelog entry.
- Version changes require a dedicated PR and follow docs/VERSIONING.md. Never make a Git tag or publish packages without owner approval.
- Keep docs/SPRINT.md as a current snapshot when moving a ticket between states.
- Claim one atomic child task ID (e.g. S05-A04) from progress/atomic.json on A2A issue #9 before implementing it. Deliver one independently testable acceptance criterion per PR; the 61-unit ledger represents coarser release gates.
- Never mark an atomic child done before a merged, verifiable PR. Use in_review for an open PR (zero done credit). Run python scripts/atomic_progress.py --write in the same PR as a register edit.
- Keep progress/ledger.json as the authoritative 61-unit evidence contract. Run python scripts/progress.py --write only after all original parent acceptance and dependency requirements are proven. Do not claim real image quality or paid inference from a synthetic subtask.
- The 73-task October 17 baseline denominator is frozen. New child scope needs an explicit reviewed scope/version migration, not silent deletion of blocked items.
- For future product priorities, also read [docs/PRODUCT_MILESTONES.md](docs/PRODUCT_MILESTONES.md) and its versioned proposed register. **It is not yet adopted**: research, code, experiments and human acceptance have separate evidence gates, and no product completion or old-ledger credit may be inferred from a proposal, draft PR or synthetic evidence.
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
- Post a dated handoff to [A2A issue #9](https://github.com/interzettel/prehnite/issues/9) after meaningful progress.
- Treat a previous paid task lacking a persisted provider ID as ambiguous; never automatically resubmit.
- Do not modify main or auto-merge later PRs without approval. A single batch ID must have only one active worker.

## Development
Run:
    python -m pip install -e ".[dev]"
    python -m compileall -q src
    pytest -q

Use demo mode for CI and integration tests. Never spend API credits in CI.
Any model adapter needs capability metadata, schema validation, licence notes, mocked tests and a documented paid smoke-test procedure.

## Status honesty
If a feature is roadmap-only, document it as such. ComfyUI execution, local CUDA judges and robust mask refinement are planned but not production-certified in v0.1. The demo renderer is not a photorealistic generator.
