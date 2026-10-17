# Prehnite

**Local-first, quality-gated visual asset production. No mandatory SaaS or platform fees.**

[Source and project README](https://github.com/interzettel/prehnite#readme) · [Roadmap](https://github.com/interzettel/prehnite/blob/main/docs/ROADMAP.md) · [Changelog](https://github.com/interzettel/prehnite/blob/main/CHANGELOG.md) · [Issues](https://github.com/interzettel/prehnite/issues)

Prehnite is an MIT-licensed Python CLI and optional MCP integration for batch image generation, masks/cutouts, technical validation, targeted repair, stateful replay, quality evidence, and reproducible export. It **orchestrates image models**; it does not include model weights, a photorealistic image generator, or a subscription service.

## Quick start: no-cost local test

Requires Python 3.11 or later.

```bash
python -m pip install prehnite
prehnite init --destination my-first-batch
prehnite doctor
prehnite --help
```

The `init` command creates local starter configuration, but does not run model inference or incur fees. For a sample batch, follow the source repository's [two-minute demo](https://github.com/interzettel/prehnite#try-it-in-two-minutes).

For a sample zero-cost batch, follow the [up-to-date project README](https://github.com/interzettel/prehnite#try-it-in-two-minutes) and [onboarding guide](https://github.com/interzettel/prehnite/blob/main/docs/ONBOARDING.md).

## What is actually implemented

- CLI, strict manifest/profile validation, stage journal, bounded attempts and safe archive/export paths.
- Offline synthetic demo flow, reports and reproducible zero-cost validation.
- Experimental local ComfyUI adapter and **opt-in** `prehnite-micro` recipe binding with immutable batch identity. You must separately install ComfyUI and supply licensed checkpoints and compatible graphs. No real GPU model/cutout quality or 4K VRAM tier is certified.
- Optional paid inference connectors require explicit operator-selected profiles, permissions and budgets. **Installing Prehnite does not authorize any cloud uploads or paid API calls.**
- `prehnite-macro` is currently a read-only workflow blueprint, not an installed or benchmarked high-quality image pipeline.

See the [implementation/evidence roadmap](https://github.com/interzettel/prehnite/blob/main/docs/ROADMAP.md), [recipe contract](https://github.com/interzettel/prehnite/blob/main/docs/MODEL_RECIPES.md) and [public release history](https://github.com/interzettel/prehnite/blob/main/CHANGELOG.md).

## Release quality and licensing

The initial **0.1.0 alpha** is an early developer preview, **not production certified**. Passing synthetic CI does not prove realistic image quality, legal rights to separate checkpoints, accepted cutout accuracy, stable public APIs or physical GPU suitability.

Prehnite code: MIT. Checkpoint weights, providers and third-party assets are governed by their own licenses and usage terms. The package contains **no bundled checkpoint/model weights**.
