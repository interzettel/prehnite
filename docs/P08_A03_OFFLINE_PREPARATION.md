# P08-A03 offline preparation — repeated local inference

**Status:** preparation only; **P08-A03 remains blocked**

**Hardware execution:** not authorized and not performed

**Progress:** This originally belonged to the frozen v1 atomic register (historical snapshot: 21/73). The [single active v2 roadmap](../progress/roadmap.json) keeps the physical repeatability benchmark unverified; no completion credit is requested.

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
- startup limit **120 s**, per-run limit **300 s**, cleanup limit **60 s**;
- **total workload limit 900 s, measured from startup start through cleanup
  finish; it therefore includes the startup, all three runs and cleanup**;
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
fails closed unless the complete evidence bundle satisfies every measured limit.

## Evidence contract

### Measured preflight

`preflight.status` must be `pass`, and `preflight.samples` must contain at least
one typed observation. Every sample must provide finite numeric:

- `available_ram_mib` ≥ **6,000**;
- `system_commit_percent` ≤ **80**;
- `free_vram_mib` ≥ **5,000**.

A reported pass with an unsafe or missing measurement is rejected. Booleans,
strings, negatives, NaN and infinity are invalid; values are not coerced from
defaults.

### Startup receipt

The startup object must record exactly one supervised startup (`count: 1`,
`supervised: true`), `ready: true`, timezone-aware `started_at`/`finished_at`,
`elapsed_seconds` ≤ **120**, explicit `prompts_submitted_before_ready: 0`, and
`required_nodes_present: true`. Timestamps must be chronologically consistent
with the reported duration.

### Three runs

Exactly three run records are required, with ordered `run_index` values `1..3`.
Each must record:

- the identical profile digest;
- a unique prompt id and `retry_count: 0`;
- timezone-aware start/finish timestamps and a matching latency ≤ **300 s**;
- finite sampled peak VRAM, minimum free VRAM, minimum available RAM and maximum
  commit;
- `status: success`, an explicit null/empty `cuda_error`, and `cleanup_ok: true`;
- a unique output path and a 64-character SHA256 declaration.

Missing `retry_count`, a missing CUDA field, duplicate/reordered indexes, reversed
or naive timestamps, booleans in numeric fields, NaN/infinity and a fourth run are
all rejected.

### Cleanup and total workload

Cleanup must include timezone-aware `started_at`/`finished_at`,
`elapsed_seconds` ≤ **60 s**, an empty `remaining_processes` list,
`listener_open: false`, `cache_removed: true`, and
`environment_restored: true`. Its start must follow the final run.

The observed total workload is computed from startup start to cleanup finish and
must be ≤ **900 s**. This explicitly includes startup, the three runs and cleanup.

### Hash provenance

A SHA256-shaped string is not proof that a file was rehashed. Evidence must
declare:

- `integrity.profile_hashes` and `integrity.output_hashes` provenance;
- declared/unverified/synthetic provenance is not accepted as verified evidence;
- `operator_measured` is accepted as operator-reported, not independently
  verified;
- an `independently_rehashed` declaration requires an independent manifest
  declaration, but the public offline validator still reports
  `independently_verified: false` because it cannot access or rehash private
  bytes.

The bundle must also declare `evidence_origin`. A `synthetic_fixture` can validate
the schema/control path but is **never hardware-acceptance eligible**. A
`real_hardware_run` requires a separate `real_run_attestation` (operator, unique
receipt id, private-evidence SHA256 and aware attestation timestamp); even then
the public validator reports the hashes as operator-reported, not independently
rehashed.

The synthetic fixture is a schema/control-path fixture only. It is not hardware
evidence and is ineligible for hardware acceptance.

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
- corrupt output hash;
- incomplete cleanup, listener, cache removal and environment restoration;
- exactly three runs, no fourth run and no retry;
- equality and one-unit-beyond tests for every resource threshold and clock
  ceiling;
- missing-field/default, boolean/NaN/infinity, chronology and integrity
  provenance cases.

These are **control-path safety tests only**. They do not show that a real CUDA
OOM recovers successfully or that a real hardware fallback occurred.

## Offline validation

```text
pytest -q tests/test_p08_a03_offline.py
```

The current focused suite has **98 tests**, plus a synthetic fixture whose output
hashes intentionally differ. The fixture does not contain real hardware results;
its validator verdict is explicitly hardware-ineligible.

## Remaining unverified / limitations

- No real three-run inference, model load, CUDA execution or output exists yet.
- No real OOM/termination fallback was provoked; simulated control paths are not
  proof of CUDA recovery.
- One laptop model and one segmentation profile only; not a broader compatibility
  claim.
- Output determinism is unknown and is not required by the contract.
- Operator-reported hashes require separate private-byte rehashing for independent
  artifact-integrity acceptance.
- The real runtime runner and private evidence remain under separate hardware
  authorization.

## Authorization request

Owner authorization is requested for **one** session with **one** startup and
**at most three** identical prompts, under the thresholds and stop conditions
above, with no retry and no fourth prompt. Any failure ends the session and is
reported with evidence rather than retried.

Until that grant and independently reviewed physical evidence exist, the P08-A03 **historical criterion remains unverified** and the v2 [8 GiB reproducible baseline (P1-M02)](progress/STATUS.md) remains **unverified**. The archived [21/73 v1 atomic snapshot](../progress/archive/v1/atomic.json) is read-only, not an active product completion score.

[![](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)
