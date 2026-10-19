# P08-A02 final cold/warm benchmark evidence

**Status:** original narrow benchmark criterion independently reviewed as met; **completion credit awaits evidence PR merge and separate frozen-ledger reconciliation**

**Issue:** [#24](https://github.com/interzettel/prehnite/issues/24)

## Scope

One owner-authorized session using the verified ComfyUI venv, pinned
Transformers 4.57.6 overlay and original model/checkpoint hashes. Exactly one
startup and exactly two prompts were submitted: one cold, then one identical
warm prompt after cold success. No retry or third prompt occurred.

## Startup recovery

The previously reproduced Windows YAPF grammar-cache stall was avoided with a
**child-scoped, disposable writable platformdirs cache**. The override was not
applied to the parent environment; the original YAPF cache was not modified. The
disposable cache was removed after the run.

- YAPF validation: `YAPF_IMPORT_OK`, `CACHE_WRITE_OK`, cache under override
- validation elapsed: **0.184 s**
- parent environment restored; no global cache/ACL/package change

## Preflight

Unchanged policy: ≥6,000 MiB available RAM, ≤80% commit, ≥5,000 MiB free VRAM.

- available RAM: 9.33–9.58 GB — pass
- commit: 42.941 / 42.587 / 42.689% — pass
- free VRAM: 8.10–8.11 GB — pass
- all eight pinned model/config/tokenizer hashes matched
- no conflicting listener/process

## Startup and node registration

- one startup, original **120 s** limit
- ready elapsed: **10.0 s**
- `/system_stats`: **200**
- `/object_info`: **200**, **991** node classes
- required nodes present:
  - `SAM2ModelLoader (segment anything2)`
  - `GroundingDinoModelLoader (segment anything2)`
  - `GroundingDinoSAM2Segment (segment anything2)`
  - `LoadImage`, `MaskToImage`, `SaveImage`

## Cold/warm measurements

| Measurement | Cold | Warm |
| --- | --- | --- |
| Prompt ID | `078f3e05-e8d8-4deb-a70a-51af18587be4` | `34416532-7730-407b-9d0d-30c6d3f76a2e` |
| Status | success | success |
| Wall latency | **7.562 s** | **0.727 s** |
| Log execution | 7.11 s | 0.67 s |
| Checkpoint loads | **1** total (cold path) | none |
| Observable model-load interval | **4.0 s** | null |
| Cold post-load derived | **3.562 s** | — |
| Cold − warm | **6.835 s** | — |

Both prompts used the same model, source bytes, target, threshold and graph
parameters. The warm source is byte-identical under a different filename to
avoid cache reuse; it is not a different image.

## Inputs and workflow identity

- original CC0 JPEG: `2a5fd2cc4f8d150f74666bcd3ec34da08de9a5041e817c81f2416f444e593a97`
- 768×1024 source derivative: `0633e149dd41d14355c2097e5fb80b824f53d22a1e3b75faed915ce3d8682b2c`
- target: `red backpack`; threshold `0.3`
- cold graph: `07ddf6858b2f787bac3af255a4c0fac7dfee9f15a5c5dfeb14fd581f71787b98`
- warm graph: `c757c57be1f2cd725e6c6c3e40aaa896440f8152de37894d4e6011de7d9fc7d3`

## Outputs

Both are 768×1024 RGB and remain **review-pending**; no visual acceptance is
claimed.

- cold: 7,142 bytes — `df7a5a5b81d3036da08c275b00f30d58487b554a77841a9f5eca323637f9de25`
- warm: 7,147 bytes — `0d15dad790f64880f57f03066481f5c69669fd02bd4638d1551863297fb9ab61`

## Resource observations and failures

- sampled peak VRAM: **2,582 MiB** — this is not a minimum-VRAM requirement
- minimum free VRAM: **5,367 MiB**
- minimum available RAM: **7,533.3 MB**
- maximum commit: **51.01%**
- monitor samples: 51
- no OOM; no traceback
- warnings were environment notices only: Windows single-GPU mode,
  cu130 recommendation, triton unavailable, PyTorch &lt;2.8 DynamicVRAM fallback
- two prompts executed within the **300 s** workload budget

## Cleanup

- supervisor return code: **0**
- descendants tracked and cleaned; no remaining processes
- no 8188/8189 listener
- disposable YAPF cache removed; parent override absent
- original YAPF cache preserved

## Acceptance boundary

This evidence has been **independently reviewed for P08-A02's narrow original metric criterion**, but it earns no completion credit before the evidence PR merges and a separate accounting PR passes CI. The original atomic tracker was **19/73 (26.03%) when the laptop report was prepared**. Unrelated [S04-A04 accounting PR #178](https://github.com/interzettel/prehnite/pull/178) subsequently moved public `main` to **20/73 (27.40%)**. P08-A02 remains blocked in the current register until credited against that latest baseline; P08-A03 is not started, and no release, model/package change or historical artifact was modified. Cold post-load latency is derived from observable timestamps, not a separately instrumented measurement.

[![](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)
