# Prehnite — agent/session handover (2026-10-18, post-cutout update)

> **Current as of the documented local-lab acceptance on 2026-10-18.**
> This replaces the earlier same-date handover snapshot that incorrectly ended with **Gate 3 pending**. The original text is preserved in Git history. Always check newer reports and live GitHub before acting. **No new GPU inference, package install, model download, cloud call, public merge, or owner-signed journal promotion is authorized by this document.**

## 1. Where things stand

- **Public repository:** [interzettel/prehnite](https://github.com/interzettel/prehnite). Current public source is a development build, distinct from the released `0.1.0a1` PyPI package; check the live branch/revision.
- **Private operator-owned Windows lab:** `prehnite-local-lab`, with local reports, installed model files, private cutout images, prompt records and acceptance evidence. **Do not upload private image bytes, checkpoint files, paths or review images to public GitHub.**
- **Local lab last reported commit:** `b79a6cb`; source checkout in that lab was reported at public commit `5f70965`, behind the addition of this handover and later documentation. **Do not assume the local checkout reflects current upstream.**
- **First accepted cutout:** one desk lamp produced by local GroundingDINO+SAM2, CPU-refined, with Candidate A independently visually approved at the reviewed comparison scale. This is **not** general quality certification or an owner-signed Prehnite journal acceptance.
- **Full public evidence index:** [LOCAL_LAB_MILESTONE_2026-10-18.md](LOCAL_LAB_MILESTONE_2026-10-18.md).
- **Release counting:** original **42/61 (68.9%)** evidenced units, **2/7** milestone gates, frozen scoped atomic **14/73 (19.18%)**, unchanged because the remaining parent acceptance criteria exceed a single approved case study. See [release readiness](PROGRESS.md) and [roadmap](ROADMAP.md).
- **Outstanding draft upstream branch:** [PR #159](https://github.com/interzettel/prehnite/pull/159) on resource readiness; draft, unmerged. Do not claim its CLI exists on `main` or in the released alpha.

## 2. Immutable source, failure and successful candidate

| Item | Exact identifier / result |
| --- | --- |
| Original 768×1024 SDXL lamp source SHA256 | `282e6d4af8ab3a68cafef674ff33d8bd20001be3b4dfedfb216c853fca6832d3` |
| Original human review SHA256 | `97f66bcd94f2752894279576276facd5839d652cbdd605226834f67551c15dad` |
| Source-stage acceptance attestation SHA256 | `f1aa31d0014c640f9eddf8e235bcd6517e4b8e3f5a5084620ab2fa242c9666ec` |
| Original generation batch | `sdxl-1k-generation`: successful SDXL inference but original automated quality decision **rejected**; separate source approval only allowed next segmentation stage |
| First segmentation (Gate 3) | **Failed**; prompt `1f0c7c40-4b09-402d-997d-6ce46d4a5e66`; Transformers 5.20.1/legacy BERT helper incompatibility; no mask; failed batch remains unchanged |
| Later successful batch | `lamp-autonomous-20261018T1819` |
| Successful segmentation prompt | `ab4cb4d3-3b87-4cab-9ad9-666112f12236`; **one** submission, successful in **8.994 s**, no retry |
| Raw binary segmentation mask SHA256 | `d0e666267bc33ab046bd146576a1911b3a6c6e4072c159a5b68cab941ae07971` |
| Original RGBA cutout SHA256 | `454b27ed1b214c9adb50f8ffc4c15a73ce80bd89fea2513abfeaed68feecf968` |
| **Independently accepted Candidate A** | CPU-refined σ 0.65 px; SHA256 `5e925240e2c527a9922ffad2729fcb9111ed25251f3c2aedfba8c87903bd6450` |
| Private `ACCEPTANCE.md` | SHA256 `2c8721b1b03e225034ae3910c16c9fe87d30e96d6fcc0b1d6d63d181399acd08` |
| Private `approval.json` | SHA256 `109880d217b7bdca715e7be63975f5ac7218155960b937b4c0c9af8a9886988f` |

**Original review intent:** include lamp shade/body, neck/stem and base. Exclude power cord, tabletop, cast shadow, background. One component, zero holes, binary raw mask, ~16.44% canvas coverage. Candidate A preserved hard-silhouette IoU 1.0. Candidate B (σ 1.0) was retained but not selected. Visual assessment was based on submitted original/A/B overview and enlarged shade/stem/base comparisons, not a claim about all backgrounds or transparent materials.

**Approval scope:** independent visual review at the presented scale, **not** owner-authenticated journal approval. Do not change old batch status or call this pipeline release-ready.

## 3. What made it run locally

- Owner's RTX 4070 Laptop GPU, ~8 GiB-class VRAM; ComfyUI **0.41.0**, Python **3.12.9**, shared Torch **2.7.0+cu128**.
- Original active ComfyUI Python still has `transformers 5.20.1`, `huggingface_hub 2.2.0`, `tokenizers 0.23.3`. Do not downgrade it.
- A **private process-only import overlay** used `transformers 4.57.6`, `huggingface_hub 0.36.2`, `tokenizers 0.22.2`, backed by previously acquired local wheels. The live runtime resolved those packages from the private target.
- Pinned `neverbiasu/ComfyUI-SAM2` at `757034be78e877c07db8e7913f489089af224630`, GroundingDINO SwinT, SAM 2.1 base-plus, BERT base uncased, with operator-declared checked weight/config/tokenizer bytes. **Full runtime-resident model dependency attestation and third-party license clearance remain open** ([#156](https://github.com/interzettel/prehnite/issues/156)).
- ComfyUI node classes registered in a short-lived isolated service on `127.0.0.1:8189`; live six-node graph validated. **Server starts with private paths and must import Transformers only after ComfyUI has configured Torch/CUDA.** The early "90-second" watchdog failures were due to a missing sleep; an additional CUDA allocator assertion was traced to early Torch import. Both were repaired in the private scripts.
- Successful segmentation observed peak VRAM **2,533 MiB**, minimum available system RAM **3,338 MB**, maximum commit **57.6%**, peak GPU utilization **55%**. Model loading and inference were not separately timed; per-process private-byte peak absent. SDXL generation was ~46.04 s, sampled peak VRAM 7,763/8,188 MiB in a **separate stage**, not concurrently.
- No cloud requests, fees, new model downloads or package installs during the final autonomous cutout. Historical evidence and all attempts/markers remain immutable.

For exact filenames and private commands, consult **local** (not publicly copied) reports:
`results/2026-10-18-local-cutout-autonomous-session.md`,
`review/2026-10-18-local-cutout-alpha-refinement/README.md`,
`review/2026-10-18-local-cutout-alpha-refinement/ACCEPTANCE.md`,
and the preceding Gate 4B-N/O, Gate 4A and Gate 3 reports.

## 4. Current project position: real experiment vs public product

**Done as local lab evidence:** original source generation, compatibility diagnosis, synthetic wrapper parity, live node registration, one successful segmentation, raw mask/transparent PNG, CPU edge refinement, independent artifact-level visual acceptance and provenance records.

**Not yet implemented in the public installable workflow:** consolidated short-lived ComfyUI child launcher/overlay; reusable, configurable CPU alpha processing with RGB edge decontamination; product-level end-to-end acceptance-record flow, tested non-lamp fixtures, independent mask/alpha gold standards and unattended batch resource/process monitoring. The public package includes adjacent schema, journal, handoff and hardware-observation foundations, **but a private lab result is not automatically a merged public feature**.

**Not yet certified:** 8 GiB recipe feasibility across repeats, 4K generation, category-wide mask accuracy, hair/glass/translucency handling, 90-object real batch, cloud billing, legal permission for every model, operational multi-machine release readiness.

The reviewed-source handoff and model dependency manifest remain separate from original SDXL `rejected` journal status. Do not reclassify any private acceptance as an owner-signed Prehnite journal event.

## 5. Next work — productize, don't redo the lamp

1. Read current public [README](../README.md), [ROADMAP](ROADMAP.md), [PROGRESS](PROGRESS.md), [reviewed handoff](REVIEWED_SOURCE_HANDOFF.md) and [model/recipe contracts](RECIPE_EXECUTION.md), and the **local** runner scripts/reports.
2. Refactor the demonstrated private launcher/overlay/supervision as an **optional** testable integration, not a mandatory ComfyUI install or a new job engine. Offline synthetic tests first; preserve exact Torch initialization order.
3. Make alpha refinement a **parameterized optional step**, with conservative silhouette/halo/color checks. σ 0.65 px is the accepted **lamp** candidate only; don't hardcode it globally.
4. Keep **[PR #159](https://github.com/interzettel/prehnite/pull/159)** draft and separate from this case-study documentation; validate Windows real telemetry, CI and tests before merge.
5. Improve execution receipts to distinguish **resource readiness → compatibility → technical execution → mask/alpha checks → independent visual review → owner-signed final acceptance**. A CLI zero-exit after an asset failure must not be reported as production success.
6. Propose a diverse-object pilot (hair, glass, multi-instance, dark-on-dark, occlusions) **only after separate authorization**, proper rights and review rubric. No background GPU reruns, no model downloads or hosted tests authorized by this handover.

**Operational safety:** No implicit inference retries; stop after a failed authorized cutout, never replay the rejected Gate 3 batch, do not silently clear startup attempt markers, avoid sharing original model images publicly, and respect original `uncertain: reject` policy. No new GitHub release tag/merge without review.

**Latest task ownership:** the next local Codex assignment is a **bounded productization sprint** (offline engineering and mock tests, not another lamp/GPU run). Reconcile the local lab README and current public source, then report real changes, hashes and tests.
