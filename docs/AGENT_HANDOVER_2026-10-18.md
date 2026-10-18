# Prehnite — agent/session handover (2026-10-18, post-cutout update)

> **Current as of the documented local-lab acceptance on 2026-10-18.**
> This replaces the earlier same-date handover snapshot that incorrectly ended with **Gate 3 pending**. The original text is preserved in Git history. Always check newer reports and live GitHub before acting. **No new GPU inference, package install, model download, cloud call, public merge, or owner-signed journal promotion is authorized by this document.**

## 1. Where things stand

- **Public repository:** [interzettel/prehnite](https://github.com/interzettel/prehnite). Current public source is a development build, distinct from the released `0.1.0a1` PyPI package; check the live branch/revision.
- **Private operator-owned Windows lab:** `prehnite-local-lab`, with local reports, installed model files, private cutout images, prompt records and acceptance evidence. **Do not upload private image bytes, checkpoint files, paths or review images to public GitHub.**
- **Local lab last reported commit:** `da7b478` (Productization Sprint 1). Public source was rebased locally to `848edaf`; local-only branch `feature/local-cutout-productization` at `f416aa4d2a7770575b0388cdc566fa307ebbd8c7` is **one commit ahead, unpushed and unmerged**. The previous accepted-artifact evidence remains at lab commit `b79a6cb`. **Do not assume any local changes are available on public GitHub.**
- **First accepted cutout:** one desk lamp produced by local GroundingDINO+SAM2, CPU-refined, with Candidate A independently visually approved at the reviewed comparison scale. This is **not** general quality certification or an owner-signed Prehnite journal acceptance.
- **Full public evidence index:** [LOCAL_LAB_MILESTONE_2026-10-18.md](LOCAL_LAB_MILESTONE_2026-10-18.md).
- **Release counting:** original **42/61 (68.9%)** evidenced units, **2/7** milestone gates, frozen scoped atomic **14/73 (19.18%)**, unchanged because the remaining parent acceptance criteria exceed a single approved case study. See [release readiness](PROGRESS.md) and [roadmap](ROADMAP.md).
- **Outstanding draft public PRs:** [#159](https://github.com/interzettel/prehnite/pull/159) resource readiness and [#160](https://github.com/interzettel/prehnite/pull/160) dated documentation catch-up; both draft, unmerged. Local code productization branch has **not been pushed or PR'd**. Do not claim its new CLI exists on `main` or in the released alpha.

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

**Implemented in Productization Sprint 1, but still ONLY in the local/unpushed branch:**
- Reusable `src/prehnite/cutout_quality.py` with hash-bound source/target/workflow/model recipe, 1–4 explicit sigma candidates (no universal default), nearest-opaque RGB decontamination, technical QA, seven separate stage statuses, create-only review records.
- Additive `prehnite cutout-qa` and `prehnite cutout-accept` CLI, `tests/test_cutout_quality.py` (12 CPU tests), `docs/LOCAL_CUTOUT_PIPELINE.md` and an unreleased changelog entry.
- Private consolidated `scripts/prehnite_local_runtime.py` entry point (`preflight`, `check`, `start`, `status`, `stop`). The existing Engine remains the job lifecycle owner; the new QA is **not yet wired automatically into Engine**.
- Local tests reported: 12 new tests pass; full suite 863 pass/15 skip/1 Windows symlink-privilege failure; compileall and new-module Ruff pass. One local `preflight` refused to start at 4,454.7 MB available (<6,000 MB floor), while separate overlay `check` passed. **No new ComfyUI server, checkpoint inference or `/prompt`** was executed in the sprint.
- Productization report `results/2026-10-18-productization-sprint-1.md` SHA256 `918961c189104323b852c92cb22307f44a25a343a2209542ae3993b58b89420f`; private patch SHA256 `ca991fcc79af26a71a045dd0214e1aea1a896ea60ec249fac4be3338c5beb40c`.

**Still NOT present in the public installable package:** that unpushed reusable cutout QA patch, consolidated private runtime, compatibility overlay, model files or validated next-object cutout; independent gold-mask cohorts and unattended batch resource/process safeguards remain incomplete. The successful lamp's historically approved PNG has **not** been shown byte-identical to the new public-module candidate algorithm; do not claim such parity without an explicit offline reproduction check.

**Not yet certified:** 8 GiB recipe feasibility across repeats, 4K generation, category-wide mask accuracy, hair/glass/translucency handling, 90-object real batch, cloud billing, legal permission for every model, operational multi-machine release readiness.

The reviewed-source handoff and model dependency manifest remain separate from original SDXL `rejected` journal status. Do not reclassify any private acceptance as an owner-signed Prehnite journal event.

## 5. Next work — reconcile and review the finished local code, don't redo the lamp

1. **Update private lab `README.md`, `docs/LOCAL_RUNTIME.md` (if needed), current status/handover and developer entry points** to reference the already completed Sprint 1, accepted artifact, source feature branch at `f416aa4`, private lab commit `da7b478`, actual tests and the public status documentation [PR #160](https://github.com/interzettel/prehnite/pull/160). Do not leave stale "productization not started" statements.
2. Inspect the full local feature diff and run secret/private-image/absolute-path/binary scans **before pushing**. Confirm `feature/local-cutout-productization` is on upstream `848edaf`, verify the public repo working tree/HEAD, then publish **only the sanitized source changes as a distinct draft PR**. Do not merge, force-push unrelated branches, commit private runtime config or weights, or overwrite [PR #159](https://github.com/interzettel/prehnite/pull/159)/[#160](https://github.com/interzettel/prehnite/pull/160).
3. Review new CLI source, alpha-candidate semantics, candidate hash integrity and create-only independent visual acceptance. Reproduce existing accepted lamp **only by offline CPU processing** if its original bytes are available, while preserving and independently validating its immutable `5e9252…` accepted hash; do not assert byte-for-byte match to the new module unless measured.
4. Explicitly track the existing full-suite Windows symlink privilege limitation, CI results from the public draft PR when available, and any tests that cannot run. A host privilege test failure must neither be ignored nor misrepresented as an application failure.
5. Leave [draft PR #159](https://github.com/interzettel/prehnite/pull/159) observation-only; avoid adding another sampler/scheduler into the cutout PR. Keep `cutout-qa` opt-in rather than silently changing the reviewed-source Engine or journals.
6. **Next material product milestone:** review/public integration and a separately authorized, next-object live Engine → cutout-qa trial with human review. No new GPU inference, package installs, downloads or `/prompt` are authorized merely because Sprint 1's tests passed.

**Operational safety:** No implicit inference retries; stop after a failed authorized cutout, never replay the rejected Gate 3 batch, do not silently clear startup attempt markers, avoid sharing original model images publicly, and respect original `uncertain: reject` policy. No public PR merge or release tag without review.

**Latest task ownership:** local Codex owns private README/status reconciliation, private source safety review, and preparing a **separate draft productization PR**; ChatGPT is updating public evidence docs via [PR #160](https://github.com/interzettel/prehnite/pull/160). Both must track actual branch/PR state without claiming unmerged functionality on `main`.
