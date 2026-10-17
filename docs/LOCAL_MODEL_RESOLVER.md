# Micro recipe local-input resolver (offline preview)

This is the first, **read-only** part of [issue #135](https://github.com/interzettel/prehnite/issues/135). It does not install, download, load or execute any model. It does not certify checkpoint usage rights or ComfyUI compatibility. Existing `prehnite-micro` remains a **blueprint only**, not a runnable package.

## Operator setup

1. Export your own ComfyUI API-format generation and segmentation graphs to a private directory. Supply your own appropriately licensed local checkpoint files in a separate approved directory.
2. Hash each actual local file with SHA256 (`sha256sum` or PowerShell `Get-FileHash -Algorithm SHA256`). Do not use a model's filename or unverified registry hash as proof of local bytes.
3. Run `python scripts/recipe_plan.py --recipe recipes/prehnite-micro/0.1.0-preview.1.json` to obtain the canonical recipe SHA256.
4. Create a local JSON bindings document following the structure below. Stage names must correspond exactly to non-demo recipe stages (`generate` and `cutout`). Supply your own **real** digests and terms source.

```json
{
  "schema_version": 1,
  "recipe_sha256": "REPLACE_WITH_ACTUAL_RECIPE_SHA256",
  "stages": {
    "generate": {
      "workflow": "generation_api.json",
      "workflow_sha256": "REPLACE_WITH_ACTUAL_GRAPH_SHA256",
      "checkpoint": "my-generation.safetensors",
      "checkpoint_sha256": "REPLACE_WITH_ACTUAL_CHECKPOINT_SHA256",
      "model_revision": "operator-pinned-revision",
      "model_terms_url": "https://example.org/replace-with-real-model-terms",
      "acknowledged_terms_for_local_use": true
    },
    "cutout": {
      "workflow": "segmentation_api.json",
      "workflow_sha256": "REPLACE_WITH_ACTUAL_GRAPH_SHA256",
      "checkpoint": "my-segmentation.safetensors",
      "checkpoint_sha256": "REPLACE_WITH_ACTUAL_CHECKPOINT_SHA256",
      "model_revision": "operator-pinned-revision",
      "model_terms_url": "https://example.org/replace-with-real-model-terms",
      "acknowledged_terms_for_local_use": true
    }
  }
}
```

This is a **template only**, and deliberately will not validate until replaced with real local data. An operator acknowledgement means only that an operator states they reviewed the model's local-use terms; Prehnite cannot confer or verify those rights.

Run:

```bash
prehnite recipe-resolve --recipe recipes/prehnite-micro/0.1.0-preview.1.json --bindings /private/my-binding.json --workflows /private/comfy-graphs --checkpoints /private/model-weights
```

The command reads and hashes only the explicitly referenced files below approved root directories and emits a **non-executable** JSON receipt. It does not reveal private local absolute paths. Nested symlinks, traversal, duplicate keys, oversized graph files, unsupported checkpoint extensions, non-HTTPS terms URLs and SHA mismatches fail closed. The static ComfyUI node-shape check does **not** prove that ComfyUI recognizes the node classes or that a model works with the graph.

## Still missing (must not claim completed)

- Physical-device benchmark and memory-tier certification (#134).
- Legitimate sourced/checksum-pinned checkpoint installation, offline cache import and terms handling (#135).
- Model-specific ComfyUI graph input/output compatibility checks, node mappings and runtime checks (#132).
- Immutable **per-batch journal pinning** and resume mismatch refusal (#133/#136).
- A measured image generation and product cutout with human-reviewed alpha-quality evidence (#32/#132).

No checked-in third-party weights and no paid platforms, model APIs or hosted providers.
