# Prehnite — 8 GB laptop-first image workbench strategy (proposal)

**Date:** 2026-10-19  
**Status:** proposed for owner review, not yet an approved change to release scope or progress accounting  
**Planning home:** [architecture epic #132](https://github.com/interzettel/prehnite/issues/132) · [proposed product milestones](PRODUCT_MILESTONES.md) · [v2 register](../progress/product_milestones.v2.proposed.json)  
**Other current work:** [local P08-A03 PR #181](https://github.com/interzettel/prehnite/pull/181), [soft alpha PR #182](https://github.com/interzettel/prehnite/pull/182)

## The product decision

Prehnite is an **installable, local-first image-generation and experimentation workbench optimized first for an 8 GiB laptop GPU and the system RAM it actually has available**. It helps people produce useful images and controlled variations on hardware they already own, while preserving reproducibility and using optional bigger machines or paid APIs without having to reinvent the workflow.

Batching is important, but this is **not** an AI video factory, YouTube automation tool, Higgsfield clone, general-purpose graph editor, or bespoke foundation-model training suite.

The primary unmet job is: **“I have an 8 GB laptop GPU, sometimes limited free system RAM, and models/LoRAs I want to try. Help me use this machine efficiently, run it safely, compare actual configurations, recover failures, and get consistent, usable images without requiring cloud accounts.”**

The owner's actual 8 GiB RTX 4070 laptop is the design center, not an unfortunate compatibility exception. **There is no planned 4 GiB or 6 GiB optimization, support certification or hardware procurement campaign.** A stronger GPU should run compatible versions of the *same* workflow faster and allow bigger models when verified; an API is an optional backend, never a prerequisite.

### Two phases, and no automatic third phase

1. **Phase 1 — practical low-memory image engine.** Configuration-aware model execution, profiling, conservative scheduling, reliable batches, quality-aware selection and transparent outputs on modest machines.
2. **Phase 2 — repeatable creative experiments.** Local LoRA/styling, reference-conditioned edits and controllable subject consistency, including private appearance variations on a user's own images.

Do **not** add a third “media pipeline”, audio/TTS, editing timeline, video publisher, social distribution suite or hosted UI phase by default. Separate future discussion may reconsider scope, but none is authorized by this strategy.

## Users and jobs to be done

- **8 GiB laptop experimenter:** uses the owner's RTX 4070-class 8 GiB GPU and constrained host RAM; wants to know whether an exact pinned local model/workflow can run, what measured trade-offs apply and why a job refuses. No unsupported model/hardware promises.
- **Batch experimenter:** varies prompts, seeds, samplers, LoRAs, resolutions or backends; wants organized comparison, provenance, repeatable outputs and time/energy/memory measurements, not a spreadsheet of forgotten image files.
- **Creative practitioner:** wants 10–50 “good enough” images at consistent style and known elapsed time, with retries/repair bounded to avoid wasting scarce local compute; cost per **human-accepted image**, not just raw throughput.
- **Private self-image experimenter:** opts into local reference photos and controlled hairstyle, beard, hair-color, clothing and appearance variations; original photos stay local by default, and outputs are **visual simulations**, not predictions of physical outcomes. Subject identity and appearance consistency require human evaluation.
- **Portable power user:** can install the same Python package on a large machine or explicitly enable a hosted image endpoint; batch semantics and receipt format remain compatible, model feasibility and quality are remeasured for the new environment.

## Competitive / integration research (original sources, checked 2026-10-19)

| Existing system | What already exists | Prehnite's honest role | Boundary |
| --- | --- | --- | --- |
| [ComfyUI](https://docs.comfy.org/development/comfyui-server/comms_routes) | Local node graphs; native HTTP/WebSocket workflow, queue and history APIs; [dynamic VRAM/startup controls](https://docs.comfy.org/development/comfyui-server/startup-flags) | **First-class local runtime adapter**, reuse existing API graph contracts; profile/replay/error isolation and user-level batch decisions | Never rebuild its node editor or fork all custom nodes. Flags depend on active ComfyUI memory manager and model. |
| [InvokeAI low-VRAM mode](https://invoke.ai/configuration/low-vram-mode/) | Partial model loading, VRAM working-memory reserve, RAM-copy and cache management | **Benchmark/reference competitor**; compare measured outcomes or add an adapter if users demand it | Do not claim Prehnite invented partial loading; do not scrape private internals. |
| [Hugging Face Diffusers memory guidance](https://huggingface.co/docs/diffusers/optimization/memory) | Model/sequential/group CPU offload, VAE slicing/tiling and device placement; [quantization + offload](https://huggingface.co/docs/diffusers/optimization/speed-memory-optims) | Optional later **direct runtime** or reference for supported backend optimization profiles, not mandatory in Phase 1 | Offloading can trade huge latency/host-RAM costs for smaller VRAM; not universally compatible. |
| [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) | Alternative C/C++ runtimes/backends and model-specific quantization paths | Optional measured low-overhead candidate, especially if PyTorch/ComfyUI overhead dominates a tested tier | Verify quality, model/operator coverage, package/OS licensing, memory and LoRA behavior independently; no universal superiority claim. |
| [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) | Experimental quantized loading for supported transformer models | Opt-in **external plugin** candidate for comparative experiments | Third-party custom node, compatibility/security/license review first; no surprise auto-install. |
| [Diffusers LoRA adapters](https://huggingface.co/docs/diffusers/main/using-diffusers/loading_adapters) | LoRA loading/unloading, stacking/scales and hot-swapping | Reuse runtime-native LoRA support; pin base model, adapter hash/order/scale and record memory/switching effects | Never silently download adapters or train identity LoRAs on private photos. |
| [Higgsfield official API](https://docs.higgsfield.ai/docs) | Authenticated asynchronous image/video model calls, queue status and cancellation; [API contract](https://docs.higgsfield.ai/docs/api-reference/overview) | **Optional hosted image-provider adapter only**, under existing provider, privacy, idempotency and budget policies | Not needed for local use; no implicit upload; no video requirement, no subscription dependency, no spent credits in CI. |

These references establish *capabilities available to investigate*, not measured superior performance or endorsement. Every concrete hardware/model combination needs real observed results. The ComfyUI [server API overview](https://docs.comfy.org/development/comfyui-server/comms_overview) allows orchestration without duplicating its user interface; Higgsfield's [September 2026 API launch](https://higgsfield.ai/blog/higgsfield-api) confirms a developer integration exists, not that Prehnite supports it today.

## System boundary: reuse inference engines, optimize the operator experience

- **Prehnite owns:** hardware/resource preflight, policy-aware recipe selection; immutable model+LoRA+graph hash binding; batch intent, seeds, run IDs, cancel/resume, output integrity; conservative scheduling and model-residency decisions *when backend capabilities expose them*; human/aesthetic quality review; error diagnosis and per-accepted-image benchmark receipts; reproducible reports/archives.
- **Runtimes own:** model kernels, torch/CUDA graph execution, attention implementations, quantizers, graph-editor UX, runtime-specific offload mechanics and third-party plugins.
- **Optional providers own:** paid inference and their endpoint-specific terms; Prehnite records capability, advertised price, authorization, remote request ID, eventual billing and upload scope, but does not silently retry ambiguous submissions.
- **The user owns:** models and rights receipts, consent to installs/uploads, performance/quality thresholds for each job, acceptance decisions and private image files.

A packaging goal, **not a present claim**: Python users can install Prehnite, inspect the machine, choose an already-installed runtime, load an owned rights-cleared model/LoRA and run a reproducible job with few commands. The installer must not imply that ComfyUI, model weights or proprietary nodes are bundled.

## Phase 1 — low-memory image engine

### P1.0 — reconcile existing work, not another infrastructure detour

Finish independent CI/reviews for #181 and #182 without automatic atomic credit; leave the 8 GiB hardware benchmark blocked until freshly authorized. Preserve 43/61 release and 21/73 frozen atomic numbers on the proposal branch. Existing P08-A03 preflight available RAM >= 6,000 MiB and free VRAM >= 5,000 MiB are **that specific proposed experiment's fixed stop conditions**; do not relax them for convenience or present them as universal product minimums.

### P1.1 — characterize the actual 8 GiB laptop and constrained host RAM, *without fake compatibility*

Extend [#134](https://github.com/interzettel/prehnite/issues/134): implement an offline read-only **eligibility/estimated footprint report** with clear “unknown” and “untested” states; require owner-authorized opt-in real runs for benchmark receipts. Explicitly measure host RAM free/available, commit/pagefile/disk pressure, driver/runtime versions, occupied VRAM and model/LoRA weights separately. Our first lab showed host RAM pressure can block a session even with nominal 8 GiB VRAM.

Use at least two lawful, pinned model families as candidates *only after verified weights/terms*; use SDXL as a known local starting comparison, plus a smaller or quantized model whose real availability and outputs have been verified. Measure the default installed ComfyUI configuration **as baseline** before changing any flags. Then test one factor at a time where supported:

1. Runtime-native model CPU offloading/model unload or dynamic-VRAM policy.
2. Supported quantized weights/encoders with pinned independent model licenses.
3. Reduced latent resolution / staged generation / VAE tiling with quality-aware output flags.
4. Attention backend changes, model/component residency and memory release.
5. One-item sequential batching vs compatible warm-model group batching.
6. Alternative runtime only if expected performance warrants an integration experiment.

Never assume an optimization is faster or produces equivalent quality. If memory savings consume huge amounts of system RAM or wall time, classify them as trade-offs or refusals. Explicitly distinguish *GPU working space*, model residency, PyTorch reservations, OS GPU telemetry, host commit and disk offload. Benchmark only the actual 8 GiB laptop unless another platform is later explicitly requested; do not create smaller-GPU experiments to satisfy a marketing matrix.

### P1.2 — make measured optimizations user-selectable and explainable

Extend [#136](https://github.com/interzettel/prehnite/issues/136) with a small set of explicit profiles (e.g. conservative-memory, balanced, throughput), only when supported by the chosen backend and backed by measurements on a pinned recipe. Expose “why this profile was selected”, actual resource margins and failure classification. Prefer one loaded model at a time where host RAM pressure is severe; model caching and concurrent requests are not automatically faster. Do not unilaterally alter third-party runtime startup flags, graphics drivers, user caches or model paths.

No hidden OOM retry. Safe stops and separate new authorized attempt budgets must remain distinct. Reproducible identity includes runtime mode and exact LoRA state.

### P1.3 — useful batch jobs, not perfect pictures

A batch manifest should describe image goals and accepted quality level: requested number, output size, aspect, style/subject conditions, seed range, model/LoRA set, candidate limit, compute/time budget and explicit optional provider constraints. The engine should produce inspectable candidates, permit manual accept/reject, and optionally compute deterministic quality checks. **“Good enough” is set by the user**, not by a fabricated default AI score.

First proof: a **ten-image, local-only real batch** on a separately authorized, reproducible 8 GiB setup. Include distinct prompts/subjects, output hashes, reproducible configs, all failure/retry outcomes, wall time, model loads, sampled peak VRAM/RAM/commit, and human accepted fraction. Do not use synthetic demo images to claim AI batch quality. Scale to 30 or 90 only if the small pilot proves the work is useful; the original 90-image release gate and its separate billing requirements remain.

### Phase 1 proposed exit criteria (not currently met)

- Installer/doctor identifies actual configuration and clearly refuses unknown/unsafe profiles.
- One independently reviewed real GPU profile can generate an accepted, repeatable 10-image batch from a pinned lawful model, within its **declared** resource/time budget.
- Outcomes include accepted/total images, latency (cold and warm), memory telemetry, output/recipe integrity, failures and honest uncertainty; another operator can repeat the exact instructions.
- Tested 8 GiB compatibility applies **only to individually measured model+version+resolution+backend combinations**. Other VRAM tiers remain **untested/out of scope**, with no promise or plan to certify them.
- Optional provider use remains zero by default. No required cloud account or model-weight bundle.
- Demonstrate measurable added value over a **ComfyUI-only baseline on the same hardware and fixed workload**: e.g. fewer manual steps or better reproducible resume/selection. Do not claim speedups that actually arise from changing model/quality settings.

## Phase 2 — local LoRA and controlled visual consistency

- **Versioned adapter recipes:** base checkpoint and each LoRA's file hash, compatibility family, source/rights receipt, insertion order, weight/scale, activation schedule and intended prompts. Explicitly record unload/swap decisions and effects on host RAM/VRAM/latency.
- **Experiment grids:** controlled variations across seeds, prompts, LoRA strengths, samplers and image-to-image strengths with comparable contact sheets and batch receipts; ability to pin all settings except the dimension being studied.
- **Subject/identity consistency:** local-only opt-in reference conditioning using backend-supported methods; measure subjective identity retention and requested-attribute adherence separately from pixel fidelity. Do not pretend a generic LoRA alone preserves face identity under every pose/edit.
- **Personal appearance sandbox:** self-owned images may be used for hairstyle/beard/hair color, clothing or imagined body-shape variations. Keep source images local and excluded from telemetry/shared diagnostics by default. Use user review and label results as speculative visualizations, not guaranteed real appearances. No implicit face datasets, hosted training or uploads.
- **Creative batch reuse:** save a successful style/subject recipe and regenerate controlled variations across 10–50 images; compare variability and accepted yield under memory budgets.
- **Optional API images:** only after opt-in provider-specific contract verification and explicit owner consent to upload a particular private image. Higgsfield is one possible provider; fal and others remain optional. Costs and privacy are visible before submission, and idempotency/recovery is tested without real spending in CI.

### Phase 2 proposed exit criteria (not currently met)

- A user can reliably run a LoRA/style experiment on one locally verified low-memory configuration without undocumented manual graph edits.
- A small human-reviewed multi-seed comparison includes memory/load-switching costs, quality consistency and repeatability evidence; failures remain in the report.
- A locally controlled appearance study accepts user-owned references, records consent and leaves images local by default.
- The same saved experiment can be migrated to a different supported GPU or expressly approved API without silently rewriting source/LoRA/quality settings. Unsupported transfer is clearly refused.

## Measurement design and fair baseline protocol

**Benchmark the entire process rather than reporting an isolated denoiser time.** Pin GPU/driver/OS, available system RAM, model files, LoRA files, graph and runtime commits, seeds, steps, resolution, safety/quality settings and output format.

| Measure | How to report and interpret |
| --- | --- |
| Cold and warm time | Separate startup/model load from repeated end-to-end image delivery; record p50/p95 only with meaningful sample sizes. |
| GPU memory | Report allocated/reserved where available and sampled device peak, plus pre-run free VRAM and monitoring interval. Sampled peak is **not absolute peak**. |
| Host RAM / commit | Available/minimum RAM, process peak RSS, system commit/pagefile and OS pressure; disk offload footprint and SSD traffic if used. |
| Quality | Human-rated acceptance fraction and, where meaningful, blinded side-by-side fidelity/identity/style ratings; no quality equivalence claim from matching filenames or dimensions. |
| Efficiency | Images accepted per hour; seconds per accepted image; model-load count; total energy only when directly measured; API cost only when billed. |
| Robustness | OOM/timeout/refusal counts, recovery integrity, failures that require manual restart, reproduction on same and changed machine. |
| Fair comparator | Same licensed weights, graph semantics, steps, seeds, resolution and quality evaluation on vanilla ComfyUI first. Additional InvokeAI/Diffusers/sd.cpp comparison only if implementation supports comparable models/settings. |

Benchmark receipts should be machine-readable, content-addressed and distinguish **simulated**, **operator-observed**, **independently checked**, **human-accepted** and **unverified** evidence. Run-size and resource budgets must be explicit and approved before each real test. A saved profile is not a blanket future execution authorization.

## Work order: what to prioritize and what to postpone

**Immediate / next reviews:** independently close #181 and #182 review outcomes as appropriate; publish this strategy as a proposal; obtain an explicit decision about priorities. No GPU starts or release credit from a planning PR.

**Next engineering slices (create/reuse narrowly scoped tickets, do not expand the frozen 73 tasks):**

1. #134 — measured compatibility and a baseline benchmark receipt for the **actual 8 GiB RTX 4070 laptop**, including the separate host-RAM bottleneck. No 4/6 GiB test matrix.
2. #136 — one bounded backend-aware memory option, benchmark against ComfyUI default using same model and image conditions.
3. #135 — safe rights-acknowledged local model and LoRA import, no silent download; constrained system RAM/disk handling.
4. #132 — smallest reproducible generation → inspection/selection → export workflow in public code with independently reviewed real evidence.
5. Phase 2 continuation under #132 — LoRA provenance, experiment matrix and local-only subject-reference/appearance study.

**Deprioritize until user demand or measured need:** native inference kernels, a node-graph editor, heavy UI, universal model support, hosted model training, automatic private-data sync, video/TTS/editor/publishing, cosmetic “AI judge” scores without human calibration, unmeasured 4K claims, broadly rewritten model recipes, new abstract orchestration frameworks. Keep existing quality/cutout and release obligations; prioritizing core hardware usefulness **does not erase** 18 open parent units.

## Decision risks

- **8 GiB of VRAM does not imply abundant available host RAM.** CPU offload can make system commit worse on the actual laptop; measure free RAM and refuse configurations that would thrash rather than claiming a VRAM-only optimization worked.
- **Memory-optimized image quality may differ.** Quantization, image size, model/LoRA swaps and tiled decoding can alter results; measure acceptance relative to a fixed baseline.
- **A model catalog is not a rights grant.** SDXL, FLUX, LoRAs, third-party custom nodes and API outputs have separate current licensing and commercial-use conditions. Never redistribute weights as MIT package assets.
- **The API boundary is real.** Higgsfield provides a paid developer API today, but no provider is integrated or authorized by writing this document; private photos must never leak from a local job through fallback.
- **Overengineering is a delivery risk.** Don't create another 1000-line abstract controller before measuring a 10-image real workload.
- **Frozen completion accounting survives reprioritization.** 43/61, 21/73 and original parent acceptance definitions remain unchanged until an explicitly reviewed migration.

## Approval questions for the owner

1. Is the north-star **“usable images and reproducible creative experiments on modest GPUs”** approved?
2. Is Phase 2 explicitly **LoRA / controlled variations / private appearance experiments**, and is media/video automation out of scope?
3. Use **only the existing 8 GiB laptop** for near-term hardware benchmarks, with explicit host-RAM measurements and no campaign to source/test smaller GPUs? (The owner's direction is **yes**.)
4. Keep ComfyUI as the first runtime and treat InvokeAI, Diffusers and sd.cpp as baselines/optional future adapters; Higgsfield only as an opt-in paid image endpoint?

**No approval is implied by this document, and no runtime or hardware test is authorized.**
