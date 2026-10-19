"""Fail-closed evidence contract for the P08-A03 repeated-inference experiment.

This module is deliberately offline and hardware-free. It defines the proposed
three-run experiment, validates a complete evidence bundle, and models the
control path for preflight/startup/inference failures. It cannot launch
ComfyUI, import Torch/CUDA, submit a prompt or inspect GPU state.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = 1
EXPERIMENT_ID = "P08-A03"
EXPECTED_RUNS = 3
MAX_ATTEMPTS = 3
PROFILE_FIELDS = (
    "profile_id",
    "model_sha256",
    "workflow_sha256",
    "input_sha256",
    "parameters_sha256",
    "target",
)
REQUIRED_NODE_TYPES = (
    "SAM2ModelLoader (segment anything2)",
    "GroundingDinoModelLoader (segment anything2)",
    "GroundingDinoSAM2Segment (segment anything2)",
    "LoadImage",
    "MaskToImage",
    "SaveImage",
)
PREFLIGHT_LIMITS = {
    "min_available_ram_mib": 6000,
    "max_commit_percent": 80,
    "min_free_vram_mib": 5000,
}
STARTUP_LIMIT_SECONDS = 120
RUN_LIMIT_SECONDS = 300
TOTAL_WORKLOAD_LIMIT_SECONDS = 900
CLEANUP_LIMIT_SECONDS = 60
DURATION_TOLERANCE_SECONDS = 1.5
RUN_STATUSES = frozenset({"success", "failed", "terminated", "unknown"})
EVIDENCE_ORIGINS = frozenset({"real_hardware_run", "synthetic_fixture"})
HASH_PROVENANCE = frozenset({
    "declared",
    "operator_measured",
    "independently_rehashed",
    "unverified",
    "synthetic",
})
TRUSTED_HASH_PROVENANCE = frozenset({"operator_measured", "independently_rehashed"})
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical_digest(payload: Mapping[str, Any]) -> str:
    """Stable SHA256 over a JSON object; no whitespace or key-order variance."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def profile_digest(profile: Mapping[str, Any]) -> str:
    missing = [name for name in PROFILE_FIELDS if not profile.get(name)]
    if missing:
        raise ValueError(f"profile missing fields: {missing}")
    return canonical_digest({name: profile[name] for name in PROFILE_FIELDS})


