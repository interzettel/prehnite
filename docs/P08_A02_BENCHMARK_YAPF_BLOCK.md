# P08-A02 bounded benchmark — startup blocked in SAM2/yapf import

**Task:** P08-A02 — bounded 8 GB model load and forward pass

**Status:** **BLOCKED — no prompt, model load or inference occurred**

**Issue:** [#24](https://github.com/interzettel/prehnite/issues/24)

## What was attempted

One owner-authorized benchmark session with a maximum of two prompt submissions.
The validated ComfyUI startup configuration (ComfyUI venv, 4.57.6 overlay,
GroundingDINO SwinT OGC + SAM 2.1 Base Plus + BERT, RTX 4070 Laptop) was used.

The preflight passed with unchanged policy:

- available RAM: 10.26–10.42 GB
- commit: 39.09–39.30%
- free VRAM: 7.87 GB
- all eight pinned weights/config/tokenizer hashes matched
- no existing conflicting listener

## Result

The session failed **before readiness**:

- supervisor `ready: false`, `reason: timeout`
- elapsed: **122.469 s**
- child return code: **124** (launcher watchdog)
- prompt submissions: **0**
- checkpoint/model loads: **0**
- cold/warm inference: **not_observed**
- peak sampled VRAM: **559 MiB** (startup only; not a model/inference peak)
- independent TCP observations: 250 samples, **250 timeout, 0 connected**
- cleanup: no remaining processes, no 8188/8189 listener
- no OOM and no model-rights failure

## Captured blocking stack

Thread stacks were captured at 30, 60 and 90 seconds by the diagnostic
`faulthandler` instrumentation. The main thread was repeatedly blocked in this
custom-node import path:

```text
ComfyUI-SAM2/__init__.py
→ node.py
→ local_groundingdino/util/utils.py
→ local_groundingdino/util/slconfig.py (yapf FormatCode import)
→ yapf/__init__.py
→ yapf/pyparser/pyparser.py
→ yapf_third_party/_ylib2to3/pygram.py
→ pgen2/driver.py load_grammar
→ pgen2/grammar.py dump
→ tempfile.NamedTemporaryFile
→ tempfile._mkstemp_inner
```

No diagnostic-node or server-ready marker was reached. The blocked path is in
custom-node initialization, before any segmentation checkpoint is loaded.

**Immediate root cause is proven at the stack level:** yapf import inside the
SAM2 custom node blocks in temporary-file creation during grammar loading.

**Not proven:** why the OS temporary-file operation stalls (filesystem, filter,
driver or other host state). The failure is also nondeterministic: an earlier
startup-only run using the same diagnostic base became ready in 9.328 s.

## Acceptance status

P08-A02's original acceptance is **not met**:

- no cold inference or warm inference latency;
- no model-load timing;
- no model/inference VRAM peak;
- no OOM/post-load failure behavior.

No output or prompt identity exists. No generated content was promoted or
visually accepted. P08-A02 remains **blocked**; the original atomic tracker is
unchanged and P08-A03 is not started. No release or historical artifact was
changed.
