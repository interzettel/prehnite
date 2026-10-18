# Prehnite — agent/session handover (2026-10-18)

> **Snapshot, not a live status page.** Read this before resuming the first real image/cutout acceptance trial or the Micro/Mezzo/Macro architecture discussion. Check GitHub, the local lab and newer reports for any changes since this handover. **Do not equate plan, static validation, completed GPU work, or human approval.**

## 1. Identity, authorities and operating rules

- **Public repository:** [interzettel/prehnite](https://github.com/interzettel/prehnite) (MIT Python image-production engine, CLI/MCP/ComfyUI adapter, strict quality/budget/journal/provenance pipeline). **Private separate Windows lab:** `prehnite-local-lab`, containing operator-owned model files, original render and review records; never add those bytes to the public repository.
- **Roles:** ChatGPT coordinates architecture, reviews evidence and may update the **public upstream** repository through authorized GitHub access. A separate **local Codex agent** uses the owner's RTX 4070 Laptop Windows machine to do explicitly approved setup/inference. ChatGPT **cannot claim to have run local GPU inference**. Local agent may progress only within the owner's explicit gate.
- **Current snapshot:** public `main` `5f70965a830fc7f77d5369651565fd136cffe652`, no open PRs when checked; private lab latest reported commit `3d324b2` clean. Changes after this snapshot require checking, not guessing.
- **Hard principles:** no unauthorized network/model downloads, package changes, cloud uploads/paid calls or GPU repeats; original source batch never rewritten; exact SHA256-bound sources and review receipts; `uncertain: reject` remains strict; technical pass != visual acceptance; output cutouts remain `review_pending` until independently reviewed; provenance claims must distinguish observed, declared, and unverified facts.
- Release metadata: editable development source reported as `0.1.0a2.dev0`; publicly published `0.1.0a1` wheel does **not** contain later handoff features. See [README](../README.md), [roadmap](ROADMAP.md), [progress](progress/STATUS.md). Do not change frozen progress percentages or award hardware/quality/legal release gates without independently supporting evidence.

## 2. What the owner last authorized — **Gate 3**, one run only

Owner's **latest explicit authorization** was **one local GroundingDINO SwinT + SAM 2.1 base_plus segmentation attempt** of the already-reviewed SDXL table-lamp PNG. The comprehensive operator instruction has already been sent to local Codex, which is expected to execute it. **Do not independently submit another `/prompt`, execute the command twice, auto-retry, or reinterpret authorization as permission for BiRefNet, more model downloads, any package replacement or hosted inference.**

**Status at handover:** Gate 3 **authorized, not yet reported as executed**. Latest local report is Gate 2 static validation; no runtime segmentation output, mask, PNG or GPU load has been seen. If a subsequent Codex report arrives, inspect it first and update the state accordingly.

Gate-3 scope:
1. Rehash source, review, handoff, dependency inventory, installed weights and actual graph; verify local ComfyUI healthy, queue empty; check RAM/VRAM. Ensure the local-image upload via Prehnite maps to the actual ComfyUI `LoadImage` node (the placeholder filename in the static graph is not runtime proof).
2. Execute **one** `prehnite run` of a **new** reviewed-source cutout batch: one ComfyUI `/prompt` through existing adapter; zero generation/upscaling/judging, cloud cost 0, `maximum_attempts=1`, `uncertain=reject`, no automatic repair. Prompt `table lamp`, detection threshold `0.3`, `keep_model_loaded=false`, installed SAM2 base-plus and GroundingDINO SwinT. Avoid unintended automatic model downloads; monitor/refuse external egress if enforceable without system-wide firewall mutation.
3. Preserve measured stage/wall time, VRAM/RAM/commit peaks, failures, ComfyUI prompt ID, file hashes, raw mask, RGBA cutout and 1:1 detail/candidate composites; report whether power cord, tabletop, cast shadow or background were included. If failure/timeout/OOM: **stop without a second submission**; keep honest failure evidence.
4. The resulting candidate is *not* automatically accepted. Human review should inspect lamp shade perimeter/top rim, thin stem, ceramic base, contact edge, and the exiting cord, ideally on checkerboard/black/white backgrounds.

Gate 3 has no authority to upgrade/downgrade packages, add models, regenerate SDXL, alter original review, run a benchmark suite or try a second threshold. The local machine has limited available RAM: avoid simultaneous jobs.

### Local run packet (private; do not commit)

All paths below are relative to `prehnite-local-lab/` unless noted:

| Artifact | Private relative path | SHA256 |
| --- | --- | --- |
| Reviewed source | `_private/sdxl-1k/handoff-v2/inputs/reviewed-source.png` | `282e6d4af8ab3a68cafef674ff33d8bd20001be3b4dfedfb216c853fca6832d3` |
| Original human review Markdown | `_private/sdxl-1k/handoff-v2/inputs/original-human-review.md` | `97f66bcd94f2752894279576276facd5839d652cbdd605226834f67551c15dad` |
| Structured human-attestation JSON | `_private/sdxl-1k/handoff-v2/inputs/review-handoff.json` | `f1aa31d0014c640f9eddf8e235bcd6517e4b8e3f5a5084620ab2fa242c9666ec` |
| Original handoff manifest (unchanged) | `_private/sdxl-1k/handoff-v2/manifest-reviewed-cutout.yaml` | `9813e6186800b4fb1e399e8d5cd843f804109737410bc7353113b4abc9a7bb7b` |
| Eight-file implicit dependency inventory | `_private/sdxl-1k/handoff-v2/inputs/implicit-dependencies.json` | `e310f771cc6d681023d8b9103df8f9128e13cacc97746cbbdfd9b664a7ff07ea` |
| Dependency-aware handoff manifest | `_private/sdxl-1k/handoff-v2/manifest-reviewed-cutout-deps.yaml` | `4c3f5b6045e50c9d08d5f6658ced410da3fdd387eaeb5e44618044367e52ad94` |
| Live-schema-validated ComfyUI API graph | `_private/sdxl-1k/handoff-v2/cutout_api.json` | `bb96de575d0ce3de0a72ff67440b5e650a47c993977bb33a08071987bda29d23` |
| Installed segmentation profile | `_private/sdxl-1k/handoff-v2/profile-segmentation-installed.yaml` | `c74c95b44280d56fec47d7840a4ca83f38f87f59e0291f24ac15fcae09240b3b` |
| Offline graph check receipt | `_private/sdxl-1k/handoff-v2/graph-validation.json` | `682ebe9882fcb925dc90580eed41048cbe59de40867243a7b69add66df44e49e` |

**Owner verdict:** `accepted_for_next_stage` refers only to the **unchanged generated source PNG**; original generation batch `sdxl-1k-generation` still has engine status **rejected** for `Visual quality unverified and policy rejects uncertainty`. Source is 768×1024 RGB; one lamp, diffuse neutral studio backdrop. Include lamp body + shade. Exclude **power cord, tabletop, cast shadow, background**. Keep original image/review/masks unmodified. The new batch reported in the private manifest is `lamp-reviewed-cutout-deps`; the earlier handoff batch was `lamp-reviewed-cutout-new-batch`. Do not confuse them.

For command structure and vetted private paths see the latest local report:
`prehnite-local-lab/results/2026-10-18-gate2-sam2-install.md`.
Core command uses `prehnite run` with `--profile`, `--workspace`, `--inputs`, `--dependencies-root`; `PREHNITE_WORKFLOWS` must be set to the private graph directory. **Never paste unverified local file paths or run the command merely to check status.**

## 3. Real machine / Gate 1 and Gate 2 evidence

**Generation already performed**: one successful SDXL Base 1.0 native-1K lamp generation, ~46.04 s, Euler 25 steps, CFG 7, seed 42, 768×1024, observed sampled peak VRAM **7,763 / 8,188 MiB**. This proves a successful single SDXL generation, not reproducibility, no-OOM guarantee, or combined model residency.

**Gate 1 (model bytes)**: GroundingDINO SwinT `693,997,677` bytes SHA `3b3ca2563c77c69f651d7bd133e97139c186df06231157a64c507099c52bc799`; SAM 2.1 base-plus `323,606,802` bytes SHA `a2345aede8715ab1d5d31b4a509fb160c5a4af1970f199d9054ccfb746c004c5`; BERT base-uncased safetensors `440,449,768` bytes SHA `68d45e234eb4a928074dfd868cead0219ab85354cc53d20e772753c6bb9169d3`; plus GroundingDINO config and BERT config/tokenizer/vocab. **8 files, 1,458,753,441 bytes**, all byte-verified in staging and later in active model directories. Static coverage: `operator_declared_implicit_only`; graph completeness, actual weights loaded at runtime, independent model rights and segmentation quality are **not yet verified**. SAM2 extra HF `config.json` not downloaded; extension includes `sam2_configs/sam2_1_hiera_base_plus.yaml`.

**Gate 2 (successful)**: user/local Codex installed `neverbiasu/ComfyUI-SAM2` at immutable Git commit `757034be78e877c07db8e7913f489089af224630` into the **managed backend** under `C:\Users\yigit\Documents\ComfyUI\custom_nodes`. Active model directory is `C:\Users\yigit\Documents\ComfyUI\models`. The initial `transformers 5.20.0` + torch 2.7 incompatibility (`torch.distributed.checkpoint.hf_storage`) was fixed by an owner-approved single-package upgrade to `transformers 5.20.1` (wheel SHA `5f51ce444193e5d0a751e3fa489ddbc2224ff12f6675a5cfefd4044b09757c19`; upstream fix [huggingface/transformers#49652](https://github.com/huggingface/transformers/pull/49652)). Other existing packages unchanged. `pip check` clean, `BertModel` import passes. Torch `2.7.0+cu128`; torchvision `0.22.0+cu128`; numpy `1.26.4`; Python `3.12.9`; ComfyUI `0.41.0`.

All 3 nodes registered at local `/object_info`:
- `GroundingDinoModelLoader (segment anything2)` selected `GroundingDINO_SwinT_OGC (694MB)`
- `SAM2ModelLoader (segment anything2)` selected `sam2_1_hiera_base_plus.pt` (real disk basename `sam2.1_hiera_base_plus.pt`)
- `GroundingDinoSAM2Segment (segment anything2)` prompt `table lamp`, threshold 0.3, keep loaded false; image, two model inputs; `MASK` output index 1 to `MaskToImage`, then `SaveImage`.

Six graph nodes: 1 LoadImage, 2 GroundingDINO loader, 3 SAM2 loader, 4 GroundingDinoSAM2Segment, 5 MaskToImage, 6 SaveImage. Prehnite `input_node=1`, `target_node=4`, `target_input=prompt`, `output_node=6`. **27 static checks passed** against actual live schemas; NO models loaded and NO `/prompt` submitted through Gate 2. No automatic downloads observed during registration. `ComfyUI-SAM2` can auto-download absent assets during **model loading**; file presence and external egress remain a concern.

**Last idle hardware snapshot:** available RAM 5,767 MB, committed memory 86.0%; VRAM 909 MiB used / 7,040 MiB free (8,188 MiB total); GPU idle. Monitor actual resources at runtime; these numbers are not a feasibility certificate. The background ComfyUI process was restored using a correctly quoted launch command; the Manager's legacy restart command is broken for a spaced `Comfy Desktop` directory and must not be reused. The backend was not running under the original Desktop launcher as reported.

Local reports:
- `prehnite-local-lab/results/2026-10-18-reviewed-handoff-validation.md` — exact review handoff, 21 offline tests.
- `prehnite-local-lab/results/2026-10-18-implicit-dependency-validation.md` — 8-file hashes, 16 pass / 1 skip.
- `prehnite-local-lab/results/2026-10-18-gate2-sam2-install.md` — import and live static schema, 27 checks, zero inference.
The local lab reports are **operator-provided evidence**; don't represent them as independently re-executed on this assistant's machine.

## 4. Relevant merged public PRs, documentation and open issues

- [PR #155](https://github.com/interzettel/prehnite/pull/155), merge `c48ba8730e97e13bb7e008b306daaa060908066c`: hash-bound, reviewed-source-only new batch; original review plus separate operator-attested JSON; no regeneration, no automatic judge/promotion, `review_pending`.
- [PR #157](https://github.com/interzettel/prehnite/pull/157), merge `5f70965a830fc7f77d5369651565fd136cffe652`: optional `handoff.implicit_manifest`/SHA and `--dependencies-root`; hash-pinned operator-declared weights, configs, tokenizer dependencies, replay validation; **not** runtime-loaded-model attestation. Both PRs passed 25/25 CI; no source release tag/publishing implied.
- [Reviewed-source handoff](REVIEWED_SOURCE_HANDOFF.md), [implicit dependencies](IMPLICIT_DEPENDENCIES.md), [multi-file provenance](MULTIFILE_PROVENANCE.md), [first-real-asset runbook](FIRST_REAL_ASSET.md), [roadmap](ROADMAP.md), [model recipes](MODEL_RECIPES.md), [recipe runtime](RECIPE_EXECUTION.md).
- [Issue #156](https://github.com/interzettel/prehnite/issues/156) remains **open** for real custom-node/implicit dependency load provenance; installation plus static hashes do not close it.
- Keep [#132](https://github.com/interzettel/prehnite/issues/132), [#134](https://github.com/interzettel/prehnite/issues/134), [#135](https://github.com/interzettel/prehnite/issues/135), [#136](https://github.com/interzettel/prehnite/issues/136), and [#32](https://github.com/interzettel/prehnite/issues/32) distinct: versioned recipes, physical machine evidence, rights/sourcing, resource scheduling, real cutout/visual acceptance. Do not infer closed/open issue state from this snapshot—check live GitHub.

## 5. Research direction from latest design discussion — **not yet adopted**

The owner proposed **Prehnite Micro / Mezzo / Macro** as three modes. Public research and comparison with [ComfyUI](https://github.com/Comfy-Org/ComfyUI), [InvokeAI](https://github.com/invoke-ai/InvokeAI), [SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI), [Hugging Face Diffusers](https://huggingface.co/docs/diffusers/optimization/memory), [rembg](https://github.com/danielgatis/rembg), [BiRefNet Lite](https://huggingface.co/ZhengPeng7/BiRefNet_lite) and [Grounded-SAM-2](https://github.com/IDEA-Research/Grounded-SAM-2) suggested **execution policies over versioned interchangeable recipes**, not three new fixed model bundles or a second GPU scheduler:

| Proposed policy | Design intention, not benchmark claim | Plausible route |
| --- | --- | --- |
| **Micro** | Low-resource, simple workflow; target 8 GB-class hardware based on *measurement*, not presumed concurrent residency | compact local generator + single-stage foreground remover (e.g. BiRefNet Lite or rembg/ISNet), or other proven low-memory arrangement |
| **Mezzo** | More capable **sequential local** pipeline, with model loading/offloading delegated to established backends | SDXL/new generator → targeted GroundingDINO + SAM2 as needed → local alpha/edge refinement → review |
| **Macro** | Optimize real **cost per human-accepted deliverable**, not biggest model / cheapest isolated inference | stage-specific model routing, quality-driven authorized escalation, selective review, measured costs, existing multi-worker backends when useful |

**Important compatibility distinction:** existing versioned `prehnite-micro` preview recipes and `prehnite-macro` blueprint already exist (see [ROADMAP](ROADMAP.md)); **do not silently redefine their contracts**, advance percentages or treat a proposed Mezzo as a production recipe. Introduce explicit versioning/migration and tests before modifying recipe semantics. Mezzo has **not** been implemented.

**Highest-value research hypothesis:** we may not need GroundingDINO + BERT + SAM2 to cut out one centered product lamp on a simple background. A direct foreground removal model (particularly BiRefNet Lite, which has a small openly available model) might be faster and simpler; licensing, quantization, RAM/VRAM fit and edge quality must be independently checked on the specific model/version. Language-grounded detection + SAM2 remains useful when extracting a **specific named object** from a multi-object scene. Glass, fine strands or translucency may require dedicated matting or human intervention. Do not add mandatory detection just because it is technically available. Commercial restrictions differ across models; e.g. BRIA RMBG-2.0 is not an automatic commercially unrestricted default.

**Avoid reinventing:** ComfyUI scheduler/model swapping, generic multi-GPU resource orchestration, a new segmentation network, a full custom distributed runtime, blind exhaustive search. **Build eventually:** typed recipe capability + hardware budget declarations, simple policy-based strategy selection, transparent multi-file byte provenance, meaningful per-stage memory/cost/latency telemetry, quality/rights gates and controlled escalation. Model-residency is a *choice*, not the defining criterion of Micro: fitting all weights simultaneously is unnecessary if stages can unload sequentially. Offloading has CPU-RAM/bandwidth costs, especially on the measured laptop.

**Benchmark before planner**: Same immutable source across SAM2 and later separately approved single-model cutout, compare *raw masks + human-reviewed alpha*, timing, peak VRAM, peak committed RAM, model loads, edge/cord correctness and actual correction labor. Further representative categories: thin wire, glass, hair/fabric, cluttered multi-object, dark-on-dark, then batch throughput. No new model download/inference benchmark is authorized by this document. **First finish the already-approved one-shot SAM2 baseline** and review its output; then propose a separately authorized BiRefNet Lite comparison. Do not assert which will win before evidence.

## 6. Exact next-agent workflow

1. **First ask whether a local Codex Gate 3 report/result has arrived** (or read an attached result). If one exists, examine the concrete log, new batch journal/report, source and output SHA256, GPU telemetry, raw mask and PNG before offering quality verdicts. A local text claim alone is not a visual inspection of alpha edges.
2. If **Gate 3 is still pending**, do not duplicate it. The owner already authorized **one** run for local Codex; wait for result and help debug only within that authorization. If the attempt was submitted but interrupted, **never assume a retry is permitted**; inspect the ComfyUI prompt ID/queue/history and journal first.
3. If success, request/upload/share **private review composites/crops** (no public GitHub image upload without owner approval). Review thin power cord exclusion, lampshade/background separation, top rim and base contact. Separate engine technical status from independent human mask acceptance. Keep candidate `review_pending` until explicit owner judgment.
4. If failed or OOM, preserve unchanged experiment artifacts and propose a *new separately authorized* diagnostic or single-model approach. Prioritize RAM pressure and model offloading evidence; avoid a blind series of retries.
5. After the SAM2 baseline, propose the **minimum** BiRefNet Lite or rembg/ISNet acquisition/installation/one-run gate needed for an apples-to-apples comparison, including licence verification, output contract and measured resource constraints. Do not download/run without explicit owner consent.
6. For architectural work, draft a short [issue #132](https://github.com/interzettel/prehnite/issues/132) comment or an **unmerged** design proposal only after confirming existing recipe schema/contracts. No implementation solely to satisfy the three names until baseline evidence supports the policy boundaries. If doing GitHub edits, run the relevant tests/CI and cite exact PR and merge state.
7. Keep [issue #156](https://github.com/interzettel/prehnite/issues/156) open until operator-declared hashes can be related to actual executed model file paths/runtime loader evidence; never call eight-file static hashes a complete runtime SBOM.

## 7. Do-not-confuse checklist

- Original SDXL generation **rejected by automatic visual gate** despite a technically successful GPU run; human receipt is **accepted_for_next_stage** only.
- 27 ComfyUI **static** checks and SAM2 node registration are not successful segmentation/inference.
- A mask image or technically valid RGBA image is not a human-accepted good cutout.
- 8-file byte attestation is not all-implicit-dependencies discovery or runtime residency proof.
- PR #157 and Gate 2 have already been completed. Gate 3 has **one-run authorization**, but completion evidence was **not yet received at this handover**.
- No concurrent SDXL generation during first cutout, no remote/paid workflow, no auto-download and **no second submission** without separate user permission.
- Do not confuse an engineering plan to compare BiRefNet with authorization to download or run it.

**Primary next question to user/local agent:** *What is the outcome of the single authorized Gate 3 run? Please provide its report and mask/cutout images if it has finished; otherwise continue waiting for Codex rather than launching a second job.*
