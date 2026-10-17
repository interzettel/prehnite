# First real asset: local ComfyUI or opt-in fal.ai

**Development workflow, not part of the already published `prehnite==0.1.0a1` wheel.** Use a checkout of the latest `main` after this feature PR merges. No model weights, subscriptions, private photographs, GPUs or API credits are included. One good accepted transparent cutout is the next *unverified* milestone, not a claim already achieved.

## Choose a lane

| Step | Local-first `prehnite-micro` | Explicit paid fal.ai first smoke |
| --- | --- | --- |
| No-cost static plan | `prehnite micro-setup` then `prehnite trial-plan --mode local` | `prehnite trial-plan --mode fal` |
| Inference process | Your own local ComfyUI on loopback | Your fal.ai account, via `prehnite run` |
| Default cost | USD 0 to providers; electricity/compute not included | No call unless separately running with `allow_paid`, `FAL_KEY`, budget |
| Included model weights | None | None; remote service endpoint opt-in |
| Initial result | 1 generated image + 1 transparent cutout candidate | 1 generated image; segmentation intentionally **off** |
| Ready-for-quality claims | No; physical GPU and human alpha review required | No; human quality review and real invoices required |

### Checkout preparation

```bash
git clone https://github.com/interzettel/prehnite.git
cd prehnite
python -m pip install -e ".[dev]"
prehnite hardware
prehnite doctor
```

On Windows PowerShell use `$env:PREHNITE_WORKFLOWS = "C:\\...\\my-graphs"`; on bash use `export PREHNITE_WORKFLOWS=/path/my-graphs`. Neither command installs or contacts ComfyUI.

## A. Local generation + cutout

