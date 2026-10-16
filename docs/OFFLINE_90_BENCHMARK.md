# 90-slot offline production benchmark

**Issue:** [#41](https://github.com/interzettel/prehnite/issues/41) · **Type:** reproducible integration/dry-run evidence · **Not:** a real-model quality or provider-billing benchmark.

The zero-cost benchmark exercises the **complete synthetic pipeline** from a 90-slot manifest to accepted images, named cutouts, an offline gallery, journal recovery, provenance and ZIP integrity. It runs on Ubuntu and Windows GitHub Actions using no keys, external images, model downloads, cloud providers, GPU or paid inference. Data are disposed from a temporary directory after each run; a sanitized JSON results summary is uploaded as a CI artifact.

## Execute

From the repository root with Python 3.11+ and the package installed:

```bash
python scripts/offline_90_benchmark.py --result-file benchmark-90.json
```

The script deliberately terminates a **child** Python worker with `os._exit(73)` during crash injection. The parent process itself remains running, resumes the journal and verifies the delivered archive. It asserts all invariants and exits nonzero on any violation; the JSON result is only written following a successful exercise. The script is intended to run locally and on CI, not against live API profiles.

## Fixed deterministic workload

| Requirement | Fixture |
| --- | --- |
| Distinct required asset slots | 90 |
| Preexisting local images | 60 (synthetically generated with Pillow) |
| Demo-generated images | 30 (built-in synthetic provider, never generative model) |
| Requested named cutouts | 18 (simple synthetic ellipse masks) |
| Aspect ratios | 1:1, 3:4, 9:16, 16:9, 4:3 |
| Final pixel dimensions | 128×128, 144×192, 108×192, 192×108, 192×144 |
| Remote calls / inference charges | 0 |
| Quality | Technical checks only, explicit `accept_unverified`; no human verification |

These compact pixel dimensions keep CI bounded: **no 4K photorealistic quality is tested** here.

## Execution sequence and invariants

1. Stage 60 synthetic RGB inputs, a versioned 90-slot YAML manifest and a no-spend demo profile inside the MCP manager's allowlisted home.
2. Launch using the same persisted token and journal contract as MCP `submit_batch`, while replacing only the subprocess spawn with a deterministic local harness. Inject an error for slot 010; assert the error is reported, not accepted. Request `pause` after slot 030. Verify exactly 30 recorded slots, 29 accepted, one error and persisted `paused` status.
3. Explicitly `resume` with a new token. A *genuine child process* reruns failed slot 010 and continues to slot 065, then `os._exit(73)` before slot 066. The manager must report `interrupted` using OS-lock evidence, not stale PID files.
4. Explicitly resume again. The remaining slots must finish; previously accepted outputs/stages must be reused without duplicated stage reservations or attempts. Assert exactly 90 accepted slots and 18 named cutouts.
5. Verify selected ZIP contents: **108 image entries**, SHA256 receipt for every included ZIP entry, CRC validation, stable sorted archive order and a provenance record covering all 90 slots.
6. Reopen the same batch in direct CLI mode (a *new* engine instance), rerun, and require zero new attempts and **byte-identical ZIP**.
7. Write a compact, machine-readable, provider-independent `benchmark-90.json`. Never call fake model rates actual invoices.

**Accounting caveat:** the one injected slot error occurs before stage dispatch, so a successful replay should not be counted as a new provider attempt. The 30 demo generations and 18 demo segmentations are actually observed stage operations, not 90 paid inference calls.

## Hypothetical cost scenarios

Results include independent illustrative USD arithmetic, deliberately *not* provider quotations. These assume **33** generated images (30 initial plus 10% extra attempts) and **18** segmentation calls; no judge, upscaler, hardware, labor, taxes or provider extras. They do not claim the synthetic fixture cost money.

| Scenario | Assumed USD per generation | Per segmentation | Projected total |
| --- | ---: | ---: | ---: |
| Low | $0.020 | $0.003 | **$0.714** |
| Mid | $0.050 | $0.010 | **$1.830** |
| High | $0.100 | $0.025 | **$3.750** |

Compare actual image/model provider rates only after #17 quote sourcing and separately authorized live pilots. Never substitute estimated reserves for invoice reconciliation.

## Limitations and next gates

- This is a *failure-handling and delivery* exercise; synthetic images and ellipse masks do not establish photorealism, alpha quality on hair/glass/fur, prompt fidelity, calibrated judges or acceptable production aesthetics.
- The crash is local worker termination and cannot establish real remote provider queue status or invoice reconciliation.
- The exercise verifies selected artifact replay under controlled, unchanged manifests; changing inputs or a provider configuration must continue to fail closed.
- See #24 (RTX 4070 laptop model performance), #28 (human judge calibration), #32 (difficult cutouts), #17 (real charges) and #42 (owner-accepted live production).
- The separately scoped `C08` work unit covers a **local Windows 90-item interrupted execution** on the owner's computer and remains pending unless that evidence is recorded. GitHub Actions Windows runs verify CI runner behavior, not the owner's RTX machine.

All individual run evidence must link to a real CI workflow run and the archived JSON, not to hand-written illustrations.
