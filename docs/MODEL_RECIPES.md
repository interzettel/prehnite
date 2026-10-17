# Model Recipes — micro/macro blueprints and the experimental local bridge

**The versioned JSON manifests are blueprint-only; an opt-in, separately configured micro execution bridge now exists.** Loading or validating either manifest alone never invokes inference, downloads weights, accesses a GPU, uploads images or spends money. The `prehnite-micro` bridge can invoke the existing local ComfyUI adapter **only** with separately supplied workflow graphs, lawful checkpoint files, verified local hashes and an explicit profile. That execution path has not passed a real-GPU, licensed-model or human-cutout-quality acceptance run. `prehnite-macro` has no executable recipe bridge. Passing schema/CI checks is not a license grant or hardware benchmark.

## The abstraction

Prehnite's **Model Recipe** is a versioned description of which adapters
could perform generation, segmentation and technical assessment as a DAG.
The versioned DAG is a **Workflow Blueprint**; its executable mapping and
runtime compatibility must be established separately for each supported recipe.
A recipe ID is the stable alias; the exact semantic version and a canonical
SHA256 form the immutable job intent. A newer recipe may change adapters
but must never silently change an already-running job's meaning.

Current demonstrators:

| Recipe | Suggested shape | Known unsupported work |
| --- | --- | --- |
| [prehnite-micro](../recipes/prehnite-micro/0.1.0-preview.1.json) | Operator-provided local ComfyUI generation and segmentation, plus technical demo judge | Opt-in engine/journal bridge exists; **no bundled/validated weights, tested real graph pair, physical GPU tier or human-accepted output evidence** |
| [prehnite-macro](../recipes/prehnite-macro/0.1.0-preview.1.json) | Hosted fal FLUX.3 Klein generation + hosted SAM 3.1 segmentation, plus local technical judge | **Blueprint only:** no authorized cloud spending, runtime recipe bridge, live tested endpoint, payment or output rights approval |

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

This **planning command** prints a reproducible canonical SHA256, stage IDs,
external pin status and a strict `executable: false` **for the manifest by itself**.
It performs no network request or model inference and writes no files. The
separate opt-in micro-to-ComfyUI engine bridge described below does not
change the truthful output of this contract-only inspection command.

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

## Implemented local micro bridge (still experimental)

The following independently reviewable slices are merged:

1. [#138](https://github.com/interzettel/prehnite/pull/138) — typed versioned schema, stage DAG/capability checks and canonical recipe identity
2. [#139](https://github.com/interzettel/prehnite/pull/139) — read-only hardware doctor, not a VRAM feasibility certificate
3. [#140](https://github.com/interzettel/prehnite/pull/140) — `prehnite recipe-resolve` checks operator-supplied graph/checkpoint file digests, revision labels and terms acknowledgement, returning a **non-executable receipt**
4. [#141](https://github.com/interzettel/prehnite/pull/141) — `prehnite run --recipe --bindings --workflows --checkpoints` maps the **exact three-stage micro recipe only** to compatible configured local ComfyUI endpoints. Recipe/version, resolved file identities and manifest/profile hash are journal-pinned before execution; changed/unbound/legacy resumes fail closed
5. [#142](https://github.com/interzettel/prehnite/pull/142) — issue/board closeout for the completed contract and journal scope

The actual `prehnite run` command can **attempt local inference** when the
operator runs their own ComfyUI process and supplies compatible generation
and segmentation API-format graphs and lawful, local model files. No real
model weights or graph pair are bundled; the CI tests use synthetic fixtures.
The current bridge requires `native_4k`, no upscaler, demo technical judge,
no cross-batch cache, no cloud uploads or spending, and the exact pinned graph
checkpoint names. This does **not** certify 4K output accuracy or GPU memory.
Recipe-aware MCP execution is not yet supported.

See [offline input resolver](LOCAL_MODEL_RESOLVER.md) and
[operator setup / execution and recovery contract](RECIPE_EXECUTION.md).
These checks do not prove ComfyUI loaded the same weights into memory at
runtime, a mask is accurate, a checkpoint is legally cleared, or the workflow
will fit the owner's GPU.

## Next evidence boundary

Perform a real, consented **local generated image -> transparent cutout**
run with appropriate checkpoints, pinned graph/runtime version and physical
GPU measurements, independently assess cutout quality, and record exact
VRAM/RAM/latency/OOM results. The dedicated work remains [#132](https://github.com/interzettel/prehnite/issues/132),
[#134](https://github.com/interzettel/prehnite/issues/134),
[#135](https://github.com/interzettel/prehnite/issues/135),
[#136](https://github.com/interzettel/prehnite/issues/136) and
[#32](https://github.com/interzettel/prehnite/issues/32).
`prehnite-macro` requires its own explicit, separately authorized execution
and benchmark work. Do not infer macro execution or spending authorization
from the micro bridge.

For a concise implementation/acceptance checklist, see the
[Model Recipes workstream in ROADMAP.md](ROADMAP.md#model-recipes-workstream--versioned-micromacro-october-2026).
Keep synthetic fixtures separate from photographed product quality results.
