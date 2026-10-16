<div align="center">
  <img src="assets/prehnite-lockup.svg" alt="Prehnite — Make the batch. Keep the best." width="620" />
  <p><strong>Batch image production without the platform tax.</strong><br />
  An open-source Python engine for generating, checking, refining and exporting visual assets.</p>
  <p>
    <a href="https://github.com/interzettel/prehnite/actions/workflows/ci.yml"><img alt="Tests" src="https://github.com/interzettel/prehnite/actions/workflows/ci.yml/badge.svg" /></a>
    <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-296d60" /></a>
    <img alt="Python 3.11 or newer" src="https://img.shields.io/badge/python-3.11%2B-40564d" />
    <img alt="Development version" src="https://img.shields.io/badge/status-development-c28b4a" />
    <img alt="Mandatory platform fees: zero" src="https://img.shields.io/badge/platform%20fees-%240-296d60" />
  </p>
  <p>
    <a href="#try-it-in-two-minutes">Quick start</a> ·
    <a href="#how-it-works">How it works</a> ·
    <a href="#where-things-stand">Project status</a> ·
    <a href="docs/progress/STATUS.md">Progress</a> ·
    <a href="https://github.com/orgs/interzettel/projects/1">Project board</a>
  </p>
</div>

---

## Ninety images is a different problem from one image

Generating a single good picture is easy to demonstrate. Making a *batch* of assets to a brief, with the correct dimensions, cutouts, filenames, and a predictable bill, is a different job.

Prehnite is an attempt to automate the boring, expensive middle: keeping track of prompts and seeds, trying variants, checking what worked, doing targeted repairs instead of blindly starting over, and handing back exactly the files you asked for.

The ambition is simple: **spend less per *usable* asset, not merely less per generation.** It is a design target, not a claim we've already established with real-world benchmarks.

**Free orchestration is non-negotiable.** Prehnite is MIT licensed, runs locally, and has no required account, hosted workflow subscription, or per-seat platform fee. Use a local model where practical; connect to a paid image API *only when you choose to*, with a budget you set.

## Start with a zero-cost local batch

Run `prehnite init --destination my-first-batch` to get two safe sample
YAML files, then `prehnite doctor` to inspect your Python environment
without revealing any keys or contacting a service. For details, see
[the first-run guide](docs/ONBOARDING.md). These commands do not run AI
image generation or incur any inference costs.

## Try it in two minutes

You can test the complete workflow without a GPU, credentials, subscription, or inference charge. **The demo creates simple synthetic test images, not AI photographs.**

Clone the repo, create a Python 3.11+ environment, and install:

```bash
git clone https://github.com/interzettel/prehnite.git
cd prehnite
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux:        source .venv/bin/activate
python -m pip install -e .
```

Run a preflight estimate, then the zero-cost sample batch:

```bash
prehnite validate examples/manifest.yaml --profile examples/profile-demo.yaml
prehnite estimate examples/manifest.yaml --profile examples/profile-demo.yaml
prehnite run examples/manifest.yaml --profile examples/profile-demo.yaml --workspace workspace
```

Look under `workspace/batches/portrait-pilot/`. You'll find the selected images, the state journal, JSON/CSV reports, an [offline visual gallery](docs/OFFLINE_GALLERY.md) (`gallery.html`), a [local provenance record](docs/PROVENANCE.md) (`provenance.json`), and a ZIP with the requested output paths. A second run reuses completed stages.

<details>
<summary><strong>What the output looks like</strong></summary>

```text
workspace/
└── batches/
    └── portrait-pilot/
        ├── state.sqlite3
        ├── intermediates/
        ├── selected/
        │   └── photos/
        │       ├── street-001.jpg
        │       └── interior-001.jpg
        ├── report.json
        ├── operations.csv
        ├── report.html
        ├── gallery.html
        ├── provenance.json
        └── prehnite-portrait-pilot.zip
```

The ZIP preserves your requested relative filenames. Accepted cutouts, when configured, are transparent PNGs. Internally generated files stay separate from the deliverables.

</details>

## How it works

| | Stage | What Prehnite does |
| :--- | :--- | :--- |
| 01 | **Describe** | Read a structured manifest: prompts or existing images, exact sizes, targets and output filenames |
| 02 | **Plan** | Choose model providers and variants; estimate request counts and spend before starting |
| 03 | **Make** | Run generation and optional upscaling; preserve seeds, inputs and intermediate artifacts |
| 04 | **Check** | Apply technical checks, and optional model-based judgments when configured |
| 05 | **Repair** | Retry selectively under a hard attempt limit; cutout errors needn't regenerate accepted photos |
| 06 | **Deliver** | Export accepted images, named cutouts, a ZIP and an inspectable report |

A small manifest can describe a portrait batch with precise delivery requirements:

```yaml
id: street-pilot
assets:
  - id: rainy-street
    prompt: "A candid smartphone photograph of a rainy street at dusk"
    aspect_ratio: "9:16"
    target_size: [2160, 3840]
    output:
      image: photos/rainy-street.jpg
      cutouts: {}
```

The **manifest** says *what* to make. A separate **profile** says *how*: which provider/model to use, whether to compare 2K-upscaled and 4K variants, what to accept, the retry limit, and whether cloud calls may cost money. See the [working examples](examples/).

### Bring your own models, not your own orchestration subscription