def _number(value: Any, *, allow_zero: bool = True) -> float | None:
    """Return a finite non-negative number; reject bools, strings, NaN and inf."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        return None
    if not allow_zero and number == 0:
        return None
    return number


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp only when it carries an explicit timezone."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _duration_matches(reported: float, start: datetime, finish: datetime) -> bool:
    observed = (finish - start).total_seconds()
    return observed >= 0 and abs(reported - observed) <= DURATION_TOLERANCE_SECONDS


def classify_run_failure(run: Mapping[str, Any]) -> str:
    """Map an observed run outcome to a stable, non-duplicating failure code."""
    cuda_error = str(run.get("cuda_error") or "").lower()
    if "out of memory" in cuda_error or "cuda oom" in cuda_error or "oom" in cuda_error:
        return "cuda_oom"
    if run.get("status") == "terminated":
        return "process_terminated"
    if run.get("status") == "unknown":
        return "unknown_outcome"
    supplied = run.get("failure_code")
    if isinstance(supplied, str) and supplied.strip():
        return supplied.strip()
    return "inference_failed"


def _blocked(code: str, detail: str, *, prompts: int = 0) -> dict[str, Any]:
    return {
        "verdict": "blocked",
        "failure_code": code,
        "detail": detail,
        "prompts_submitted": prompts,
        "acceptance": "not_met",
        "fallback_required": True,
    }


def _incomplete(errors: list[str]) -> dict[str, Any]:
    return {
        "verdict": "incomplete",
        "errors": errors,
        "acceptance": "not_met",
        "fallback_required": True,
    }


def _validate_origin(data: Mapping[str, Any]) -> dict[str, Any] | None:
    origin = data.get("evidence_origin")
    if origin not in EVIDENCE_ORIGINS:
        return _incomplete([
            "evidence_origin must be real_hardware_run or synthetic_fixture"
        ])
    if origin == "synthetic_fixture":
        return None
    attestation = data.get("real_run_attestation")
    if not isinstance(attestation, Mapping):
        return _incomplete([
            "real_run_attestation is required for real_hardware_run evidence"
        ])
    if not (isinstance(attestation.get("operator"), str) and attestation["operator"].strip()):
        return _incomplete(["real_run_attestation.operator is required"])
    if not (isinstance(attestation.get("receipt_id"), str)
            and attestation["receipt_id"].strip()):
        return _incomplete(["real_run_attestation.receipt_id is required"])
    if not _HEX64.fullmatch(str(attestation.get("private_evidence_sha256") or "")):
        return _incomplete([
            "real_run_attestation.private_evidence_sha256 is invalid"
        ])
    if not _timestamp(attestation.get("attested_at")):
        return _incomplete(["real_run_attestation.attested_at is invalid"])
    return None


def _validate_integrity(data: Mapping[str, Any]) -> dict[str, Any] | None:
    integrity = data.get("integrity")
    if not isinstance(integrity, Mapping):
        return _incomplete(["integrity must be an object"])
    profile_provenance = integrity.get("profile_hashes")
    output_provenance = integrity.get("output_hashes")
    if profile_provenance not in HASH_PROVENANCE:
        return _incomplete(["integrity.profile_hashes is missing or invalid"])
    if output_provenance not in HASH_PROVENANCE:
        return _incomplete(["integrity.output_hashes is missing or invalid"])
    if profile_provenance not in TRUSTED_HASH_PROVENANCE:
        return _incomplete([
            "integrity.profile_hashes must be operator_measured or independently_rehashed"
        ])
    if output_provenance not in TRUSTED_HASH_PROVENANCE:
        return _incomplete([
            "integrity.output_hashes must be operator_measured or independently_rehashed"
        ])
    if output_provenance == "independently_rehashed":
        manifest = integrity.get("independent_rehash_manifest")
        if not isinstance(manifest, Mapping):
            return _incomplete(["independent_rehash_manifest is required"])
        if not (isinstance(manifest.get("verifier"), str) and manifest["verifier"].strip()):
            return _incomplete(["independent_rehash_manifest.verifier is required"])
        if not _HEX64.fullmatch(str(manifest.get("manifest_sha256") or "")):
            return _incomplete(["independent_rehash_manifest.manifest_sha256 is invalid"])
        if not _timestamp(manifest.get("verified_at")):
            return _incomplete(["independent_rehash_manifest.verified_at is invalid"])
    return None


def validate_evidence(data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a complete P08-A03 evidence object.

    A pass requires one successful supervised startup and three successful runs
    with one identical profile, measured preflight samples inside the floors,
    observed durations inside every ceiling, no retries/duplicates, distinct
    output paths and complete cleanup. Hash strings are never treated as proof
    of independently rehashed private bytes.
    """
    if not isinstance(data, Mapping):
        return _incomplete(["evidence must be a JSON object"])
    if data.get("schema_version") != SCHEMA_VERSION:
        return _incomplete([f"schema_version must be {SCHEMA_VERSION}"])
    if data.get("experiment") != EXPERIMENT_ID:
        return _incomplete([f"experiment must be {EXPERIMENT_ID}"])

    profile = data.get("profile")
    if not isinstance(profile, Mapping):
        return _incomplete(["profile must be an object"])
    try:
        digest = profile_digest(profile)
    except (TypeError, ValueError) as exc:
        return _incomplete([str(exc)])
    for name in ("model_sha256", "workflow_sha256", "input_sha256", "parameters_sha256"):
        if not _HEX64.fullmatch(str(profile.get(name, ""))):
            return _incomplete([f"{name} must be 64 lowercase hex characters"])

    origin_error = _validate_origin(data)
    if origin_error is not None:
        return origin_error

    integrity_error = _validate_integrity(data)
    if integrity_error is not None:
        return integrity_error

    preflight = data.get("preflight")
    if not isinstance(preflight, Mapping):
        return _incomplete(["preflight must be an object"])
    if preflight.get("status") != "pass":
        checks = preflight.get("blocked_checks") or []
        detail = "preflight did not pass"
        if checks:
            detail = f"preflight blocked: {checks}"
        return _blocked("insufficient_resources", detail)
    samples = preflight.get("samples")
    if not isinstance(samples, list) or not samples:
        return _incomplete(["preflight.samples must contain measured observations"])
    for position, sample in enumerate(samples, start=1):
        if not isinstance(sample, Mapping):
            return _incomplete([f"preflight sample {position} must be an object"])
        ram = _number(sample.get("available_ram_mib"))
        commit = _number(sample.get("system_commit_percent"))
        vram = _number(sample.get("free_vram_mib"))
        if ram is None or commit is None or vram is None:
            return _incomplete([f"preflight sample {position} has invalid measurements"])
        if ram < PREFLIGHT_LIMITS["min_available_ram_mib"]:
            return _blocked(
                "insufficient_resources",
                f"preflight sample {position} available RAM below floor",
            )
        if commit > PREFLIGHT_LIMITS["max_commit_percent"]:
            return _blocked(
                "insufficient_resources",
                f"preflight sample {position} commit above ceiling",
            )
        if vram < PREFLIGHT_LIMITS["min_free_vram_mib"]:
            return _blocked(
                "insufficient_resources",
                f"preflight sample {position} free VRAM below floor",
            )

    startup = data.get("startup")
    if not isinstance(startup, Mapping):
        return _incomplete(["startup must be an object"])
    startup_count = _integer(startup.get("count"))
    if startup_count != 1:
        return _blocked("startup_count_invalid", "exactly one supervised startup is required")
    if startup.get("supervised") is not True:
        return _blocked("startup_not_supervised", "startup supervision is required")
    if startup.get("ready") is not True:
        reason = startup.get("reason")
        if reason is None:
            return _incomplete(["startup.reason is required when not ready"])
        reason_text = str(reason).strip().lower()
        code = "startup_timeout" if "timeout" in reason_text else "startup_failed"
        return _blocked(code, f"startup did not become ready: {reason_text}")
    startup_start = _timestamp(startup.get("started_at"))
    startup_finish = _timestamp(startup.get("finished_at"))
    startup_elapsed = _number(startup.get("elapsed_seconds"), allow_zero=False)
    if startup_start is None or startup_finish is None or startup_elapsed is None:
        return _incomplete(["startup timestamps/elapsed_seconds are required and valid"])
    if startup_finish < startup_start:
        return _incomplete(["startup timestamps are reversed"])
    if not _duration_matches(startup_elapsed, startup_start, startup_finish):
        return _incomplete(["startup.elapsed_seconds does not match timestamps"])
    if startup_elapsed > STARTUP_LIMIT_SECONDS:
        return _blocked("startup_limit_exceeded", "startup exceeded 120 seconds")
    before_ready = _integer(startup.get("prompts_submitted_before_ready"))
    if before_ready is None:
        return _incomplete(["startup.prompts_submitted_before_ready is required"])
    if before_ready != 0:
        return _blocked("startup_contract_violation", "prompt submitted before readiness")
    if startup.get("required_nodes_present") is not True:
        return _blocked("required_nodes_missing", "required segmentation nodes unavailable")

    runs = data.get("runs")
    if not isinstance(runs, list) or len(runs) != EXPECTED_RUNS:
        return _blocked(
            "incorrect_run_count",
            f"expected exactly {EXPECTED_RUNS} runs; observed {len(runs) if isinstance(runs, list) else 'invalid'}",
        )

    prompt_ids: set[str] = set()
    output_paths: dict[str, str] = {}
    previous_finish = startup_finish
    for position, run in enumerate(runs, start=1):
        if not isinstance(run, Mapping):
            return _incomplete([f"run {position} must be an object"])
        index = _integer(run.get("run_index"))
        if index != position:
            return _incomplete([f"run {position} must have run_index {position}"])
        if run.get("profile_digest") != digest:
            return _blocked("profile_mismatch", f"run {position} profile digest differs")
        retry_count = _integer(run.get("retry_count"))
        if retry_count is None:
            return _incomplete([f"run {position} retry_count is required"])
        if retry_count != 0:
            return _blocked("retry_attempted", f"run {position} reports a retry")
        prompt_id = run.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id.strip():
            return _incomplete([f"run {position} has no prompt_id"])
        if prompt_id in prompt_ids:
            return _blocked("duplicate_prompt", f"run {position} reuses a prompt id")
        prompt_ids.add(prompt_id)
        run_start = _timestamp(run.get("started_at"))
        run_finish = _timestamp(run.get("finished_at"))
        latency = _number(run.get("latency_seconds"), allow_zero=False)
        if run_start is None or run_finish is None or latency is None:
            return _incomplete([f"run {position} timestamps/latency are invalid"])
        if run_finish < run_start or run_start < previous_finish:
            return _incomplete([f"run {position} chronology is invalid"])
        if not _duration_matches(latency, run_start, run_finish):
            return _incomplete([f"run {position} latency does not match timestamps"])
        if latency > RUN_LIMIT_SECONDS:
            return _blocked("run_limit_exceeded", f"run {position} exceeded 300 seconds")
        for metric in ("peak_vram_mib", "min_free_vram_mib",
                       "min_available_ram_mib", "max_commit_percent"):
            if _number(run.get(metric)) is None:
                return _incomplete([f"run {position} {metric} is invalid"])
        status = run.get("status")
        if status not in RUN_STATUSES:
            return _incomplete([f"run {position} status is invalid"])
        if status != "success":
            return _blocked(
                classify_run_failure(run),
                f"run {position} did not complete successfully",
                prompts=position,
            )
        if "cuda_error" not in run:
            return _incomplete([f"run {position} cuda_error field is required"])
        if run.get("cuda_error"):
            return _blocked(
                "cuda_error", f"run {position} reports a CUDA error", prompts=position
            )
        if run.get("cleanup_ok") is not True:
            return _blocked("cleanup_incomplete", f"run {position} cleanup not proven")
        output_path = run.get("output_path")
        output_hash = run.get("output_sha256")
        if not isinstance(output_path, str) or not output_path.strip():
            return _incomplete([f"run {position} has no output_path"])
        if not _HEX64.fullmatch(str(output_hash or "")):
            return _incomplete([f"run {position} output_sha256 is invalid"])
        if output_path in output_paths:
            return _blocked(
                "artifact_overwrite",
                f"run {position} reuses an output path with hash {output_hash}",
            )
        output_paths[output_path] = str(output_hash)
        previous_finish = run_finish

    cleanup = data.get("cleanup")
    if not isinstance(cleanup, Mapping):
        return _incomplete(["cleanup must be an object"])
    cleanup_start = _timestamp(cleanup.get("started_at"))
    cleanup_finish = _timestamp(cleanup.get("finished_at"))
    cleanup_elapsed = _number(cleanup.get("elapsed_seconds"), allow_zero=False)
    if cleanup_start is None or cleanup_finish is None or cleanup_elapsed is None:
        return _incomplete(["cleanup timestamps/elapsed_seconds are required and valid"])
    if cleanup_finish < cleanup_start or cleanup_start < previous_finish:
        return _incomplete(["cleanup chronology is invalid"])
    if not _duration_matches(cleanup_elapsed, cleanup_start, cleanup_finish):
        return _incomplete(["cleanup.elapsed_seconds does not match timestamps"])
    if cleanup_elapsed > CLEANUP_LIMIT_SECONDS:
        return _blocked("cleanup_limit_exceeded", "cleanup exceeded 60 seconds")
    if "remaining_processes" not in cleanup:
        return _incomplete(["cleanup.remaining_processes is required"])
    remaining = cleanup["remaining_processes"]
    if not isinstance(remaining, list) or remaining:
        return _blocked(
            "cleanup_incomplete", "owned processes remain", prompts=EXPECTED_RUNS
        )
    for name in ("listener_open", "cache_removed", "environment_restored"):
        if name not in cleanup:
            return _incomplete([f"cleanup.{name} is required"])
    if cleanup["listener_open"] is not False:
        return _blocked(
            "cleanup_incomplete", "listener still open", prompts=EXPECTED_RUNS
        )
    if cleanup["cache_removed"] is not True:
        return _blocked(
            "cleanup_incomplete", "disposable cache removal not proven",
            prompts=EXPECTED_RUNS,
        )
    if cleanup["environment_restored"] is not True:
        return _blocked(
            "cleanup_incomplete", "child environment restoration not proven",
            prompts=EXPECTED_RUNS,
        )

    total_workload = (cleanup_finish - startup_start).total_seconds()
    if total_workload > TOTAL_WORKLOAD_LIMIT_SECONDS:
        return _blocked("workload_limit_exceeded", "total workload exceeded 900 seconds")
    if total_workload <= 0:
        return _incomplete(["total workload timestamps are inconsistent"])

    origin = data["evidence_origin"]
    return {
        "verdict": "pass",
        "evidence_origin": origin,
        "hardware_acceptance_eligible": origin == "real_hardware_run",
        "profile_digest": digest,
        "run_count": EXPECTED_RUNS,
        "prompts_submitted": EXPECTED_RUNS,
        "outputs_distinct": len(output_paths) == EXPECTED_RUNS,
        "startup_count": 1,
        "observed_total_workload_seconds": round(total_workload, 3),
        "total_workload_includes": ["startup", "three_runs", "cleanup"],
        "integrity": {
            "profile_hashes": data["integrity"]["profile_hashes"],
            "output_hashes": data["integrity"]["output_hashes"],
            "independently_verified": False,
            "note": (
                "Public validator checks provenance declarations only; private bytes "
                "must be independently rehashed separately."
            ),
        },
        "acceptance": (
            "3-run identical profile evidence and fallback path (operator-reported)"
            if origin == "real_hardware_run"
            else "offline contract fixture only; not hardware acceptance"
        ),
        "fallback_required": False,
        "note": "Observed evidence only; sampled peak VRAM is not an absolute peak.",
    }


