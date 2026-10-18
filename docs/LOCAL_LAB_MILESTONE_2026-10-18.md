# First accepted local cutout — evidence snapshot (2026-10-18)

**Status:** One actual, owner-authorized, local GroundingDINO + SAM2 cutout was produced, conservatively refined on CPU and **independently visually accepted for this artifact at the reviewed comparison scale**. The acceptance was documented in the **private local lab**; it is **not an owner-signed Prehnite journal acceptance**, release certification, representative benchmark, or bundled model workflow.

This page is a **public textual evidence index**, not a replica of the private image corpus or an inference script. The source, masks, composites, weights, per-machine paths, private reports and approval JSON stay in `prehnite-local-lab`. Local operator reports were provided to the project; no GitHub runner independently re-executed the GPU job.

## What actually happened

| Step | Observed result | Boundary |
| --- | --- | --- |
| Source generation | One SDXL Base 1.0 native **768 × 1024** desk-lamp image on an RTX 4070 Laptop GPU; generation ~**46.04 s**, sampled peak VRAM **7,763 / 8,188 MiB** | Original generation batch did **not** automatically pass visual-quality policy. Source was separately permitted for the cutout stage; this does not certify SDXL 4K performance. |
| First segmentation attempt (Gate 3) | **Failed**, prompt ID `1f0c7c40-4b09-402d-997d-6ce46d4a5e66`, missing legacy `BertModel.get_extended_attention_mask` on Transformers 5.20.1 | Kept as immutable failed evidence; no masked output or retry within that batch. |
| Compatibility recovery | Pinned `ComfyUI-SAM2@757034be78e877c07db8e7913f489089af224630` and **Transformers 4.57.6 / huggingface-hub 0.36.2 / tokenizers 0.22.2** in a private child-process import overlay; Torch **2.7.0+cu128** reused from the installed ComfyUI venv | The shared environment remained at Transformers 5.20.1. Synthetic BERT/mask parity and live node/schema registration were tested separately; no new package/model was shipped with Prehnite. |
| Successful segmentation | One fresh local batch `lamp-autonomous-20261018T1819`; ComfyUI prompt `ab4cb4d3-3b87-4cab-9ad9-666112f12236` reported successful completion in **8.994 s** (model loading plus inference) | **Exactly one** segmentation submission to the working isolated process. No segmentation retry, SDXL regeneration, cloud call or paid request. |
| Raw mask | **768 × 1024**, one connected foreground component, zero holes, binary alpha, **16.44%** canvas coverage; bbox `[231, 272, 590, 924]` | Technical mask validity is not the same as visual acceptance. |
| CPU-only edge refinement | Two alternatives: A (**σ = 0.65 px**, hard-mask IoU **1.0**, no hard-pixel changes); B (σ = 1.0 px, IoU 0.999961, five hard-pixel changes) | Both derivatives retained; original binary mask and RGBA were not rewritten. |
| Independent visual review | **Candidate A accepted for this specific lamp and reviewed display scale**, after comparing original/A/B silhouettes and crops of shade, stem and base | Candidate B not selected. No guarantee for arbitrary backgrounds, high enlargement, other objects or materials. |
| Acceptance recording | Private `ACCEPTANCE.md` and `approval.json` committed under local lab commit **`b79a6cb`** | Independent visual approval record only; not owner-authenticated journal promotion or pipeline-wide certification. |

The successful cutout run reported a **2,533 MiB sampled VRAM peak**, **55% sampled GPU utilization**, **3,338 MB minimum available system RAM**, and **57.6% maximum system commit**. The standalone segmentation service started in **9.25 s** on the successful job runtime, and the observed prompt completion interval was **8.994 s**. Model-load and inference sub-times were **not separated**, process-private peak RAM was **not sampled**, and figures are from one setup/run, not repeatable performance distributions. No claim of feasible concurrent SDXL+SAM2 residency follows.

## Exact artifact identity and private evidence