1. Install [ComfyUI](https://github.com/Comfy-Org/ComfyUI) yourself. Choose a generation model **and** a segmentation/matting model under individually acceptable terms from their original publishers; keep weights in your own ComfyUI-accessible model directories. Do **not** redistribute gated weights or put them in the Prehnite repository. The `--checkpoints` directory must contain the **same actual bytes** that ComfyUI will load (this is not independently verified at runtime).
2. Export each real workflow as **ComfyUI API JSON**. Use one exact image output per stage. The generation graph must have `text` for the prompt node, seed input, `width` and `height` for size node, and one saved image node; segmentation must have an image-loading node with `image`, a text-target node with `text`, and a saved *mask* image output. Every graph must reference its selected checkpoint by its exact ComfyUI loader value.
3. Place `generation_api.json` and `cutout_api.json` under your private workflow root. Review the node IDs and edit [profile-first-local.yaml](../examples/profile-first-local.yaml)—the provided numbers are placeholders. Start with the [one-asset manifest](../examples/manifest-first-local.yaml); `native_4k` means an actual **3072×4096** ComfyUI request at 3:4 (not a promise that your GPU can handle it). If your GPU cannot run that, **do not fake the result**; a separate smaller-capacity recipe will require engineering/benchmarking.
4. Manually review **both models' exact local-use terms**. Run the create-only setup below with real names, revisions and **publisher-hosted HTTPS terms URLs**; no dummy URLs. Point to the private file's parent directory as `--output`—the command will **refuse to overwrite** an existing file.

```bash
prehnite micro-setup \
  --recipe recipes/prehnite-micro/0.1.0-preview.1.json \
  --workflows /path/my-graphs --checkpoints /path/my-checkpoints \
  --generation-graph generation_api.json --generation-checkpoint YOUR_GENERATION.safetensors \
  --generation-revision YOUR_EXACT_GENERATION_REVISION \
  --generation-terms-url https://MODEL_PUBLISHER/TERMS \
  --cutout-graph cutout_api.json --cutout-checkpoint YOUR_CUTOUT.safetensors \
  --cutout-revision YOUR_EXACT_CUTOUT_REVISION \
  --cutout-terms-url https://MODEL_PUBLISHER/TERMS \
  --acknowledge-model-terms \
  --profile examples/profile-first-local.yaml \
  --output /path/private/prehnite-bindings.json
```

The command creates JSON containing SHA256 for the exact workflow and checkpoint files and recipe identity, then checks strict `prehnite-micro` profile policy. It does not contact ComfyUI, download models, judge the license or claim your GPU is suitable. If graph/profile compatibility fails, it makes **no output file**. Do not use these example placeholders unchanged.

5. Start ComfyUI locally. Check that the expected graph nodes are installed and the graph can run directly in ComfyUI first. Prehnite may query only `http://127.0.0.1:8188` / `localhost`. Check with `prehnite doctor --check-comfyui` (loopback health only; not a GPU run).
6. Do a zero-cost Prehnite preflight before **separately choosing** to execute:

```bash
prehnite recipe-resolve --recipe recipes/prehnite-micro/0.1.0-preview.1.json \
  --bindings /path/private/prehnite-bindings.json \
  --workflows /path/my-graphs --checkpoints /path/my-checkpoints

prehnite trial-plan examples/manifest-first-local.yaml \
  --profile examples/profile-first-local.yaml --mode local --max-test-usd 0
```

7. When ready to run **real** ComfyUI inference:

```bash
prehnite run examples/manifest-first-local.yaml \
  --profile examples/profile-first-local.yaml \
  --workspace /path/private/workspace --inputs /path/private/inputs \
  --recipe recipes/prehnite-micro/0.1.0-preview.1.json \
  --bindings /path/private/prehnite-bindings.json \
  --workflows /path/my-graphs --checkpoints /path/my-checkpoints
```

The engine journals recipe/hash/profile identity and refuses a silent changed-checkpoint or changed-manifest resume. Use a *new batch ID* for changed workflow/model or tests. ComfyUI is a separate process; Prehnite does not yet attest its loaded GPU weights. If it fails due to VRAM/graph compatibility, keep exact error and sanitized hardware observations rather than asserting success.

## B. First fal.ai trial (paid, opt-in, no private input)

This exercises just one `FLUX.3 Klein` text-to-image request (no mask upload, upscale, Haiku judging or private source file). Price values in the example are **user-editable safety estimates, not a live fal quote or guarantee**. Verify [official fal.ai prices](https://fal.ai/models) and permitted output/use terms before spending anything.

```bash
python -m pip install -e ".[fal]"
prehnite doctor
prehnite trial-plan examples/manifest-first-fal.yaml \
  --profile examples/profile-first-fal.yaml \
  --mode fal --max-test-usd 0.20
```

The plan prints `provider_calls_made: 0`, configured max budget, per-operation attempted call counts and unknown live price status. `0.20` is merely the **example operator cap**, *not* a price quotation and not protection against external charges already incurred under uncertain network failure. Don't run if provider pricing or license terms are uncertain.

When YOU deliberately authorize a real billable request, set `FAL_KEY` only in a private environment (never in YAML/Git/issues), use a **new unique batch ID**, and run:

```bash
prehnite run examples/manifest-first-fal.yaml \
  --profile examples/profile-first-fal.yaml \
  --workspace /path/private/fal-workspace --inputs /path/private/inputs
```

Never retry ambiguous remote requests blindly. Save fal request IDs, final provider invoice and output hashes privately; compare the actual invoice to the planning estimate. Paid endpoint schema and rates can change independently of Prehnite. Additional fal segmentation is a *separate future test* requiring image-upload authorization and fresh rights review, not automatically enabled.

## C. Evidence needed to mark #134/#32 complete

Once real local GPU inference is done, preserve a **private** evidence directory with: OS/GPU/driver, VRAM and RAM observed, ComfyUI/runtime revision, exact file hashes, recipe/manifest/profile hashes and batch ID, cold/warm duration per stage, peak GPU VRAM/RAM *if actually measured*, screenshots or output PNG hashes, and the journal report. Capture and label OOM/error behaviour. Measure idle vs peak realistically, with a clearly noted tool and time window. Never invent unsupported hardware capacity tiers.

For quality, obtain a separately rights-cleared and **human-reviewed reference alpha mask**. Use the existing [real cutout evaluator](REAL_CUTOUT_BENCHMARK.md) to score binary IoU, normalized alpha MAE, and edge MAE. A measured number is not equivalent to owner-accepted output quality; record human verdict separately. Do not upload private images, model weights, journal database, API keys or provider invoices to public CI/GitHub issues.

The local hardware gate remains [#134](https://github.com/interzettel/prehnite/issues/134), model setup/download work [#135](https://github.com/interzettel/prehnite/issues/135), quality [#32](https://github.com/interzettel/prehnite/issues/32) and scheduler [#136](https://github.com/interzettel/prehnite/issues/136). The already published `0.1.0a1` PyPI release is immutable; these features need a later explicitly approved alpha version to become pip-installable.
