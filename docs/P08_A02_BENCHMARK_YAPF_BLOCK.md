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

## Upstream Windows YAPF grammar-cache candidate (independent review)

An independent review found a notably similar [upstream YAPF issue
#1311](https://github.com/google/yapf/issues/1311). On **Windows +
Python 3.11/3.12**, YAPF **0.43.0** was reported to repeatedly attempt
creation of its generated grammar-cache temporary file when the cache
directory appears writable but rejects creation with `PermissionError`.
The upstream stack (`pygram → driver.load_grammar → grammar.dump →
NamedTemporaryFile → _mkstemp_inner`) matches the **captured code
path** in this incident. The proposed upstream [fix #1314](
https://github.com/google/yapf/pull/1314) is not merged as of this
review. Neither report establishes this laptop's exact installed YAPF
version, cache path, permissions or reason for the stall.

**Do not treat the upstream mechanism as proven locally.** In particular,
the current traces do not show which `os.open` failures occurred or
whether file security filtering, cache permissions, other processes or
another cause prevented the operation. A successful earlier startup
does not disprove an intermittent cache-write problem.

**Next offline diagnostic — no ComfyUI or CUDA startup:**

1. Read package metadata for the **exact ComfyUI-venv YAPF version**,
   Python version and `platformdirs` version without importing YAPF.
2. Resolve the cache path using installed source and inspect directory
   existence, ACLs, timestamps, pending `.pickle`/temporary files and
   path redirection read-only; redact private paths in any public receipt.
3. In a **short-timeout isolated CPU subprocess**, separately test YAPF
   grammar import and a uniquely named disposable cache-directory file
   creation, logging the precise return/error and terminating a stalled
   child. Do not delete existing caches or silently change the user's
   actual cache permissions.
4. Contrast default-cache and clean **disposable cache** behaviour in
   otherwise identical CPU-only processes. Avoid changing the global
   `LOCALAPPDATA`, dependency versions or permanent ComfyUI environment.
5. If this reproduces a denied-cache retry, propose a narrowly scoped,
   reversible cache workaround with tests and an exact evidence chain.
   A subsequent ComfyUI startup or cold/warm inference benchmark still
   requires separate explicit owner authorization.

This is a **possible root-cause mechanism to verify**, not a completed
P08-A02 benchmark or automatic permission to launch GPU processes.

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
