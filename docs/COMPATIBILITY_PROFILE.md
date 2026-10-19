# Local compatibility profile by model size (v1)

**Profile:** `p08-a04-local-compatibility` **v1.0.0** · **Published:** 2026-10-19

**Task:** P08-A04 — Publish compatibility profile by model size

**Original acceptance:** “Decision table states actually measured versus unknown VRAM configurations.”

**Status:** ready for independent review; **not** a completion claim and **not** a general GPU support certification.

This page records what was actually executed or refused on one local Windows host. It is intentionally narrow. The machine-readable table is [`compatibility-profile.v1.json`](compatibility-profile.v1.json); the environment and installed-weight evidence is in [`P08_A01_ENVIRONMENT_AND_RIGHTS.md`](P08_A01_ENVIRONMENT_AND_RIGHTS.md). The existing hardware doctor remains the generic read-only probe ([HARDWARE_DOCTOR.md](HARDWARE_DOCTOR.md)). Issue: [#24](https://github.com/interzettel/prehnite/issues/24).

## Evidence classes

| Class | Meaning in this profile |
| --- | --- |
| **Observed successful** | Backed by an actual prior execution receipt. |
| **Observed blocked** | Backed by a real preflight or execution refusal. |
| **Estimated, not verified** | Only file-size or architecture reasoning; never presented as measured. |
| **Unknown** | No trustworthy local runtime evidence. |
| **Unsupported** | Only where actual technical incompatibility was demonstrated. |

**No compatibility estimate is published here.** The checkpoint-byte total is a file-size fact, not a VRAM requirement.

## Tested configuration

- Detector: **GroundingDINO SwinT OGC** (693,997,677 bytes; config 1,006 bytes)
- Segmenter: **SAM 2.1 Hiera Base Plus** (323,606,802 bytes)
- Text encoder/tokenizer: **BERT base uncased** (440,449,768 bytes; config/tokenizer files included)
- Aggregate installed bytes: **1,458,753,441**
- All eight installed files hash-match the pinned private dependency manifest; hashes, source revisions and Apache-2.0 provenance are recorded in [P08-A01](P08_A01_ENVIRONMENT_AND_RIGHTS.md).
- Execution environment: Windows, ComfyUI **0.41.0**, Python **3.12.9**, **torch 2.7.0+cu128**, **torchvision 0.22.0+cu128**, Transformers **4.57.6** compatibility overlay.
- GPU: **NVIDIA GeForce RTX 4070 Laptop GPU**, **8,188 MiB** reported dedicated VRAM.
- Driver/CUDA layers: driver **617.42**, driver CUDA UMD **13.4**, PyTorch compiled CUDA **12.8**, no local CUDA toolkit.

## Decision table

| Configuration / model size | Device / environment | Measured VRAM | System RAM / policy | Outcome | Class |
| --- | --- | --- | --- | --- | --- |
| Tested base stack: GroundingDINO SwinT + SAM 2.1 Base Plus + BERT (1.459 GB installed files) | RTX 4070 Laptop 8,188 MiB; Windows; torch 2.7.0+cu128; Transformers 4.57.6 overlay | **2,533 MiB sampled peak used**; **5,416 MiB minimum free** | Minimum available **3,338 MB**; peak commit **57.6%**; historical **3,000 MB** supervisor floor | **1 prompt succeeded** in **8.994 s** start-to-success (model load + inference); no OOM | **Observed successful** — one run only |
| Same tested stack | Same GPU/software | Free VRAM **7,353 MiB** (VRAM pass) | Available **5,759 / 5,741 / 5,737 MiB**; commit ~**54.27%**; current **6,000 MiB** preflight floor | **Blocked before ComfyUI start; 0 prompts** | **Observed blocked — system RAM, not VRAM** |
| SAM 2.1 Hiera Large + tested detector/encoder | Same 8 GiB card | — | — | No installed checkpoint or execution | **Unknown** |
| SAM 2.1 Small / Tiny + tested detector/encoder | Same 8 GiB card | — | — | No installed checkpoint or execution | **Unknown** |
| GroundingDINO SwinB / alternate detector | Same 8 GiB card | — | — | No installed checkpoint or execution | **Unknown** |
| Quantized variants of the tested stack | Same 8 GiB card | — | — | No quantized checkpoint or execution | **Unknown** |
| SDXL segmentation configuration | Same 8 GiB card | — | — | SDXL is a generation checkpoint; no segmentation measurement | **Unknown** |
| Tested stack on 4 / 6 / 12 / 16 / 24 GiB GPU tiers | Other GPUs | — | — | No other GPU tier tested | **Unknown** |
| Tested stack under WSL/Linux | WSL Ubuntu 24.04.5 | — | — | WSL has no PyTorch or CUDA toolkit installed | **Unknown** |
| Repeated runs / batch throughput | Same 8 GiB card | — | — | One prompt only; P08-A03 remains blocked | **Unknown** |

**Unsupported configurations:** none demonstrated. Absence of evidence is **unknown**, not unsupported. WSL lacking PyTorch is an environment gap, not a proven incompatibility of the model stack.

## What the table does and does not establish

**Establishes:** one historical run of this exact base stack on this exact 8,188 MiB laptop GPU completed without OOM under a 3,000 MB RAM supervisor floor, with 2,533 MiB sampled peak VRAM. A later resource preflight with the same model files was refused because available **system RAM** was below **6,000 MiB**; free VRAM passed.

**Does not establish:**

- a minimum VRAM requirement (2,533 MiB is a sampled peak, not a floor);
- general 8 GB compatibility, another GPU tier, larger SAM variants, larger detectors, quantization, SDXL segmentation, WSL execution or repeatability;
- throughput, p50/p95 latency, batch stability or model quality;
- that the historical run’s 3,000 MB RAM floor and the current 6,000 MiB preflight floor are interchangeable. They are different policies.

The historical successful receipt is preserved in the private lab and cited by SHA256 in the machine-readable profile. The blocked preflight similarly has a private receipt and public summary. No private image, checkpoint, machine path or secret is included here.

## Reproduction and validation

- CPU-only consistency tests: [`tests/test_compatibility_profile.py`](../tests/test_compatibility_profile.py)
- Test rule: only an `observed_success` row may carry successful runtime measurements; every unknown row must have no measured values; no unmeasured configuration may be labelled successful.
- The profile is not a runtime probe. Use the read-only [hardware doctor](HARDWARE_DOCTOR.md) for current host observations; no model is loaded.
- Atomic tracker: **17/73** at publication. P08-A04 is not marked complete until this profile is independently reviewed and the supporting PR is merged; P08-A02/A03 remain blocked.