- Reviewed input SHA256: `282e6d4af8ab3a68cafef674ff33d8bd20001be3b4dfedfb216c853fca6832d3`
- Pinned segmentation graph SHA256: `bb96de575d0ce3de0a72ff67440b5e650a47c993977bb33a08071987bda29d23`
- Raw mask SHA256: `d0e666267bc33ab046bd146576a1911b3a6c6e4072c159a5b68cab941ae07971`
- Initial RGBA cutout SHA256: `454b27ed1b214c9adb50f8ffc4c15a73ce80bd89fea2513abfeaed68feecf968`
- **Visually approved Candidate A SHA256:** `5e925240e2c527a9922ffad2729fcb9111ed25251f3c2aedfba8c87903bd6450`
- Private visual acceptance markdown SHA256: `2c8721b1b03e225034ae3910c16c9fe87d30e96d6fcc0b1d6d63d181399acd08b1d6fcc0`
- Private machine-readable approval SHA256: `109880d217b7bdca715e7be63975f5ac7218155960b937b4c0c9af8a9886988f`
- Private local lab report: `results/2026-10-18-local-cutout-autonomous-session.md` (SHA256 `9ecb5927c8700459d43ef7537549b41a917c1fa821b1993a1f290edb56fc3f38`)
- Local review folder: `review/2026-10-18-local-cutout-alpha-refinement/`; approved derivative under `approved/desk-lamp-candidate-a-approved.png`.

The public repository intentionally does **not** contain these private image files or model weights. A SHA establishes bytes, not rights, human identity or runtime-resident model attestation. Local runner evidence can be checked by an authorized operator with access to the lab.

## What counts as completed now

- A **real local model path** has been exercised on the owner's named 8 GiB-class laptop, using existing pinned checkpoints and a short-lived, private ComfyUI runtime.
- One segmentation mask and transparent cutout were created, then one conservative CPU-finished derivative was independently visually approved.
- A workable **process-isolated dependency compatibility overlay** was demonstrated without downgrading the shared ComfyUI environment.
- Source, dependency, workflow, submission count, runtime observations and acceptance records can be traced across the local lab.

## What explicitly remains open

- The current public package does **not** bundle the local launcher, 4.57.6 overlay, models, refinement procedure or turnkey accepted pipeline. These remain private lab implementations; [productization](ROADMAP.md) is the next software step.
- No general **4/6/8/12 GiB model tier**, multiple-machine reproducibility, 4K real image viability, uninterrupted long-batch behavior or cost/quality throughput distribution has been established.
- No independent alpha reference corpus, measured hair/glass/translucency/multi-instance benchmark, calibrated judge or robust single-object model comparison exists.
- No comprehensive model-rights certification, runtime-loaded dependency completeness, third-party weight redistribution approval, real paid API reconciliation or production release gate follows.
- The original **61-unit release ledger remains 42/61**, the frozen **73-task register remains 14/73**, and the release matrix remains **4 verified / 7 partial / 5 unverified**. Those denominators refer to stricter, separately scoped contracts. This **new case-study evidence** does not satisfy a full outstanding parent unit such as 8 GiB feasibility across recipes, gold-standard category benchmark, 90-item live run or final release.

## Next product milestone

Turn the local-runner success into reviewed, reproducible, optional Prehnite functionality:

1. Refactor the private ComfyUI process-launch/import overlay and CPU alpha refinement into testable, optional integration with no private paths or weight redistribution.
2. Finish **[draft resource-readiness PR #159](https://github.com/interzettel/prehnite/pull/159)** independently of the private hardware runner; a passing resource preflight is not authorization to infer.
3. Define a versioned cutout execution/refinement/acceptance receipt that distinguishes **resource observation**, **compatibility**, **technical completion**, **mask quality**, **independent visual approval** and **owner-signed journal promotion**.
4. Test offline synthetic/mock error paths first, then seek separate authorization for diverse-image, real-model validation. Never treat this one accepted lamp as an automated quality metric.

See [delivery readiness](PROGRESS.md), [roadmap](ROADMAP.md), [61-unit tracker](progress/STATUS.md), [atomic task tracker](progress/ATOMIC.md), and [first-real-asset operator guide](FIRST_REAL_ASSET.md).
