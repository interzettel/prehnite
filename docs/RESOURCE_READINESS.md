# Resource readiness: observations, not launch authorization

Prehnite separates four concepts which must never silently substitute for one another:

1. **Resource readiness:** sampled physical RAM, Windows system-commit estimate and NVIDIA free VRAM against **operator-supplied** thresholds.
2. **Model compatibility:** versioned software and checkpoint-construction/inference checks performed separately.
3. **Technical execution:** an explicitly authorized model run, its journal, outcome and performance evidence.
4. **Visual acceptance:** independent human review of real image edges and alpha quality.

`prehnite hardware` remains the non-gating, read-only hardware snapshot. The additional **`prehnite resource-preflight`** command samples that existing hardware report and applies a specified resource policy. Neither command launches ComfyUI, reads private model files, submits `/prompt`, downloads weights, authorizes spending or changes a job journal.

Example **observation only** (operator-specific thresholds; these are *not* safe hardware defaults):

```console
prehnite resource-preflight --min-ram-mib 6000 --max-commit-percent 80 --min-vram-mib 5000 --samples 7 --interval-seconds 5
```

This captures seven snapshots over at least 30 seconds, with no user-supplied command execution. Every sample and every required measurement must pass. A single sample below a threshold returns `blocked`. Missing or inconsistent telemetry returns `unknown`; it never becomes zero or a pass. A detected block takes precedence over unknown telemetry. The command prints structured JSON, then exits nonzero for `blocked` and `unknown`.

Snapshot fields distinguish available physical memory from Windows system commit. On Windows the existing `GlobalMemoryStatusEx` probe also records `ullTotalPageFile` (commit limit) and `ullAvailPageFile` (remaining commit allowance); these are **not** dedicated pagefile disk size. Non-Windows commit telemetry is deliberately `unknown` in this initial implementation. NVIDIA free VRAM comes from `nvidia-smi` and refers to the explicitly selected GPU index, not a promise that memory will remain available. Unsupported accelerators remain unmeasured.

This **is not a runtime watchdog**: sampled preflight can change immediately. A launcher must still own and correctly track its *real child process*, continuously monitor resources during startup, stop safely on breach, honor a one-shot attempt marker, and preserve evidence. Resource thresholds must be chosen by an operator for the particular experiment; they cannot establish guaranteed model capacity or stability. Passing preflight **never creates permission for another GPU run**.

The JSON includes `startup_authorized: false`, `model_compatibility: not_assessed`, `technical_execution: not_started`, and `visual_acceptance: not_assessed` regardless of resource status. Downstream acceptance gates remain independent. See [hardware doctor](HARDWARE_DOCTOR.md), [issue #134](https://github.com/interzettel/prehnite/issues/134), [issue #136](https://github.com/interzettel/prehnite/issues/136) and the [agent handover](AGENT_HANDOVER_2026-10-18.md).
