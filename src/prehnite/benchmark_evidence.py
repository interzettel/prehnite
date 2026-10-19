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
from datetime import datetime
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
RUN_STATUSES = frozenset({"success", "failed", "terminated", "unknown"})
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


def _finite_nonnegative(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0


def _valid_iso(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


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


def validate_evidence(data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a complete P08-A03 evidence object.

    A pass requires one successful startup, exactly three successful runs with
    one identical profile digest, no retries/duplicates, distinct output paths
    and hashes, and complete cleanup. Preflight failure, startup failure, any
    run failure/termination/unknown outcome, or incomplete cleanup is blocked.
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

    preflight = data.get("preflight")
    if not isinstance(preflight, Mapping):
        return _incomplete(["preflight must be an object"])
    if preflight.get("status") != "pass":
        checks = preflight.get("blocked_checks") or []
        detail = "preflight did not pass"
        if checks:
            detail = f"preflight blocked: {checks}"
        return _blocked("insufficient_resources", detail)

    startup = data.get("startup")
    if not isinstance(startup, Mapping):
        return _incomplete(["startup must be an object"])
    if startup.get("ready") is not True:
        reason = str(startup.get("reason") or "startup_failed").strip().lower()
        code = "startup_timeout" if "timeout" in reason else "startup_failed"
        return _blocked(code, f"startup did not become ready: {reason}")
    if startup.get("prompts_submitted_before_ready", 0) != 0:
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
    run_indexes: set[int] = set()
    for position, run in enumerate(runs, start=1):
        if not isinstance(run, Mapping):
            return _incomplete([f"run {position} must be an object"])
        index = run.get("run_index")
        if not isinstance(index, int) or isinstance(index, bool) or index < 1:
            return _incomplete([f"run {position} has invalid run_index"])
        run_indexes.add(index)
        if run.get("profile_digest") != digest:
            return _blocked("profile_mismatch", f"run {position} profile digest differs")
        if run.get("retry_count", 0) != 0:
            return _blocked("retry_attempted", f"run {position} reports a retry")
        prompt_id = run.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id.strip():
            return _incomplete([f"run {position} has no prompt_id"])
        if prompt_id in prompt_ids:
            return _blocked("duplicate_prompt", f"run {position} reuses a prompt id")
        prompt_ids.add(prompt_id)
        if not _valid_iso(run.get("started_at")) or not _valid_iso(run.get("finished_at")):
            return _incomplete([f"run {position} timestamps are invalid"])
        if not _finite_nonnegative(run.get("latency_seconds")) or float(
            run["latency_seconds"]
        ) <= 0:
            return _incomplete([f"run {position} latency_seconds is invalid"])
        for metric in ("peak_vram_mib", "min_free_vram_mib",
                       "min_available_ram_mib", "max_commit_percent"):
            if not _finite_nonnegative(run.get(metric)):
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

    if run_indexes != {1, 2, 3}:
        return _incomplete([f"run indexes must be 1..{EXPECTED_RUNS}"])

    cleanup = data.get("cleanup")
    if not isinstance(cleanup, Mapping):
        return _incomplete(["cleanup must be an object"])
    remaining = cleanup.get("remaining_processes")
    if remaining not in ([], ()):
        return _blocked(
            "cleanup_incomplete", "owned processes remain", prompts=EXPECTED_RUNS
        )
    if cleanup.get("listener_open") is not False:
        return _blocked(
            "cleanup_incomplete", "listener still open", prompts=EXPECTED_RUNS
        )
    if cleanup.get("cache_removed") is not True:
        return _blocked(
            "cleanup_incomplete", "disposable cache removal not proven",
            prompts=EXPECTED_RUNS,
        )
    if cleanup.get("environment_restored") is not True:
        return _blocked(
            "cleanup_incomplete", "child environment restoration not proven",
            prompts=EXPECTED_RUNS,
        )

    return {
        "verdict": "pass",
        "profile_digest": digest,
        "run_count": EXPECTED_RUNS,
        "prompts_submitted": EXPECTED_RUNS,
        "outputs_distinct": len(output_paths) == EXPECTED_RUNS,
        "acceptance": "3-run identical profile evidence and fallback path",
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
        },
        "preflight": dict(PREFLIGHT_LIMITS),
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
            "preflight does not pass",
            "disposable YAPF cache validation fails",
            "startup timeout or readiness failure",
            "required segmentation nodes absent",
            "any run fails, terminates, reports CUDA/OOM, or has unknown outcome",
            "duplicate prompt id or reused output path",
            "cleanup incomplete, listener open, or resources remain",
            "workload budget exhausted",
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
