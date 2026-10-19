# First practical 8 GiB generation pilot

**Stage:** Research-backed candidate and offline pilot preparation. **No new physical inference has been run.** This is a reproducible starting point, not a generally certified 8 GiB GPU tier or a model-quality endorsement.

## Model/runtime choice

**First baseline: SDXL Base 1.0 through the existing local ComfyUI API adapter.**

Why this choice:

1. The original SDXL Base model is available from [Stability AI's model card](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0), under the **CreativeML Open RAIL++-M license**. The card explicitly documents running the base independently of the optional refiner. Its terms must still be checked by the local operator, including any commercial/distribution restrictions.
2. Prehnite has already recorded one **native 768 × 1024 SDXL** generation on the reference RTX 4070 Laptop 8 GiB, **46.04 seconds**, with sampled peak **7,763 / 8,188 MiB** of VRAM. See [local lab evidence](LOCAL_LAB_MILESTONE_2026-10-18.md). This is one observation, not three-run stability evidence, and it leaves little GPU headroom.
3. Reusing the known checkpoint/ComfyUI workflow avoids introducing new weights, a new model family or an untested inference runtime into the first repeatability study.

| Candidate | Case for it | Current reason not to switch first |
| --- | --- | --- |
| **SDXL Base 1.0** | Reuses the one observed local run, mature native-1K workflow and existing private model | Repeatability, system RAM stability and useful image yield not yet established |
| **FLUX.1 schnell FP8** | [Comfy-Org provides an FP8 ComfyUI package](https://huggingface.co/Comfy-Org/flux1-schnell), and [original weights](https://huggingface.co/black-forest-labs/FLUX.1-schnell) use Apache 2.0 | No comparable measurement with the same 8 GiB laptop/inputs yet; FP8 is not a guarantee of faster or feasible output on this machine |
| **fal.ai FLUX.3 Klein / Image** | Already covered by Prehnite's typed opt-in provider adapter for paid generation | Not a local-memory optimization baseline, requires a separately approved budget, account/API secret, and verified live endpoint behavior |
| **Other SDXL checkpoints / LoRAs** | May improve a specific brief and support Phase 2 consistency | Different weights change the model and quality baseline; do not silently substitute them in Phase 1 |

[ComfyUI's documented startup flags](https://github.com/Comfy-Org/docs/blob/main/development/comfyui-server/startup-flags.mdx) say async weight offloading is normally enabled on NVIDIA/AMD and dynamic VRAM may be enabled automatically. **Do not assume `--lowvram` is an optimization**: where dynamic VRAM is active it has no effect. Proposed first test is **unchanged known-working ComfyUI configuration**; only after a verified baseline should we compare one documented reversible memory configuration (for example, a controlled `--reserve-vram` value) using the *same* model, prompt, seed, sampler, graph and target size.

**This is a proposed model selection, not the owner decision gate P1-M01-R02.** Final choice, human criteria, permissions and resource thresholds remain explicit separate decisions.

## Batch contract

The [manifest](../examples/manifest-8g-sdxl-pilot.yaml) has **10 fixed, seed-pinned text-to-image briefs** at **768 × 1024, 3:4**, including ceramics, furniture, a still life and prehnite mineral. They are distinct prompts, not repeated trials. Those ten assets are a small useful-image pilot, not a repeatability experiment. The original **P08-A03** three-run benchmark targets **SAM2 segmentation**, with SAM2-specific nodes and image inputs. SDXL generation requires a **distinct** three-identical-generation-run protocol under P1-M02-E01; no SAM2 evidence can stand in for it.

The [local profile](../examples/profile-8g-sdxl-pilot.yaml) is ComfyUI only, single variant `native_1k`, one attempt, no cloud uploads/spend, no segmentation/upscaling, no external AI judge and no cross-batch cache. It retains **visually unverified technical candidates for manual review** (`uncertain: accept_unverified`). Do not treat Prehnite's technical acceptance status as human quality acceptance. Its exported API graph node IDs are **examples** and must be replaced with IDs from the actual local graph before execution.

There is an equivalent [synthetic demo profile](../examples/profile-8g-sdxl-offline-demo.yaml) solely for exercising journal/resume, estimates, reporting and export code without a GPU.

## Offline-only checks (safe now)

From the repository root and an installed development environment:

```bash
prehnite validate examples/manifest-8g-sdxl-pilot.yaml \
  --profile examples/profile-8g-sdxl-offline-demo.yaml

prehnite estimate examples/manifest-8g-sdxl-pilot.yaml \
  --profile examples/profile-8g-sdxl-offline-demo.yaml

python scripts/score_8g_pilot.py plan \
  --manifest examples/manifest-8g-sdxl-pilot.yaml

prehnite run examples/manifest-8g-sdxl-pilot.yaml \
  --profile examples/profile-8g-sdxl-offline-demo.yaml \
  --workspace workspace-pilot-demo
```

The last command runs **synthetic/demo generation only**. It exercises the existing engine end to end, including a second run against the same workspace for recovery. Its outputs are not AI photographs, model performance samples or live GPU acceptance.

## Before any real physical run

A local operator must receive **new explicit scoped permission** that fixes which model/checkpoint and exact hashes, ComfyUI revision/graph, sampler/steps, stop conditions, RAM/commit/VRAM preflight floors, time budget, output privacy, no additional installation or retries, and cleanup. The earlier P08-A03 proposal has its own stricter one-startup, three-identical-run constraints. There is no implied approval to reuse that authorization for ten distinct images.

Check the [micro recipe execution contract](RECIPE_EXECUTION.md) and [first real asset guide](FIRST_REAL_ASSET.md). This generation-only manifest **does not satisfy the existing three-stage recipe's cutout graph requirements**. Do not falsely label a generation-only engine run as recipe-attested unless an appropriate generation-only recipe schema is separately implemented and reviewed.

The code/profile never starts ComfyUI or installs models by itself; `prehnite run` **will submit actual generation to a locally running ComfyUI server if the local profile is supplied**. Only use it after the above authorization and privacy/rights checks.

## Measure usable yield (privately and read-only)

The [offline pilot scorer](../scripts/score_8g_pilot.py) is deliberately separate from inference and never opens network connections. It accepts `--outputs` pointing to the batch's own `workspace/batches/<batch-id>/selected` folder (or an approved copy containing exactly the specified relative output paths), plus a private review JSON.

```bash
python scripts/score_8g_pilot.py evaluate \
  --manifest examples/manifest-8g-sdxl-pilot.yaml \
  --outputs /private/workspace/batches/sdxl-8g-pilot-001/selected \
  --receipt /private/review.json
```

Receipt fields:
- top-level: `schema_version: 1`, exact `batch_id`, `origin: real_local_comfyui` or `synthetic_demo`, `operator`, `reviewer`, timezone-aware `reviewed_at`, declared `model_sha256` and `workflow_sha256`. A real run also requires an `authorization_receipt` reference.
- `assets`: ten uniquely indexed image IDs with `outcome: generated` or `failed`, mandatory `decision: accept/reject` and an informative `failure_reason` when rejected.
- for generated output: exact manifest relative path, the **locally rehashed** SHA256, native PNG resolution, human scores 1–5 for `prompt_adherence`, `composition`, `material_and_edges`, and `usable_for_brief`. Failed generations require no fictional artifact or visual score.
- measured `elapsed_seconds` per attempted item, and **real sampled** `sampled_peak_vram_mib` and `min_available_ram_mib` together, or both `null` if missing. Missing samples remain unknown, never zero.

Report: generated/failed count, accepted-image **yield out of all ten attempted prompts**, median/p95 item time, total seconds / accepted image, sampled peak GPU and minimum available RAM, resource sample coverage and failure-reason distribution. A zero-accepted batch has `seconds_per_accepted_image: null`, not infinity or zero. Output hashes attest file integrity but not model/runtime residence.

**A positive scorer result is an operator report, never independent GPU attestation.** Even a 100% synthetic-demo yield remains `eligible_as_accepted_real_batch: false` and `independently_verified: false`. Independent source verification and actual owner visual acceptance still gate P1-M04-E01 and P1-M05-A01.

## Optimization comparison, after baseline acceptance

Keep exact checkpoint and ComfyUI graph hashes, seeds, prompts, dimensions, sampler, steps, runtime revision and host hardware constant. First measure unchanged settings over a repeatable run, then change **one** memory/scheduling variable. Compare elapsed distribution, peak VRAM, *available system RAM*, system commit, failures, manual quality scores and accepted-image yield. Check that any reported improvement does not simply reduce resolution, skip requested images or use a different model. Never equate memory savings with higher visual quality.

Phase 2 LoRA studies should run only after a stable base/adapter provenance contract is accepted, because switching LoRAs changes the comparison.

## Sources and traceability

- [SDXL model card and Open RAIL++-M terms](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)
- [Official ComfyUI startup VRAM and offloading flags](https://github.com/Comfy-Org/docs/blob/main/development/comfyui-server/startup-flags.mdx)
- [FLUX.1 schnell original model and Apache 2.0 terms](https://huggingface.co/black-forest-labs/FLUX.1-schnell)
- [ComfyUI FP8 repackaged schnell option](https://huggingface.co/Comfy-Org/flux1-schnell)
- [Prehnite 2026-10-18 observed local lab](LOCAL_LAB_MILESTONE_2026-10-18.md)
- [Canonical roadmap and current task gates](../progress/roadmap.json)
