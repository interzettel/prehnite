# Model Recipes — micro and macro (contract preview)

**This is a schema preview, not an image-generation capability or installer.**
The two manifests are read-only blueprints. They deliberately do **not**
execute inference, download models, access a GPU, upload private images, or
spend money. A successful validation is **not** a hardware benchmark or
permission to use or redistribute third-party model weights.

## The abstraction

Prehnite's **Model Recipe** is a versioned description of which adapters
could perform generation, segmentation and technical assessment as a DAG.
The future executable composition is called a **Workflow Blueprint**.
A recipe ID is the stable alias; the exact semantic version and a canonical
SHA256 form the immutable job intent. A newer recipe may change adapters
but must never silently change an already-running job's meaning.

Current demonstrators:

| Recipe | Suggested shape | Known unsupported work |
| --- | --- | --- |
| [prehnite-micro](../recipes/prehnite-micro/0.1.0-preview.1.json) | Unresolved user-provided local ComfyUI generation and segmentation workflows, plus technical demo judge | No local checkpoint/revision, measurements, weights, runnable ComfyUI graph, or verified VRAM budget |
| [prehnite-macro](../recipes/prehnite-macro/0.1.0-preview.1.json) | Hosted fal FLUX.3 Klein generation + hosted SAM 3.1 segmentation, plus local technical judge | Zero cloud permission/budget, no live tested endpoint, no payment or output rights approval, no production execution |

The macro recipe is **not automatically higher quality**. It is a candidate
combination to benchmark later. FLUX.3 Klein's hosted endpoint must NOT
be confused with permission to install or run a local weight file.
Likewise a ComfyUI stage needs the user's separately licensed checkpoint
and API graph. No checkpoint, model source or license is inherited from
Prehnite's MIT code.

## Offline inspection

After installing Prehnite locally:

    python scripts/recipe_plan.py --recipe recipes/prehnite-micro/0.1.0-preview.1.json
    python scripts/recipe_plan.py --recipe recipes/prehnite-macro/0.1.0-preview.1.json

The command prints a reproducible canonical SHA256, stage IDs, external
pin status and explicit booleans saying the recipe is **not executable**
and has no hardware/licensing/paid authorization. It performs no network
request or model inference and writes no files.

The schema rejects:
- Unknown or nonimplemented model capabilities in the existing registry
- Accidental hosted-model execution within micro, or local aliases for fal
- Missing generation/cutout stages, unknown edges, duplicate nodes and cycles
- Root/parent input incompatibilities, unsupported operation combinations
- Unresolved model revision with a fabricated SHA, and external models
  claiming bundled demo-code rights
- Auto-downloading, bundled checkpoints, billable calls, cloud uploads and
  nonzero budgets in these contract-preview files
- Noncanonical versions, duplicate JSON keys, symlinked files and oversized
  or malformed local JSON

The preview deliberately does not claim a benchmarked 4GB, 6GB, 8GB or
12GB configuration. That requires issue [#134](https://github.com/interzettel/prehnite/issues/134).
Rights-aware optional downloads and first-run install UX are [#135](https://github.com/interzettel/prehnite/issues/135).
Memory-aware batching, model residency, tiling, OOM recovery, cost-per-accepted
output and real-performance comparisons are [#136](https://github.com/interzettel/prehnite/issues/136).
The overall architecture and acceptance program is [#132](https://github.com/interzettel/prehnite/issues/132).

## Next execution boundary

A separate future PR must implement a verified **resolver** connecting
a pinned recipe DAG to the engine and journal. It must bind exact adapter,
checkpoint, graph and manifest versions to every immutable batch attempt.
The resolver must refuse unresolved model identifiers, missing downloadable
rights, missing hardware evidence, or paid/API stages lacking explicit owner
consent and cost estimates. Cached or interrupted batches must not silently
upgrade their recipes when new versions are published.

Until this happens, **neither micro nor macro can be used to generate images**.
Keep demo fixtures separate from photographed product quality results.