@dataclass
class RunController:
    """No-retry, no-duplicate, no-overwrite control path for a future run."""

    max_runs: int = EXPECTED_RUNS
    runs: list[dict[str, Any]] = field(default_factory=list)
    prompt_ids: set[str] = field(default_factory=set)
    output_paths: dict[str, str] = field(default_factory=dict)
    stopped: bool = False
    stop_code: str | None = None

    def _stop(self, code: str) -> None:
        self.stopped = True
        self.stop_code = code

    @property
    def can_start(self) -> bool:
        return not self.stopped and len(self.runs) < self.max_runs

    def record(self, run: Mapping[str, Any]) -> bool:
        """Record one already-observed attempt; never submits or retries it."""
        if not self.can_start:
            return False
        prompt_id = str(run.get("prompt_id") or "").strip()
        if not prompt_id or prompt_id in self.prompt_ids:
            self._stop("duplicate_prompt")
            return False
        output_path = str(run.get("output_path") or "").strip()
        output_hash = str(run.get("output_sha256") or "").strip()
        if output_path and output_path in self.output_paths:
            self._stop("artifact_overwrite")
            return False
        status = run.get("status")
        if status not in RUN_STATUSES:
            self._stop("invalid_run_status")
            return False
        if output_path:
            self.output_paths[output_path] = output_hash
        self.prompt_ids.add(prompt_id)
        self.runs.append(dict(run))
        if status != "success":
            self._stop(classify_run_failure(run))
        return True


