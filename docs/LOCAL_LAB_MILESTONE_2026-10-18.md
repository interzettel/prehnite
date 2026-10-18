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

## Productization and merged public source (same date)

**Productization Sprint 1 and closeout are complete locally.** The local lab
advanced from `da7b478` (initial implementation) to **`896fdea`**
(documentation synchronization, audit and closeout). Reusable source code was reviewed and **merged to development `main`** as [PR #161](https://github.com/interzettel/prehnite/pull/161) at squash commit `ca78b8b`, after [PR #159](https://github.com/interzettel/prehnite/pull/159) resource-readiness integration (`ef54488`). The preceding #161 code-review fix head was `9949367`. These merges are **not a new packaged PyPI release**.

- `src/prehnite/cutout_quality.py`: source/target/workflow/model SHA256
  contracts, configurable CPU alpha candidates, nearest-foreground RGB
  expansion, mask/alpha technical QA, seven distinct evidence states and
  create-only independent visual review records.
- Additive, **opt-in** `prehnite cutout-qa` and `cutout-accept`, regression
  tests and `docs/LOCAL_CUTOUT_PIPELINE.md`. The existing `Engine` continues
  to own execution, journals, recovery and no retry; the QA step is not yet
  automatically linked to the Engine.
- Private `scripts/prehnite_local_runtime.py` consolidates
  `preflight/check/start/status/stop`. It and the model environment remain in
  the private lab, **not shipped in the PR**.
- **Engineering checks:** review-resolution head `9949367` reported 21 cutout tests passed; host full suite **872 passed / 15 skipped / 1 Windows symlink-privilege failure**; private combined integration session (`3a08740`) reported **890 passed / 15 skipped / 1 host symlink case deselected**. The three cross-PR interface tests from temporary [PR #162](https://github.com/interzettel/prehnite/pull/162) were preserved in merged #161. After the source merges, [development `main` CI 39153867726](https://github.com/interzettel/prehnite/actions/runs/39153867726) passed **25/25 jobs**, independently checked. Private review-resolution report commit `a33f4bf`.
- Original accepted lamp Candidate A remains immutable. The new CPU algorithm
  did **not** reproduce identical bytes: hard silhouette IoU 1.0, but **6,749
  alpha pixels changed** and transparent/fringe RGB output differs. No
  transfer of its historical visual acceptance to the new derivative.
- The original independent source review's **five focused findings were
  addressed in PR #161 head `9949367`** and inspected: file SHA assertions
  separated from unverified runtime compatibility/execution, versioned PR #159
  resource observation with `startup_authorized:false`, true hole-component
  metrics, valid CLI runbook, and measured RGB expansion operation facts.
  The owner subsequently authorized source merges; the corrected contracts are now on development `main`. The earlier runner's `preflight` refused startup below its 6,000 MB RAM policy floor.
  **No new GPU inference, ComfyUI startup, downloads or packages** were used
  for review resolution.

Private reports:
`results/2026-10-18-productization-sprint-1.md` (SHA256
`918961c189104323b852c92cb22307f44a25a343a2209542ae3993b58b89420f`)
and `results/2026-10-18-productization-closeout.md` (SHA256
`5a9a4d3db711e5cf79490aff24ab123b1878df6ba3b1347c644c4ddf928f2c84`),
plus `results/2026-10-18-pr161-review-resolution.md` (SHA256
`77507c1048004e483be679d70084664aa03e10e3815ce83a1c789a2aaa6371a0`).
The private patch, source image, masks, GPU logs, local runtime config and
weights remain private.

**Integration housekeeping:** the three synthetic resource→QA interface tests were retained on `main`; temporary [PR #162](https://github.com/interzettel/prehnite/pull/162) was **closed without merging**. The dated documentation is tracked in [PR #160](https://github.com/interzettel/prehnite/pull/160). **Next:** plan a separately authorized, genuinely different live-object Engine→opt-in `cutout-qa` trial. No release/tag or inference authorization follows automatically.

## What explicitly remains open

- The **development source** now includes resource preflight, CPU cutout QA/acceptance and the integration regressions (#159/#161). The **released PyPI `0.1.0a1`** does not. The private local launcher, Transformers overlay and weights remain unbundled. Engine→QA remains opt-in/manual, with no second real-object certification ([roadmap](ROADMAP.md)).
- No general **4/6/8/12 GiB model tier**, multiple-machine reproducibility, 4K real image viability, uninterrupted long-batch behavior or cost/quality throughput distribution has been established.
- No independent alpha reference corpus, measured hair/glass/translucency/multi-instance benchmark, calibrated judge or robust single-object model comparison exists.
- No comprehensive model-rights certification, runtime-loaded dependency completeness, third-party weight redistribution approval, real paid API reconciliation or production release gate follows.
- The original **61-unit release ledger remains 42/61**, and the technical release matrix remains **4 verified / 7 partial / 5 unverified**. At the time of this lamp case study, the frozen 73-task atomic register was **14/73**. A **separate subsequent merged implementation [PR #164](https://github.com/interzettel/prehnite/pull/164)** fulfills the original S03-A03 CPU color-spill pixel-test criterion and changes the same canonical atomic register to **15/73**; **the lamp evidence alone never earned that credit**. These denominators retain their original independent acceptance conditions: no real multiple-category alpha benchmark, 8 GiB feasibility tier or production release has been certified.

## Next product milestone

1. **Source integration complete:** #159 and #161 merged into development `main`, with synthetic cross-interface tests preserved. CI passed 25/25 on `main`.
2. **Documentation closeout:** #160 describes the merged source accurately; temporary #162 should be closed without merging. The private lab reports and review history remain immutable.
3. **Next new evidence:** under separate operator authorization, verify the merged optional Engine→CPU QA workflow on a **different real object** with provenance-bound execution receipts and independent visual review.
4. **Later quality/release work:** gold-reference diverse masks, model and weight rights, long-running batch safety, reviewed owner journal promotion and representative hardware-tier measurements. One accepted lamp and passing synthetic CI do not complete these tasks.

See [delivery readiness](PROGRESS.md), [roadmap](ROADMAP.md), [61-unit tracker](progress/STATUS.md), [atomic task tracker](progress/ATOMIC.md), and [first-real-asset operator guide](FIRST_REAL_ASSET.md).
