# Multi-file ComfyUI model provenance (schema v2, offline)

**Development feature, not included in public PyPI 0.1.0a1.** A model is not necessarily one `.safetensors` file. The local-lab inspection found a FLUX 3-family graph may require a transformer, text encoder, VAE and other files, while the original `micro-setup` hashes only one checkpoint per stage. This is a **byte-level provenance** extension, not a GPU/runtime or legal license certificate.

## What the new receipt does

- Existing single-checkpoint bindings are **schema v1**, still accepted with the same `resolved_inputs_sha256` algorithm and journal semantics. Their coverage is explicitly reported as `legacy_primary_checkpoint_only`. Do not claim completeness for v1.
- The operator may add `--additional-models /private/selection.json`, a create-only, separately stored manifest listing each extra file in `generate` and `cutout` stages. This makes **schema v2** bindings.
- The tool validates paths inside your exact `--checkpoints` root, rejects directory traversal/symlinked files, and computes SHA256 for each file, including transformer, text encoder, VAE and supplemental segmentation weights. It requires a named role, publisher revision and public HTTPS terms URL for each extra file. Checkpoint bytes stay on your PC.
- A **graph reference** may differ from the local path. Example: file `diffusion_models/flux3.safetensors` under models root, but ComfyUI `UNETLoader.unet_name` is `flux3.safetensors`. Use `--generation-checkpoint-graph-ref flux3.safetensors`. The original single-checkpoint path is still required for the hash.
- Every ComfyUI API graph input containing a recognized model-file extension (`.safetensors`, `.ckpt`, `.pt`, `.pth`, `.onnx`, `.gguf`, `.bin`) must correspond **exactly** to one pinned loader reference in that stage, or setup/resolution fails. Every declared file must also be referenced.
- The engine rehashes primary and extra model files, graph and profile **before** journal-bound execution/resume and refuses changed bytes with a clear error. It stores hashes/revisions, not private model file paths.
- Schema v2 remains **static coverage** only: custom nodes may load models from defaults, aliases, nested structures, Python code or values without file extensions. Prehnite cannot independently confirm ComfyUI loaded the pinned bytes, installed node versions or live model license eligibility. The receipt says `checked_for_known_weight_extensions`, not "all possible runtime dependencies certified".

## Example: update your private local lab

Copy [supplemental-models.example.json](../examples/supplemental-models.example.json) into the lab's **ignored private folder** and replace all placeholder paths, source revisions, terms URLs and ComfyUI loader filenames. Never commit the private result, model weights or generated images.

```powershell
$prehnite = "C:\Users\yigit\Documents\repos\prehnite"
$lab = "C:\Users\yigit\Documents\repos\prehnite-local-lab"
# Illustrative only; paths, terms and installed model files must be real.
& "$prehnite\.venv\Scripts\prehnite.exe" micro-setup `
  --recipe "$prehnite\recipes\prehnite-micro\0.1.0-preview.2.json" `
  --workflows "$lab\_private\workflows" `
  --checkpoints "$lab\_private\models" `
  --generation-graph generation_api.json `
  --generation-checkpoint diffusion_models/REAL.safetensors `
  --generation-checkpoint-graph-ref REAL.safetensors `
  --generation-revision REAL_PUBLISHER_REVISION `
  --generation-terms-url https://publisher.example/license `
  --cutout-graph cutout_api.json `
  --cutout-checkpoint segmentation/REAL.safetensors `
  --cutout-checkpoint-graph-ref REAL.safetensors `
  --cutout-revision REAL_SEGMENTATION_REVISION `
  --cutout-terms-url https://publisher.example/license `
  --additional-models "$lab\_private\supplemental-models.json" `
  --acknowledge-model-terms `
  --profile "$prehnite\examples\profile-first-local-1k.yaml" `
  --output "$lab\_private\micro-bindings-v2.json"
```

**Important:** The literal values above are placeholders and are intended to fail until you install compatible graph/model files and replace them. `micro-setup` is offline. `prehnite run` is a **separate local GPU execution**, subject to user approval and operator rights review; no remote calls, model downloads or automatic vendor billing are enabled in this path. The 8 GB GPU must be tested, not assumed suitable.

## First test acceptance

1. New `0.1.0-preview.2` native-1K manifest/profile passes a zero-call trial plan, but no GPU readiness claim.
2. Private generation graph may reference transformer, text encoder and VAE; the schema-v2 binding must include all recognized model-file inputs, checked against the actual bytes under one operator-controlled model root.
3. Changing any supplemental model byte refuses `recipe-resolve` or `prehnite run` resume **before** queue submission.
4. An undeclared graph model reference, unsafe path, missing file, duplicate pinned reference, or bad HTTPS source terms fails closed without writing bindings.
5. On actual ComfyUI, collect evidence of **runtime-loaded** checkpoints and node versions separately; byte hashes alone do not prove residency or full dependency coverage.

Related: [First Real Asset](FIRST_REAL_ASSET.md), [Local Model Resolver](LOCAL_MODEL_RESOLVER.md), [Recipe Execution](RECIPE_EXECUTION.md), issues [#135](https://github.com/interzettel/prehnite/issues/135), [#134](https://github.com/interzettel/prehnite/issues/134).