def experiment_plan() -> dict[str, Any]:
    """The exact bounded experiment proposed for separate owner authorization."""
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": EXPERIMENT_ID,
        "status": "preparation_only_not_authorized",
        "hardware": {
            "startup_limit_seconds": STARTUP_LIMIT_SECONDS,
            "max_startups": 1,
            "max_runs": EXPECTED_RUNS,
            "max_attempts": MAX_ATTEMPTS,
            "retries": 0,
            "per_run_limit_seconds": RUN_LIMIT_SECONDS,
            "total_workload_limit_seconds": TOTAL_WORKLOAD_LIMIT_SECONDS,
            "total_workload_includes": ["startup", "three_runs", "cleanup"],
            "cleanup_limit_seconds": CLEANUP_LIMIT_SECONDS,
        },
        "preflight": dict(PREFLIGHT_LIMITS),
        "integrity": {
            "required_provenance": "operator_measured",
            "independently_verified": False,
            "private_rehash_required_for_independent_acceptance": True,
        },
        "evidence_origin": {
            "synthetic_fixture_hardware_eligible": False,
            "real_hardware_run_requires_attestation": True,
        },
        "profile": {
            "identical_for_all_runs": True,
            "required_fields": list(PROFILE_FIELDS),
            "required_nodes": list(REQUIRED_NODE_TYPES),
            "deterministic_output_required": False,
            "sampled_peak_is_absolute_peak": False,
        },
        "telemetry": [
            "prompt_id",
            "started_at",
            "finished_at",
            "latency_seconds",
            "peak_vram_mib",
            "min_free_vram_mib",
            "min_available_ram_mib",
            "max_commit_percent",
            "output_path",
            "output_sha256",
            "status",
            "cuda_error",
            "cleanup_ok",
        ],
        "stop_conditions": [
            "preflight does not pass or a measured floor is violated",
            "disposable YAPF cache validation fails",
            "startup timeout or readiness failure",
            "more than one startup or missing supervision receipt",
            "required segmentation nodes absent",
            "any run fails, terminates, reports CUDA/OOM, or has unknown outcome",
            "duplicate prompt id or reused output path",
            "cleanup incomplete, listener open, or resources remain",
            "startup/run/cleanup/workload limit exceeded",
            "owner interrupt",
        ],
        "cleanup": {
            "one_supervised_startup": True,
            "stop_after_three_successes": True,
            "no_automatic_duplicate_submission": True,
            "remove_child_scoped_disposable_cache": True,
            "preserve_public_and_historical_evidence": True,
        },
        "limitations": [
            "Simulated fallback is control-path evidence, not a real CUDA OOM recovery.",
            "Three successful runs are required before any fallback interpretation.",
            "One laptop and one profile only; this is not a general compatibility claim.",
            "Output hashes may differ unless determinism is separately established.",
            "Public validator cannot independently rehash private bytes.",
        ],
    }


