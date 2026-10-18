# Local cutout pipeline

This is the reusable post-segmentation contract for a reviewed source image.
The existing `prehnite run` Engine still owns the job: reviewed-source handoff,
ComfyUI segmentation, journaling, recovery and `review_pending`. The
`cutout-qa` step adds configurable CPU alpha candidates and separate technical
evidence. It never accepts an image on its own.

## Lifecycle

```text
reviewed source
  -> provenance validation (Engine handoff)
  -> resource preflight (observation only)
  -> local segmentation (Engine + ComfyUI)
  -> raw mask
  -> cutout-qa: alpha candidates + seven-stage technical evidence
  -> independent visual review
  -> explicit cutout-accept record
  -> final approved RGBA PNG
```

## 1. Produce the mask with the Engine

Use the existing command and a new batch ID. The source and target are in the
manifest; the workflow and model dependencies are bound in the profile/handoff:

```bash
prehnite run \
  --manifest private/manifest-reviewed-cutout.yaml \
  --profile private/profile-segmentation-installed.yaml \
  --workspace workspace \
  --inputs private/inputs \
  --workflows private/workflows \
  --dependencies-root private/models
```

Set `PREHNITE_WORKFLOWS` only if the existing adapter requires it. The Engine
stages the raw mask under:

```text
workspace/batches/<new-batch>/intermediates/<asset>/cutouts/<target-hash>/mask.png
```

No generation, judge, retry or automatic acceptance is involved.

## 2. Create a cutout recipe

A recipe is explicit plain-UTF-8 JSON (no BOM); it contains source/target
definitions, the exact workflow SHA256 and node bindings, model file hashes, and
one or more alpha candidate specifications. Paths are canonical relative POSIX
paths (use `/`, not Windows `\\`). Candidate sigmas are **never defaulted**.

```json
{
  "schema_version": 1,
  "source": {
    "name": "reviewed-source.png",
    "sha256": "<source-sha256>"
  },
  "target": {
    "id": "product",
    "phrase": "the named product",
    "include": ["product body"],
    "exclude": ["background", "shadow", "cord"]
  },
  "workflow": {
    "path": "cutout_api.json",
    "sha256": "<workflow-sha256>",
    "input_node": "1",
    "target_node": "4",
    "target_input": "prompt",
    "output_node": "6"
  },
  "models": [
    {"role": "detector", "path": "detector/weights.pth", "sha256": "<model-sha256>"}
  ],
  "alpha_candidates": [
    {"id": "soft-a", "sigma_px": 0.65, "preserve_core_px": 1},
    {"id": "soft-b", "sigma_px": 1.0, "preserve_core_px": 1}
  ],
  "qa": {
    "min_hard_iou": 0.995,
    "max_removed_fraction": 0.01,
    "max_added_fraction": 0.02,
    "max_coverage_delta": 0.002,
    "max_partial_alpha_fraction": 0.02,
    "max_narrow_width_delta_px": 1
  }
}
```

## 3. Run CPU alpha QA

```bash
prehnite cutout-qa \
  --recipe private/cutout-recipe.json \
  --source private/inputs/reviewed-source.png \
  --mask workspace/batches/<new-batch>/intermediates/<asset>/cutouts/<target-hash>/mask.png \
  --workflow-root private/workflows \
  --models-root private/models \
  --output private/review/<batch>/alpha
```

The command is CPU-only. It verifies every declared hash and node binding,
expands nearest foreground RGB into transparent/fringe pixels so feathering
cannot reveal background colors, generates the declared candidates, and writes
`cutout-quality.json` plus candidate RGBA files.

The report has seven independent stages:

```text
resource_readiness
dependency_compatibility
technical_execution
segmentation_validity
alpha_quality
visual_acceptance
owner_final_acceptance
```

There is intentionally no generic `success` field. `visual_acceptance` and
`owner_final_acceptance` remain `not_recorded` after QA. A failed report may
still be written when segmentation or alpha QA fails; the CLI exits non-zero
for `failed`/`blocked` stages.

A candidate is rejected by technical QA if it loses hard silhouette, changes
components/holes, exceeds the configured coverage/feathering limits, changes a
narrow row width, or fails the hard-IoU threshold. Candidate status is
`passed` or `rejected`; every candidate remains `review_pending`.

## 4. Inspect and decide

Review the candidate and comparison composites in private space. Do not commit
private source/model images to the public repository. A useful comparison set
uses checkerboard, white, dark and high-contrast backgrounds plus enlarged
shade/stem/base or equivalent edge crops.

## 5. Record explicit review

Only after visual inspection:

```bash
prehnite cutout-accept \
  --quality-report private/review/<batch>/alpha/cutout-quality.json \
  --candidate-id soft-a \
  --reviewer "independent reviewer" \
  --decision accepted \
  --scope "This artifact at the reviewed comparison scale; not blanket pipeline certification." \
  --evidence private/review/<batch>/alpha/comparison-checkerboard.png \
  --output private/review/<batch>/acceptance.json
```

The acceptance record is create-only. It verifies that the candidate hash still
matches the QA report, records the visual decision and evidence hashes, keeps
`owner_final_acceptance` separate, and refuses a rejected technical candidate.
Acceptance is a review record, not an automatic quality gate or owner-signed
journal acceptance.

## Runtime entry point

The private lab has a single process-lifecycle entry point:

```bash
python scripts/prehnite_local_runtime.py --config private/local-runtime.json preflight
python scripts/prehnite_local_runtime.py --config private/local-runtime.json check
python scripts/prehnite_local_runtime.py --config private/local-runtime.json start
python scripts/prehnite_local_runtime.py --config private/local-runtime.json status
python scripts/prehnite_local_runtime.py --config private/local-runtime.json stop
```

`preflight` is observation-only and refuses below configured RAM/commit/VRAM
thresholds. `check` imports the overlay and node in a separate process.
`start` starts the supervised ComfyUI server and does not submit a job. The
Engine remains responsible for `prehnite run`; this script never implements a
second job engine or automatic retry.

The runtime configuration contains operator-private paths and model hashes and
must not be committed to the public repository.
