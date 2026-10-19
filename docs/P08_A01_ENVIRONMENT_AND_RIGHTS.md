# P08-A01 — environment and installed-weight rights record

> **Review status:** evidence independently reviewed and merged as [PR #166](https://github.com/interzettel/prehnite/pull/166). P08-A01 was then credited in the original frozen atomic register. This is not a legal opinion, live benchmark certification or P08 parent completion. Issue: [#24](https://github.com/interzettel/prehnite/issues/24).

## Scope

This record covers the local segmentation workflow used for the accepted lamp
trial and the prepared backpack trial: GroundingDINO detector, SAM 2.1 Hiera Base
Plus segmenter, BERT base uncased text encoder/tokenizer, and the pinned
ComfyUI-SAM2 node source. SDXL generation weights are outside this scope.

Collection was read-only. No model was loaded, no CUDA context was created, no
`/prompt` was submitted, and no image was processed for this record.

## Host and WSL

| Environment | Observation |
| --- | --- |
| Windows caption/build | Windows 11 Home, build **26300.9711**, display version **26H2**, 64-bit |
| Windows registry product name | Windows 10 Home (same build; observed discrepancy retained) |
| Physical RAM | 34,006,450,176 bytes |
| Fresh available RAM | 7,003 MiB |
| Fresh system commit | 41,817,006,080 / 76,956,123,136 bytes = **54.339%** |
| WSL | **2.5.7.0**, Ubuntu **24.04.5 LTS**, kernel **6.6.87.1-microsoft-standard-WSL2**, x86_64 |
| WSL Python | **3.12.3** |
| WSL PyTorch/torchvision | **not installed** |
| WSL CUDA toolkit/nvcc | **not installed** |
| WSL GPU visibility | RTX 4070 Laptop visible through `nvidia-smi` |
| WSL SMI header | NVIDIA-SMI **615.78.05**, KMD **617.42**, CUDA UMD **13.4**; query reports driver **617.42** |

## Driver and CUDA layers

| Layer | Value |
| --- | --- |
| NVIDIA Windows driver | **617.42** |
| Driver-reported CUDA UMD | **13.4** |
| PyTorch package | **2.7.0+cu128** |
| PyTorch compiled CUDA | **12.8** (from package metadata, not a toolkit install) |
| Local CUDA toolkit / nvcc | **none** |

The driver compatibility level, PyTorch build target and local toolkit are
separate facts and must not be conflated.

## GPU

- **NVIDIA GeForce RTX 4070 Laptop GPU**
- **8188 MiB** dedicated VRAM
- **7343 MiB** free at observation; **606 MiB** used; 0% utilization
- No ComfyUI process was running.

## Software inventory

Windows ComfyUI environment:

- `torch==2.7.0+cu128`
- `torchvision==0.22.0+cu128`
- `transformers==5.20.1` (shared) / **4.57.6** compatibility overlay
- `tokenizers==0.23.3` / **0.22.2** overlay
- `huggingface-hub==2.2.0` / **0.36.2** overlay
- `numpy==1.26.4`
- `safetensors==0.8.0`
- Prehnite editable **0.1.0a2.dev0**
- Python **3.12.9** (ComfyUI); Prehnite venv Python **3.12.5**

## Installed model dependencies

All files were hashed directly with streaming SHA256; the hashes match the
existing private implicit-dependency manifest.

| Role | Identity | Bytes | SHA256 | Source revision |
| --- | --- | ---: | --- | --- |
| Detector weights | GroundingDINO SwinT OGC | 693,997,677 | `3b3ca2563c77c69f651d7bd133e97139c186df06231157a64c507099c52bc799` | `ShilongLiu/GroundingDINO` @ `a94c9b567a2a374598f05c584e96798a170c56fb` |
| Detector config | GroundingDINO SwinT OGC | 1,006 | `172e80017f9395668a9cb5d1b8bd9d061c0e360471c6ed673c83b69bb14399f1` | same |
| Segmenter weights | SAM 2.1 Hiera Base Plus | 323,606,802 | `a2345aede8715ab1d5d31b4a509fb160c5a4af1970f199d9054ccfb746c004c5` | `facebook/sam2.1-hiera-base-plus` @ `b7320756a13354e7530a63935656d35b2f91a290` |
| Text encoder | BERT base uncased | 440,449,768 | `68d45e234eb4a928074dfd868cead0219ab85354cc53d20e772753c6bb9169d3` | `google-bert/bert-base-uncased` @ `86b5e0934494bd15c9632b12f734a8a67f723594` |
| BERT config | BERT base uncased | 570 | `7160e1553ad2ca51d8c1cb066be533db31826e12d173824c1bb0cb1a4f187d20` | same |
| Tokenizer | BERT tokenizer.json | 466,062 | `ce64fce797c24f68df90b40a3f74f579b336a493db14bd583fd520ea0d8c9a98` | same |
| Tokenizer config | BERT tokenizer_config.json | 48 | `a025160ef0431f1a392f6f050c1310f4c5d9fb6f275932dbccba73c4d214bf10` | same |
| Vocabulary | BERT vocab.txt | 231,508 | `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3` | same |

Pinned execution source: `ComfyUI-SAM2` at upstream commit
`757034be78e877c07db8e7913f489089af224630`; local `LICENSE` is Apache-2.0.

No model binaries or private paths are included in this repository.

## Licence provenance

This is a documentary review, not legal advice or legal clearance.

| Family | Licence | Commercial | Redistribution | Evidence |
| --- | --- | --- | --- | --- |
| GroundingDINO weights/config | Apache-2.0 | supported under Apache-2.0 conditions | supported under Apache-2.0 conditions | [IDEA LICENSE](https://github.com/IDEA-Research/GroundingDINO/blob/main/LICENSE), [HF model card](https://huggingface.co/ShilongLiu/GroundingDINO) |
| SAM 2.1 weights | Apache-2.0 | supported under Apache-2.0 conditions | supported under Apache-2.0 conditions | [Meta LICENSE](https://github.com/facebookresearch/sam2/blob/main/LICENSE), [HF model card](https://huggingface.co/facebook/sam2.1-hiera-base-plus) |
| BERT base uncased | Apache-2.0 | supported under Apache-2.0 conditions | supported under Apache-2.0 conditions | [HF model card](https://huggingface.co/google-bert/bert-base-uncased) |
| ComfyUI-SAM2 node source | Apache-2.0 | supported under Apache-2.0 conditions | supported under Apache-2.0 conditions | local `LICENSE`; pinned commit |

Recorded conditions: include the Apache-2.0 licence and retain applicable
copyright/patent/trademark notices; state changes to modified files; do not imply
upstream endorsement; patent grant terminates on patent litigation; no warranty.
Apache-2.0 does not grant trademark rights. Exact weight files and revisions are
listed above. No unresolved rights item was found in this limited review.

## Historical execution evidence

These are historical measurements, not fresh measurements:

- One accepted real lamp cutout with GroundingDINO + SAM2
- Prompt `ab4cb4d3-3b87-4cab-9ad9-666112f12236`
- Cold startup **9.25 s**; job start to success **8.994 s** including model
  loading and inference
- Peak sampled VRAM **2,533 MiB**
- One prompt, one success, no retry; private image and weights not published
- Public context: [dated local-lab milestone](LOCAL_LAB_MILESTONE_2026-10-18.md),
  [first real asset](FIRST_REAL_ASSET.md)

## Known / unknown

Known: OS build, WSL environment, GPU/VRAM, driver, driver CUDA UMD, PyTorch
compiled CUDA, package versions, all eight dependency hashes, source revisions,
and Apache-2.0 licence evidence.

Known absent: WSL PyTorch, WSL segmentation packages, local CUDA toolkit/nvcc.

Not inferred: WSL PyTorch CUDA build (not installed), model load in WSL,
training-data rights, output rights, future redistribution beyond Apache-2.0
notices, or legal clearance.

Observed ambiguity: Windows registry/`Get-ComputerInfo` product name versus
`Win32_OperatingSystem` caption for the same build; both are retained in the
private evidence rather than normalized.

## Reproduction

Use read-only commands and avoid importing CUDA models:

```powershell
Get-ComputerInfo
Get-CimInstance Win32_OperatingSystem
Get-CimInstance Win32_VideoController
Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free,utilization.gpu --format=csv
nvidia-smi
wsl.exe --version
wsl.exe -l -v
wsl.exe -d Ubuntu-24.04 -- bash -lc 'uname -a; cat /etc/os-release; python3 --version; python3 -m pip list --format=freeze; command -v nvcc; nvidia-smi'
```

Hash only the actual dependency files with a streaming SHA256 tool; do not load
checkpoints into RAM. Compare against the table above.

## Acceptance evaluation

| Criterion component | State |
| --- | --- |
| OS identity reproducibly documented | met |
| CUDA/driver versions recorded without conflation | met |
| Installed software dependencies identifiable | met |
| Relevant weight identities and hashes verified | met |
| Licensing and restrictions traceable | met |
| Missing/unresolved facts explicit | met |
| Inventory reproducible by another engineer | met |
| Private data excluded from this public page | met |

**Independent review verdict: `P08-A01 original acceptance criterion met`.** The private checkpoint hashes were computed and preserved by the laptop agent, not rehashed on GitHub. The private report's uploaded SHA256 and the upstream model-card licence declarations were independently checked. This does not certify full downstream redistribution or model execution.

At the time of local evidence capture, the atomic register was **15/73**. Later [S04-A02](https://github.com/interzettel/prehnite/pull/168) credit brought it to **16/73**. The independently reviewed P08-A01 evidence subsequently merged through [PR #166](https://github.com/interzettel/prehnite/pull/166), and its original-register reconciliation raised the tracker to **17/73** at that stage. A later, independent [S04-A03 source merge](https://github.com/interzettel/prehnite/pull/171) and its own original-register credit raised the current overall atomic count to **18/73 (24.66%)**; this does not increase P08 beyond 1/4. P08-A02 remains blocked; no GPU work is authorized by this record.
