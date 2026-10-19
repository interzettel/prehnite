# P08-A02 — bounded GPU benchmark blocked at startup

**Task:** P08-A02 — Run bounded 8 GB model load and forward pass  
**Original acceptance:** “Measure peak VRAM, cold/warm latency and failure behavior on actual laptop.”  
**Status:** **BLOCKED at startup; acceptance not met**  
**Progress:** no atomic completion credit; frozen tracker remains at its current value until independent review of any future complete benchmark. This page does not change `progress/atomic.json`.

## What was attempted

One explicitly owner-authorized, bounded benchmark was prepared for the exact installed
GroundingDINO SwinT OGC + SAM 2.1 Hiera Base Plus + BERT base uncased stack on the
RTX 4070 Laptop. The source was the CC0 Wikimedia Commons *Wenger backpack* photograph,
target `red backpack`, with a deterministic 768×1024 derivative.

The run was limited to one ComfyUI startup, one cold prompt and one warm prompt, a
300-second workload budget, no retries, no alternate models, no downloads and no
model or package changes.

## Preflight

The merged read-only resource policy passed immediately before startup:

- Available system RAM ≥6,000 MiB: **passed** (18,417.8 MB at runtime preflight)
- System commit ≤80%: **passed** (25.6%)
- Free GPU VRAM ≥5,000 MiB: **passed** (7,946 MB)
- All installed model/config/tokenizer SHA256s matched the P08-A01 manifest
- Transformers **4.57.6** compatibility overlay was present
- No pre-existing 8188/8189 listener or compatible ComfyUI process

The resource observation remained observation-only (`startup_authorized: false`); the
separate owner authorization was the basis for the attempt.

## Source

- Commons: https://commons.wikimedia.org/wiki/File:Wenger_backpack.jpg
- Author: Sir Tragedy · CC0 1.0
- Original: 3120×3880 JPEG; SHA256
  `2a5fd2cc4f8d150f74666bcd3ec34da08de9a5041e817c81f2416f444e593a97`
- Deterministic 768×1024 derivative: center crop `[105,0,3015,3880]`, LANCZOS;
  SHA256 `0633e149dd41d14355c2097e5fb80b824f53d22a1e3b75faed915ce3d8682b2c`
- Target: `red backpack`; no private image published.

## Startup outcome

ComfyUI did initialize the CUDA device (log reported RTX 4070 Laptop, total VRAM
8188 MB, PyTorch 2.7.0+cu128), but it **never opened `/system_stats`**. The private
supervisor reached its 120-second startup limit:

- startup result: **failed / timeout**
- elapsed: **122.703 s**
- child return code: **124**
- prompt submissions: **0**
- checkpoint loads: **0**
- model inference: **none**
- peak sampled VRAM during startup: **117 MiB**
- minimum available system RAM: **17,520.9 MB**
- maximum commit: **29.49%**
- failure behavior: bounded boot timeout, not OOM and not a model-compatibility or
  rights refusal

The last ordinary ComfyUI log marker was its OpenGL-accelerate absence notice; no
server-ready marker followed before the watchdog terminated it. No `/prompt` was
sent, so no cold/warm inference latency or model-load measurement exists.

Cleanup was clean: supervisor summary reports no descendants/remaining processes,
no 8188/8189 listener remains, and the attempt marker is preserved.

## Defect found

During the first pre-start attempt, the **private** consolidated runtime wrapper
passed a `Path` instead of an open file object to `subprocess.Popen`; that attempt
failed before spawning ComfyUI. The wrapper was fixed and the actual startup was
then attempted once. The private defect is documented in the private lab; this
public page does not claim it caused the later startup timeout.

## What this does not establish

No conclusion is drawn about:

- cold/warm inference latency;
- model-loading time;
- peak VRAM during model load/inference;
- OOM behavior after model load;
- 8 GB feasibility or other model sizes;
- source quality or acceptance.

The earlier P08-A01 environment record and the P08-A04 compatibility matrix remain
the evidence for measured-versus-unknown hardware claims.

## Next action

Diagnose the ComfyUI startup readiness hang without changing model/package
configuration; do not retry automatically. A fresh, separately authorized benchmark
is required. P08-A03 is not started. No release, tracker edit, acceptance record or
historical artifact was changed.