def simulated_fallback_scenarios() -> list[dict[str, Any]]:
    """Deterministic descriptions of failure paths; no hardware is touched."""
    return [
        {"scenario": "insufficient_ram", "stage": "preflight",
         "failure_code": "insufficient_resources", "prompts_submitted": 0,
         "startup_started": False},
        {"scenario": "insufficient_vram", "stage": "preflight",
         "failure_code": "insufficient_resources", "prompts_submitted": 0,
         "startup_started": False},
        {"scenario": "startup_timeout", "stage": "startup",
         "failure_code": "startup_timeout", "prompts_submitted": 0,
         "startup_started": True},
        {"scenario": "inference_failure", "stage": "run",
         "failure_code": "inference_failed", "prompts_submitted": 1,
         "startup_started": True},
        {"scenario": "process_termination", "stage": "run",
         "failure_code": "process_terminated", "prompts_submitted": 1,
         "startup_started": True},
        {"scenario": "unknown_outcome", "stage": "run",
         "failure_code": "unknown_outcome", "prompts_submitted": 1,
         "startup_started": True},
        {"scenario": "duplicate_prompt", "stage": "control",
         "failure_code": "duplicate_prompt", "prompts_submitted": 1,
         "startup_started": True},
        {"scenario": "artifact_overwrite", "stage": "control",
         "failure_code": "artifact_overwrite", "prompts_submitted": 1,
         "startup_started": True},
    ]
