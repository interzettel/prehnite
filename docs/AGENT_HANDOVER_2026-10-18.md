# Prehnite — agent/session handover (2026-10-18, source integration complete)

> **Updated after owner-authorized source merges of PRs #159 and #161.**
> This replaces the earlier same-date handover snapshot that incorrectly ended with **Gate 3 pending**. The original text is preserved in Git history. Always check newer reports and live GitHub before acting. **No new GPU inference, package install, model download, cloud call, public merge, or owner-signed journal promotion is authorized by this document.**

## 1. Where things stand

- **Public repository:** [interzettel/prehnite](https://github.com/interzettel/prehnite). Current public source is a development build, distinct from the released `0.1.0a1` PyPI package; check the live branch/revision.
- **Private operator-owned Windows lab:** `prehnite-local-lab`, with local reports, installed model files, private cutout images, prompt records and acceptance evidence. **Do not upload private image bytes, checkpoint files, paths or review images to public GitHub.**
- **Private lab last reported commit:** `3a08740` (temporary integration preparation), following review resolution `a33f4bf` and closeout `896fdea`. Local hardware/evidence stays private; do not assume the lab's public checkout is synchronized with current `main`. The accepted-artifact evidence remains at lab commit `b79a6cb`.
- **Merged development source:** [PR #159](https://github.com/interzettel/prehnite/pull/159) squash commit `ef54488` (resource observation), followed by [PR #161](https://github.com/interzettel/prehnite/pull/161) squash commit `ca78b8b` (opt-in cutout QA and acceptance, plus #162's synthetic pass/blocked/unknown interface tests). Post-merge `main` CI run `39153867726` passed **25/25 jobs**. **No new PyPI release was published.**
- **First accepted cutout:** one desk lamp produced by local GroundingDINO+SAM2, CPU-refined, with Candidate A independently visually approved at the reviewed comparison scale. This is **not** general quality certification or an owner-signed Prehnite journal acceptance.
- **Full public evidence index:** [LOCAL_LAB_MILESTONE_2026-10-18.md](LOCAL_LAB_MILESTONE_2026-10-18.md).
- **Original tracker progress:** release **42/61 (68.9%)**, **2/7** milestone gates. The frozen atomic register advanced from **14/73 to 15/73** through [S03-A03](https://github.com/interzettel/prehnite/pull/164)'s pixel-level criterion, and subsequently to **16/73** through the merged [S04-A02](https://github.com/interzettel/prehnite/pull/167) identity contract, and then to **17/73 (23.29%)** through the independently reviewed [P08-A01](https://github.com/interzettel/prehnite/pull/166) environment and model-rights record. Neither increment is credit for the single lamp, full multi-instance selection/export, or remaining S03 difficult-material acceptance. See [reconciliation of all 73 tasks](progress/RETROSPECTIVE_2026-10-18.md).
- **Documentation:** [PR #160](https://github.com/interzettel/prehnite/pull/160) contains this dated evidence/status update and is being merged **after** #159/#161. [Temporary integration PR #162](https://github.com/interzettel/prehnite/pull/162) demonstrated the combined branch and its test was preserved in #161; **#162 was closed unmerged**. Development `main` now contains `resource-preflight`, `cutout-qa`, and `cutout-accept`; released PyPI `0.1.0a1` does not.

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

## 4. Current project position — accepted artifact versus merged product source

**Local experimental result:** one owner-authorized real native-1K SDXL lamp generated, then segmented with GroundingDINO/SAM2; Candidate A's historical CPU alpha refinement was **independently visually accepted at the reviewed scale**. Original prompt/error history and rejected generation journal remain unchanged. No other real object has been demonstrated. The accepted lamp SHA256 is `5e925240e2c527a9922ffad2729fcb9111ed25251f3c2aedfba8c87903bd6450`.

**Merged into development `main`:** resource-readiness snapshots and fail-closed CLI (#159), reusable hash-bound source/target/model/workflow **file integrity** checks, optional CPU alpha candidates and mask topology QA, non-overwriting `cutout-qa` reports, explicit evidence-bound `cutout-accept` records, seven separate stage states and read-only resource observation integration (#161). The original five independent source-review fixes are merged, including honest `unverified` dependency compatibility and technical execution in the absence of a bound runtime receipt. The three synthetic pass/blocked/unknown interface tests from temporary PR #162 are included in `tests/test_resource_cutout_integration.py` on `main`.

**Not merged/not yet verified:** the private `scripts/prehnite_local_runtime.py` launcher and Transformers import overlay remain local to the operator, as do installed checkpoints and image assets. There is **no automatic Engine→QA orchestration**, owner-signed final journal approval, independently bound real-model execution receipt for the public QA module or diverse-object benchmark. The historical approved Candidate A bytes do **not** match the new module's offline result; hard-silhouette IoU was 1.0, but 6,749 alpha pixels differed. No historical acceptance was reassigned.

**Checks:** PR #159 and #161 each had successful CI; after the authorized merges, development `main` CI run [39153867726](https://github.com/interzettel/prehnite/actions/runs/39153867726) passed **25/25**. The private integration session reported **890 host CPU tests passed, 15 skipped, one Windows symlink test deselected**, and GitHub CI for the temporary integration branch passed 25/25. The operator's symlink privilege error `WinError 1314` and existing Ruff debt remain documented; green CI does not establish live model accuracy, rights clearance, hardware-tier certification or unattended batching.

## 5. Next real milestone — a distinct object through the merged code

1. **Already complete:** the owner's source merge authorization, #159→#161 integration, retention of the #162 synthetic interface tests, and passing post-merge `main` CI. Do not redo these steps or re-run the lamp.
2. **Documentation delivery:** this dated #160 record documents the now-merged source. Temporary #162 is already **closed unmerged** with its integration test preserved. No release or tag.
3. **Local agent:** fast-forward/reconcile its private public checkout with current `main` while preserving private artifacts and script environment. Update the private lab handover only if the changed public-state links require it; avoid repeating the completed productization sprint.
4. **Next-object pilot (separate explicit authorization required):** choose a distinct, reviewed, rights-permitted source and one target; run an operator-configured resource preflight and one bounded local Engine segmentation, then the merged opt-in `cutout-qa` step, human review and create-only evidence-bound acceptance. Record batch/prompt/source/model/mask/output receipts and actual resource telemetry; no automatic retries or implicit inference authorization.
5. Only after that real trial assess opt-in Engine→QA automation, multi-object quality benchmark, rights and hardware-tier evidence. **One accepted lamp is not production readiness.**

**Operational safety:** No implicit inference retries; stop after a failed authorized cutout, never replay the rejected Gate 3 batch, do not silently clear startup attempt markers, avoid sharing original model images publicly, and respect original `uncertain: reject` policy. No additional public PR merge or release tag without authorization.

**Latest state:** #159 and #161 are merged to development main, #160 is the dated documentation change, and #162 is closed unmerged. The new local cutout commands are public **source** functionality, not a new PyPI release or live-validated multi-object workflow.