| Route | What it means today |
| --- | --- |
| **Demo (no-cost)** | Synthetic generator + Pillow resize and technical checks. Runs offline and is covered by CI. |
| **Local ComfyUI** | Adapter for your own ComfyUI API-format workflows on localhost. You supply model weights and real graph/node mappings; no validated GPU workflow is bundled yet. |
| **fal.ai (optional paid)** | Opt-in hosted image generation/upscaling/segmentation adapter. Interfaces exist, but real endpoint schemas, pricing and image results still require live integration tests. |
| **Anthropic judge (optional paid)** | An opt-in image comparison/rubric adapter. It is not a calibrated or production-validated quality benchmark. |

No paid stage can be enabled by simply running the demo. Real cloud profiles require explicit `allow_paid` and, where images leave your machine, `allow_cloud_uploads`. They also require per-stage cost estimates and a positive `max_usd` cap. **Reserved amounts are estimates, not provider invoices or guaranteed billing ceilings.**

You can inspect what each adapter is actually prepared to run using
`prehnite models`. The [typed capability catalogue](docs/PROVIDER_CONTRACTS.md)
lists operation/input types, supported tiers and formats, upload requirements,
schema references, licensing cautions, and unimplemented candidates. Preflight
checks unsupported paid models and incompatible options **before an API call**;
custom ComfyUI graphs remain user-defined. The catalogue never supplies a
live price: all paid quotes in example profiles must be verified and updated
by you.

For the locally hosted route, start with [the ComfyUI example profile](examples/profile-comfyui.yaml). For pay-per-use hosting, review [the fal profile](examples/profile-fal.yaml), verify endpoint contracts and current prices, and provide your own `FAL_KEY`. Do not use the sample prices as a quote.

### Inspect detail without paying a judge

Image previews can hide important 4K defects. You can create **native-pixel detail crops** and an annotated overview entirely offline:

```bash
prehnite crops my-photo.png --output detail-evidence --edge 1024
```

The output includes five lossless corner/center crops and a SHA256 manifest. Add `--anchor-x 0.45 --anchor-y 0.35` for one manually chosen area. This creates review evidence, **not an automated quality score**. [Read the crop guide](docs/CROP_EVIDENCE.md).

### Opt-in reuse for repeatable stages

Prehnite can keep locally verified stage outputs in a
[private, content-addressed cache](docs/CACHING.md). It is disabled unless
you specify an explicit owner namespace; prompts, seeds, input hashes,
model options, version and model revision participate in the cache key.
Cloud-model reuse requires a separate cache opt-in and a pinned model
revision. A cache hit has no *new* provider request, but it does not erase
historical charges or prove previously billed amounts.

### Measure cost per usable asset, not raw generations

The offline [economics report](docs/ECONOMICS.md) distinguishes
**reserved/estimated spend** from **provider-reported partial amounts** and
**verified invoices** (currently unavailable). It tracks accepted versus
rejected assets, repeated stage invocations, local timing coverage and
cost-per-accepted output. Failures still contribute to reserved cost; a
batch with zero accepted assets has no meaningful cost-per-accepted figure.

## Where things stand

**`0.1.0.dev0` · source-only development preview.** Not a tagged release or a published PyPI package. The core synthetic workflow works; **photorealistic quality, 4K GPU feasibility, segmentation accuracy and actual API billing have not been certified**.

The tracker distinguishes implemented scaffolding from independently evidenced completions, and records issues blocked by local hardware, human calibration or paid-call authorization.

[![Prehnite evidence-backed progress by milestone](docs/progress/progress.svg)](docs/progress/STATUS.md)

[Read the 61-unit work ledger](docs/progress/STATUS.md) · [90-asset no-cost benchmark](docs/OFFLINE_90_BENCHMARK.md) · [Technical release gates](docs/PROGRESS.md) · [Offline production analytics](docs/OFFLINE_ANALYTICS.md) · [Failure codes and recovery actions](docs/FAILURE_TAXONOMY.md) · [Current sprint](docs/SPRINT.md) · [Roadmap](docs/ROADMAP.md)

The [Produce / Explore / Experiment evaluation RFC](docs/BATCH_OBJECTIVES.md) describes future batch modes and a measurement framework; v0.1 implements neither a general exploration planner nor a Pareto dashboard.

GitHub [Project #1](https://github.com/orgs/interzettel/projects/1) tracks workflow; the version-controlled [ledger](progress/ledger.json) tracks evidence. They answer different questions. Native Project field syncing is still [planned](https://github.com/interzettel/prehnite/issues/44).

## Built for a maintainer and their agents

Prehnite has a CLI first, optional [stdio MCP tools](src/prehnite/mcp_server.py) second. A person can run it directly; agents can submit preconfigured batches, check status, and request exports without being given arbitrary shell access. MCP workers now support [durable reconnect and cooperative pause/cancel/resume](docs/MCP_LIFECYCLE.md) on the main branch; a stop request does not immediately stop an in-flight provider request.

The project itself is managed the same way: small issue scopes, PR-based delivery, offline tests, and a persistent [agent-to-agent handoff thread](https://github.com/interzettel/prehnite/issues/9). One maintainer sets direction and approves spend and releases. Agents do the repeatable engineering work and leave evidence—not inflated status reports.

To contribute or extend the engine, start with [Contributing](CONTRIBUTING.md), [Architecture](docs/ARCHITECTURE.md), [Security](docs/SECURITY.md), and [Versioning](docs/VERSIONING.md). Issues are welcome, particularly for adapters that remain optional and testable without network access.

## License and boundaries

**[MIT](LICENSE)** for Prehnite's own code. Image models, checkpoints, external APIs, datasets, and other installed applications retain **their own** terms; nothing about this repository grants a license to third-party weights. See [Licensing](docs/LICENSING.md) and the [release policy](docs/RELEASING.md).

No model checkpoint ships with the repo. No mandatory hosted product or subscription. No release tags until a version has passed its gates and the maintainer approves it.
