<div align="center">

<img src="assets/prehnite-riso-green-coral.png" alt="Prehnite : forest-green and coral Risograph artwork on warm paper" width="680" style="border-radius: 16px; clip-path: inset(0 round 16px);" />

### Make the images. Keep the experiments.

<sub>Prehnite's terminal greeting and the owner-selected laptop artwork are prepared as an animated GIF; see [the CLI animation production guide](docs/CLI_HERO.md). The published README continues using the canonical Riso bitmap until the selected GIF asset is committed.</sub>

**A local-first Python workbench for image generation, controlled variation, quality checks, and repeatable batches.**

Designed around a real **8 GB laptop GPU**, not a requirement to own a workstation.

[![CI](https://github.com/interzettel/prehnite/actions/workflows/ci.yml/badge.svg)](https://github.com/interzettel/prehnite/actions/workflows/ci.yml)
[![MIT](https://img.shields.io/badge/license-MIT-075231)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-53675a)](pyproject.toml)

[Quick start](#try-prehnite-without-a-gpu) · [Real local models](#using-your-own-models) · [What's working](#what-actually-works-today) · [Roadmap](#one-product-roadmap) · [Development](#project-and-development-links)

</div>

---

## At a glance

![How Prehnite connects inputs, the runtime and human review](assets/diagrams/workflow.svg)

The diagram shows responsibilities, not a claim that every runtime and visual-quality pathway is production-ready.

## Why Prehnite?

Having an 8 GB graphics card should not mean that experimenting with image models is a luxury. But getting something useful out of local inference involves more than clicking Generate: managing memory pressure, changing models, keeping the right settings, resuming an interrupted batch, comparing results, and figuring out which image is worth keeping.

**Prehnite is the operator around existing image runtimes.** It aims to make those jobs reproducible, inspectable and less wasteful:on the hardware you already have.

This is *not* an attempt to build another diffusion model, replace ComfyUI's node editor, or create a Higgsfield-style media publishing suite. Prehnite uses existing model ecosystems where they do the job well and adds the parts needed for **reliable experimentation and useful output**.

| If you want to… | Prehnite's role | Status |
| --- | --- | --- |
| Produce a batch, keep the right images and preserve their settings | Manifest, journal, selection/reporting and checked exports | **Offline engine implemented**; end-to-end real-model batch unverified |
| Run a model on an 8 GB laptop | Inspect resources, bind an existing ComfyUI workflow and report failures | **Experimental integration**; one private local-lab success, no general hardware certification |
| Test whether offloading or another option genuinely helps | Measure VRAM **and host RAM**, latency, failures, output quality, accepted-image yield | **Planned experimental milestone** |
| Reuse local LoRAs and compare controlled variations | Pin model/adapter hashes, seeds, strengths and visual experiment grids | **Phase 2 goal; not a finished capability** |
| Try hairstyles, beards or other appearance variations privately | Local-only reference workflows with identity/attribute evaluation | **Phase 2 goal; not currently available as a turnkey workflow** |
| Move a workflow to a stronger GPU or use a paid image API | Preserve the same job intent while explicitly choosing compatible backends | **Architectural goal; provider-by-provider verification required** |

**The metric we care about is useful images per unit of time, memory and money:not raw generations or a perfect-looking demo.** We have not yet established a benchmark advantage over ordinary ComfyUI.

## Try Prehnite without a GPU

The following example is real, executable and costs **zero inference credits**. It uses **synthetic demo images**, not AI photographs, so you can inspect the engine and its outputs without first installing models.

Requires Python 3.11 or newer. The most complete commands are in the development checkout:

```bash
git clone https://github.com/interzettel/prehnite.git
cd prehnite
python -m venv .venv
```

Activate the environment and install:

<details>
<summary><strong>Windows PowerShell</strong></summary>

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

</details>

<details>
<summary><strong>Linux / macOS</strong></summary>

```bash
source .venv/bin/activate
python -m pip install -e .
```

</details>

Then create and run a demonstration batch:

```bash
prehnite init --destination my-first-batch --batch-id sample-one
prehnite doctor
prehnite validate my-first-batch/manifest.yaml --profile my-first-batch/profile.yaml
prehnite estimate my-first-batch/manifest.yaml --profile my-first-batch/profile.yaml
prehnite run my-first-batch/manifest.yaml --profile my-first-batch/profile.yaml --workspace workspace
```

The generated workspace contains the persistent stage journal, selected assets, JSON/CSV/HTML reports and a checked ZIP export. Run the same batch again to see completed work recovered rather than blindly repeated.

Want to use the checked-in demo files instead? Start with `examples/manifest.yaml` and `examples/profile-demo.yaml`. See the [first-run guide](docs/ONBOARDING.md) and [offline gallery](docs/OFFLINE_GALLERY.md).

> **Installed alpha versus source:** The separately published [`prehnite==0.1.0a1`](https://pypi.org/project/prehnite/0.1.0a1/) is an early, immutable release. Many newer local-runtime, resource and cutout commands described in this repository are **development-source functionality**, not features of that PyPI wheel. Work from `main` to inspect the current implementation; a new package release requires separate approval.

## Using your own models

**Prehnite doesn't ship checkpoints, a ComfyUI installation, third-party custom nodes, or a ready-to-run model catalog.** Today the local integration expects you to supply a compatible ComfyUI installation, API-format graphs, checkpoints and their applicable rights.

The intended boundary is deliberately small:

```text
you: prompts / references / batch goals
                    |
                    v
         Prehnite: intent and policy
         - manifest + recipe versions
         - model / LoRA provenance
         - resource / spend guards
         - batch journal + recovery
         - inspect / select / export
                    |
                    v
    existing runtimes, currently ComfyUI
    (or an explicitly chosen API adapter)
                    |
                    v
       actual generated image files
                    |
                    v
       human review + final package
```

### Before you attempt real inference

1. Run `prehnite hardware` for read-only, source-labeled system/GPU observations. This does not certify model compatibility. To test just a running local ComfyUI server, `prehnite doctor --check-comfyui --comfyui-url http://127.0.0.1:8188` makes a short loopback-only status request; it does **not** load a model.
2. Use [the local native-1K example](docs/FIRST_REAL_ASSET.md#8-gb-laptop-smoke-test--genuine-native-1k): the preview.2 recipe targets **768×1024**, not a 4K output disguised by resizing. Your own API graph, model files and terms acknowledgements are still required.
3. Read [local recipe execution](docs/RECIPE_EXECUTION.md), [model and workflow resolver](docs/LOCAL_MODEL_RESOLVER.md), [model rights](docs/LICENSING.md) and the [source/alpha QA workflow](docs/LOCAL_LAB_MILESTONE_2026-10-18.md). The current engine can bind a ComfyUI graph/weights to a journal; it is **not** a universal one-click inference installer.

Optional providers, including the existing fal.ai adapter, are separate from local use and require explicit provider configuration, upload permission and budget caps. Hosted schema support and actual billed charges still need verification. Higgsfield is an **investigated possible integration**, not an available Prehnite adapter. No fallback should silently transmit personal reference photos.

## What actually works today?

<details open>
<summary><strong>Demonstrated and implemented</strong></summary>

- **Offline production foundation:** validated manifests/profiles, zero-cost synthetic generation, stage journaling and replay, bounded retries, reports, gallery and ZIP integrity. Its tests run on Windows and Linux CI.
- **Model-agnostic contracts:** typed adapter interfaces, optional API scaffolding, opt-in local ComfyUI workflow and checkpoint bindings, model-file checksums and reproducible recipe records.
- **Hardware observations:** read-only GPU/OS/RAM reporting and resource preflight; a failed or unknown observation must not become a fabricated compatibility claim.
- **Technical cutout tools:** source/mask bindings, multiple-instance export, alpha candidates, conservative QA, optional visual-review receipts. Experimental soft-alpha preservation and synthetic reference-matte diagnostics do **not** manufacture hair or glass transparency from binary masks.
- **One real local-lab success:** on 2026-10-18, a laptop RTX 4070 generated one 768×1024 SDXL source in about **46.04 seconds**. A GroundingDINO/SAM2 cutout took **8.994 seconds**, including load and inference, with a sampled peak of **2,533 MiB** for that stage. One CPU-refined lamp cutout was independently accepted **for that artifact and viewing scale only**. Private weights, output pixels and launcher remain outside the public package. [Full observation and limitations](docs/LOCAL_LAB_MILESTONE_2026-10-18.md).

</details>

<details>
<summary><strong>Not yet demonstrated or generally available</strong></summary>

- A repeatable, independently verified 8 GB model profile across three identical real runs. The new [P08-A03 offline evidence contract](docs/P08_A03_OFFLINE_PREPARATION.md) validates proposed records and synthetic fallback behavior only. **No new GPU run was authorized or performed.**
- Proven better speed, memory consumption, or human-accepted image yield versus a fair ComfyUI-only baseline; CPU offloading may make host RAM or latency worse.
- An install-and-run, rights-cleared bundle that automatically obtains compatible model weights and LoRAs.
- A fully reviewed ten-image **real-model** batch with honest accepted/rejected yield and memory/recovery receipts.
- General-purpose photographic matting for difficult glass, hair and mesh, or calibrated automated aesthetic/identity judgments.
- Turnkey LoRA experiment grids, private hairstyle/appearance editing, general 4K local performance or validated provider invoices.

</details>

Technical tests passing should not be mistaken for those missing real-world proofs.

## One product roadmap

![Two-phase Prehnite roadmap with the foundation verified and remaining milestones planned](assets/diagrams/roadmap.svg)


We've retired the competing progress ledgers. The **only active product roadmap** is [`progress/roadmap.json`](progress/roadmap.json), with one [generated status dashboard](docs/progress/STATUS.md).

**Current accepted product outcomes: 1 of 9 milestones.** The verified milestone is the installable synthetic foundation, not the entire image engine.

| | Milestone | Outcome |
| --- | --- | --- |
| Phase 1 | **P1-M00 : Foundation** | Verified: installable offline/synthetic engine |
| Phase 1 | **P1-M01 : Choose a model/runtime** | Research and benchmark decision for the existing 8 GB laptop |
| Phase 1 | **P1-M02 : Reproducible baseline** | Authorized physical repeatability and independent review |
| Phase 1 | **P1-M03 : Useful optimization** | Same-workload memory/time comparison with quality trade-offs |
| Phase 1 | **P1-M04 : Ten-image local batch** | Generate, inspect, resume, select and package actual images |
| Phase 1 | **P1-M05 : Product acceptance** | Human-reviewed quality, usefulness, installation and resource report |
| Phase 2 | **P2-M01 : LoRA research** | Choose compatible methods with rights and 8 GB constraints |
| Phase 2 | **P2-M02 : Style variations** | Reproducible controlled model/LoRA/seed experiments |
| Phase 2 | **P2-M03 : Private appearance sandbox** | Local reference variations with human consistency assessment |

A milestone is only complete after its **research, code, real experiment and/or human-acceptance gates** are actually satisfied. There is no automatic Phase 3 for audio, videos, social publishing or another UI.

The original **43/61 release units** and **21/73 atomic tasks** remain documented in [the historical v1 migration archive](docs/ROADMAP_MIGRATION_V2.md), with every old open obligation traceable. They are no longer rival active progress percentages. [Milestone definitions](docs/PRODUCT_MILESTONES.md) explain the evidence policy.

## Design boundaries

**Local first.** Ordinary synthetic workflows need neither a GPU nor an account; private references stay local unless a particular provider submission is explicitly authorized.

**Existing runtimes first.** Prehnite orchestrates an image workflow; ComfyUI owns the graph execution and model ecosystem. InvokeAI, Diffusers, quantized model paths or other runtimes are research candidates, not proven speedups.

**8 GB is the practical target.** We optimize against our actual laptop and **available host RAM**, not advertise unmeasured 4/6 GB hardware tiers. A larger GPU or an optional API should remain possible without redefining the entire product.

**Reproducibility before marketing.** Jobs retain seeds, recipes, output identities and failure receipts. A hash proves byte integrity; it does not prove image quality or legal model rights.

**No hidden costs.** Local GPU time consumes power, even with zero provider fees. Optional hosted calls require explicit spending/upload policies; estimates are not invoices.

**Quality that meets a brief.** Human acceptance of useful images, not universal perfection, is the goal. Research and optimization hypotheses must survive actual comparison.

## Project and development links

| For | Read |
| --- | --- |
| Recalibrate project direction | [Two-phase strategy](docs/PRODUCT_STRATEGY_LOW_VRAM.md) · [Product milestone plan](docs/PRODUCT_MILESTONES.md) |
| Inspect current facts | [Canonical status](docs/progress/STATUS.md) · [Full changelog](CHANGELOG.md) · [Recorded lab experiment](docs/LOCAL_LAB_MILESTONE_2026-10-18.md) |
| Try the software | [First run](docs/ONBOARDING.md) · [Local first asset](docs/FIRST_REAL_ASSET.md) · [CLI / model recipes](docs/MODEL_RECIPES.md) |
| Understand architecture | [Architecture](docs/ARCHITECTURE.md) · [Local engine bridge](docs/RECIPE_EXECUTION.md) · [Security](docs/SECURITY.md) |
| Contribute or audit history | [Contributing](CONTRIBUTING.md) · [Agent governance](AGENTS.md) · [Legacy roadmap crosswalk](docs/ROADMAP_MIGRATION_V2.md) |
| Track work | [Issues](https://github.com/interzettel/prehnite/issues) · [Project board](https://github.com/orgs/interzettel/projects/1) · [Agent coordination #9](https://github.com/interzettel/prehnite/issues/9) |

Prehnite is developed with agents, but the owner chooses priorities, model/asset rights, hardware experiments, spending and releases. A passing PR does not authorize inference or release a new package.

## License

**[MIT](LICENSE)** applies to Prehnite's code. ComfyUI, model weights, LoRAs, custom nodes, training sets and hosted services each retain their own licenses and usage rules. **No third-party weights are included** and no right to redistribute them is implied. See [licensing](docs/LICENSING.md) and [release policy](docs/RELEASING.md).

---

<div align="center"><sub>Prehnite : local experiments should stay yours.</sub></div>
