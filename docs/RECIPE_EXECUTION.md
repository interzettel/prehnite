# Local micro recipe execution boundary (experimental)

This connects the offline-only model binding from [#135](https://github.com/interzettel/prehnite/issues/135) to the existing engine/SQLite journal. It supports an **explicitly configured local ComfyUI run**, not a certified model installation, quality result or GPU profile. Unlike `prehnite recipe-resolve`, the `prehnite run` command **does attempt real local inference** when a configured ComfyUI server is available. No third-party weights ship with Prehnite.

## Before attempting a run

- Install and operate ComfyUI and your own separately licensed generation/segmentation models locally. You are responsible for terms and checkpoint provenance.
- Supply real ComfyUI API-format generation and cutout graphs, exact local SHA256 bindings, the pinned recipe hash and terms acknowledgements as described in [LOCAL_MODEL_RESOLVER.md](LOCAL_MODEL_RESOLVER.md).
- Set `PREHNITE_WORKFLOWS` to exactly the folder passed to `--workflows`. The existing ComfyUI API adapter must be able to access and load the exact graphs and checkpoint names on your local ComfyUI installation.
- The initial engine bridge accepts **only** the three-stage `prehnite-micro` preview: `generate -> cutout -> quality`. Configure generation as `comfyui:user-workflow`, segmentation as `comfyui:user-segmentation`, judge as `demo:technical`, no upscaler and `variants: [native_4k]`. The profile must specify the corresponding workflow filename and explicit `output_node` for each stage, plus all required graph input mappings. The graph must explicitly reference each bound checkpoint filename. No automatic model resolution or hardware suitability guarantee follows from these static checks.
- Disable cross-batch cache, paid providers, cloud uploads, estimates and maximum spend. This path currently rejects MCP job tokens and hosted macro recipes.
- Start with a **new** batch ID. Use the same exact manifest/profile/recipe and unchanged local checkpoint/graph bytes on subsequent runs.

```bash
prehnite run ./my-manifest.yaml --profile ./my-local-profile.yaml \
  --workspace ./workspace --inputs ./inputs \
  --recipe ./recipes/prehnite-micro/0.1.0-preview.1.json \
  --bindings ./my-private-bindings.json \
  --workflows ./my-private-workflows \
  --checkpoints ./my-private-checkpoints
```

No private source images, prompt files or model binary files are committed by these instructions.

## Persisted guarantees and limits

The journal transactionally records the exact recipe ID/version/hash, resolved binding hash and manifest/profile fingerprint before the first stage. A matching resume is idempotent; a changed checkpoint or graph, changed profile/manifest, missing recipe flags or retroactive attempt to bind an older batch **fails closed**. Verification runs again under the engine's exclusive run lock, before any stage starts. The report JSON exposes only this non-sensitive identity, not private filesystem roots.

This is a **startup/checkpoint guard, not immutable checkpoint memory residency**. ComfyUI is a separately operating local process and can potentially load different bytes after static verification; Prehnite cannot yet attest to the live ComfyUI node graph/model load. The hash receipt does not prove that the configured model loaded, inference ran, quality was acceptable, or the user's laptop supports 4/6/8/12GB VRAM. There is no authenticated ComfyUI checkpoint runtime handshake, no signed model provenance, no first-run installer, no real GPU benchmark, no human cutout gold evidence and no recipe-aware MCP worker in this tranche.

**Safety:** The journal must not silently migrate old jobs or retry ambiguous paid requests. Previously accepted work remains keyed to its original configuration. If the user wants a different graph/model/version, create a new batch ID. No output quality certification is implied by passing offline tests.
