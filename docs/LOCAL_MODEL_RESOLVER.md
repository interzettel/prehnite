# Micro recipe model bindings — offline setup and read-only resolution

This is the offline operator-input preparation path under [issue #135](https://github.com/interzettel/prehnite/issues/135). Neither `prehnite micro-setup` nor `prehnite recipe-resolve` downloads, loads, executes or judges any model. The **separate** opt-in recipe-bound engine can attempt local ComfyUI inference with these bindings (see [execution](RECIPE_EXECUTION.md)); no weights, rights approvals, benchmarked GPU requirements or compatible third-party graphs are bundled.

## Operator setup

For operator-selected transformer, text encoder, VAE or other graph-loaded model dependencies, use schema v2 and the [multi-file provenance guide](MULTIFILE_PROVENANCE.md). It supports path/loader-name separation and file-level SHA256 but does not claim live ComfyUI residency or undiscoverable custom-node dependencies. Legacy schema v1 remains readable with primary-checkpoint-only coverage.\n\nFor a complete first GPU test on an 8 GB laptop use the separate **true native 1K** micro preview.2 recipe documented in [First Real Asset](FIRST_REAL_ASSET.md). The original preview.1 recipe remains 4K only. For a separate fal.ai test see that same guide. The private binding setup reads only files and never bundles/redistributes their contents.

1. Export your own ComfyUI API-format generation and segmentation graphs to a private directory. Supply your own appropriately licensed local checkpoint files in a separate approved directory.
2. Hash each actual local file with SHA256 (`sha256sum` or PowerShell `Get-FileHash -Algorithm SHA256`). Do not use a model's filename or unverified registry hash as proof of local bytes.
3. Run `python scripts/recipe_plan.py --recipe recipes/prehnite-micro/0.1.0-preview.1.json` to obtain the canonical recipe SHA256.
4. Run **`prehnite micro-setup`** with `--generation-*` and `--cutout-*` file names, publisher model terms/revisions, explicit `--acknowledge-model-terms`, and a private, *nonexistent* `--output` filename to write the digest-bound JSON **exactly once**. Supply an optional `--profile` to verify existing micro bridge constraints. No downloads, network calls or inference. Alternatively, create a local JSON bindings document manually following the structure below. Stage names must correspond exactly to non-demo recipe stages (`generate` and `cutout`). Supply your own **real** digests and terms source.

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

The `recipe-resolve` command reads and hashes only the explicitly referenced files below approved root directories and emits a **non-executable** JSON receipt. It does not reveal private local absolute paths. Nested symlinks, traversal, duplicate keys, oversized graph files, unsupported checkpoint extensions, non-HTTPS terms URLs and SHA mismatches fail closed. The static ComfyUI node-shape check does **not** prove that ComfyUI recognizes the node classes or that a model works with the graph.

## Still missing (must not claim completed)

- Physical-device benchmark and memory-tier certification (#134).
- Official-source checkpoint *downloading* or registry lookup, separate verified license review, offline cache import wizard and resumable installation (#135). Create-only local bindings/receipt now implemented; the user supplies weights.
- Model-specific ComfyUI graph input/output compatibility checks, node mappings and runtime checks (#132).
- Recipe-bound journal pinning and changed-input refusal are **implemented** for opt-in micro runs (#133), but live ComfyUI-loaded model attestations and safe memory residency remain unverified (#136).
- A measured image generation and product cutout with human-reviewed alpha-quality evidence (#32/#132).

No checked-in third-party weights and no paid platforms, model APIs or hosted providers.
