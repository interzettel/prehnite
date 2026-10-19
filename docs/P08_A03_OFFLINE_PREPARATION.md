# P08-A03 offline preparation — repeated local inference

**Status:** preparation only; **P08-A03 remains blocked**

**Hardware execution:** not authorized and not performed

**Tracker:** 21/73 unchanged; no completion credit requested

## Purpose

P08-A03's original acceptance is “3-run identical profile evidence and fallback
path.” P08-A02 established one cold and one warm run, but that does not establish
three-run repeatability or fallback behavior. This preparation defines the
bounded experiment, fail-closed evidence contract and simulated fallback tests
needed before a separately authorized GPU session.

No ComfyUI process, model checkpoint, CUDA context, prompt or GPU OOM was created
or triggered in preparing this work.

## Proposed bounded experiment

The exact proposal, requiring fresh owner authorization, is:

- **one** supervised ComfyUI startup using the validated ComfyUI venv,
  Transformers 4.57.6 overlay, original model/checkpoint hashes and the
  child-scoped disposable YAPF cache workaround;
- **exactly three** inference submissions with the same input bytes, target,
  model, graph, parameters and runtime configuration;
- **no automatic retry**, no third/fourth-submission substitution, no new model
  download/install, package upgrade, CUDA change, global cache/ACL change or paid
  service;
- unchanged preflight floors: available RAM **≥6,000 MiB**, commit **≤80%**,
  free VRAM **≥5,000 MiB**;
- startup limit **120 s**, per-run limit **300 s**, total workload limit
  **900 s**, and cleanup within **60 s**;
- stop immediately on preflight/cache-validation/startup/required-node failure,
  any run failure, termination, CUDA/OOM error, unknown outcome, duplicate prompt,
  reused output path, exhausted budget or owner interrupt;
- after three successes, stop and shut down; never submit a fourth attempt.

The reusable public contract is:

```text
python scripts/p08_a03_offline.py plan
python scripts/p08_a03_offline.py simulate-fallbacks
python scripts/p08_a03_offline.py validate <evidence.json>
```

`plan` and `simulate-fallbacks` are hardware-free. `validate` is read-only and
fails closed unless the three-run evidence is complete.

## Evidence contract

Each run must record:

- profile: input, model, workflow and parameters SHA256, profile id and target;
- the identical profile digest across all three runs;
- prompt id, run index, retry count and status;
- start/finish timestamps and wall latency;
- sampled peak VRAM, minimum free VRAM, minimum available RAM and maximum commit;
- output path and SHA256, with distinct paths per run;
- CUDA/OOM/failure classification and cleanup status.

The bundle additionally records preflight status, startup readiness and required
node presence, remaining processes, listener state, disposable-cache removal and
child-environment restoration.

Rules:

- observed measurements are distinguished from derived values;
- sampled peak VRAM is not an absolute peak or a minimum requirement;
- output hashes need not be identical unless determinism is separately proven;
- exactly three successful runs are required for a pass;
- any missing or malformed field is `incomplete`, not a pass.

## Simulated fallback coverage

The offline tests cover:

- insufficient available RAM;
- insufficient free VRAM;
- excessive system commit;
- startup timeout;
- missing required segmentation nodes;
- inference failure;
- process termination;
- unknown execution outcome;
- CUDA/OOM classification;
- duplicate prompt submission;
- reused/overwritten artifact path;
- incomplete cleanup, listener, cache removal and environment restoration;
- exactly three runs, no fourth run and no retry.

These are **control-path safety tests only**. They do not show that a real CUDA
OOM recovers successfully or that a real hardware fallback occurred.

## Offline validation

The focused suite is:

```text
pytest -q tests/test_p08_a03_offline.py
```

It uses a synthetic fixture with deliberately different output hashes. The
fixture is not hardware evidence and its profile hashes are synthetic.

## Remaining unverified / limitations

- No real three-run inference, model load, CUDA execution or output exists yet.
- No real OOM/termination fallback was provoked; simulated control paths are not
  proof of CUDA recovery.
- One laptop model and one segmentation profile only; not a broader compatibility
  claim.
- Output determinism is unknown and is not required by the contract.
- The real runtime runner and private evidence remain under separate hardware
  authorization.

## Authorization request

Owner authorization is requested for **one** session with **one** startup and
**at most three** identical prompts, under the thresholds and stop conditions
above, with no retry and no fourth prompt. Any failure ends the session and is
reported with evidence rather than retried.

Until that grant and an independently reviewed evidence PR exist, P08-A03 stays
**blocked** and the atomic tracker remains **21/73 (28.77%)**.

[![](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)
