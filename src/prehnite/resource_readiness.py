"""Read-only, fail-closed resource observations; never permission to launch models."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

MIB = 1024 * 1024


@dataclass(frozen=True)
class ReadinessPolicy:
    """Explicit operator thresholds; no universal model-safety defaults."""

    min_available_ram_mib: int
    max_commit_percent: float
    min_free_vram_mib: int
    gpu_index: int = 0

    def __post_init__(self) -> None:
        if type(self.min_available_ram_mib) is not int or self.min_available_ram_mib <= 0:
            raise ValueError("min_available_ram_mib must be a positive integer")
        if (not isinstance(self.max_commit_percent, (int, float))
                or isinstance(self.max_commit_percent, bool)
                or not math.isfinite(self.max_commit_percent)
                or not 0 < self.max_commit_percent < 100):
            raise ValueError("max_commit_percent must be strictly between 0 and 100")
        if type(self.min_free_vram_mib) is not int or self.min_free_vram_mib < 0:
            raise ValueError("min_free_vram_mib must be a nonnegative integer")
        if type(self.gpu_index) is not int or self.gpu_index < 0:
            raise ValueError("gpu_index must be a nonnegative integer")


def _byte_count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _check(measured: int | float | None, minimum: int | None = None,
           maximum: float | None = None) -> str:
    if measured is None:
        return "unknown"
    if minimum is not None and measured < minimum:
        return "blocked"
    if maximum is not None and measured > maximum:
        return "blocked"
    return "pass"


def evaluate_readiness(snapshots: Sequence[Mapping[str, Any]],
                       policy: ReadinessPolicy) -> dict[str, Any]:
    """Assess already observed snapshots; never probe, launch, spend, or retry.

    Every snapshot must pass each check. Unknown telemetry fails closed. A pass
    describes sampled resources only; it is not a launch or inference approval.
    """
    if not snapshots:
        raise ValueError("At least one observation is required")
    samples: list[dict[str, Any]] = []
    for index, snapshot in enumerate(snapshots, start=1):
        ram = snapshot.get("ram", {})
        if not isinstance(ram, Mapping):
            ram = {}
        available = (_byte_count(ram.get("available_bytes"))
                     if ram.get("status") == "observed" else None)
        commit_limit = (_byte_count(ram.get("commit_limit_bytes"))
                        if ram.get("commit_status") == "observed" else None)
        committed = (_byte_count(ram.get("commit_used_bytes"))
                     if ram.get("commit_status") == "observed" else None)
        commit_pct: float | None = None
        if (commit_limit is not None and commit_limit > 0
                and committed is not None and committed <= commit_limit):
            commit_pct = 100 * committed / commit_limit

        accelerators = snapshot.get("accelerators", {})
        nvidia = accelerators.get("nvidia", {}) if isinstance(accelerators, Mapping) else {}
        devices = nvidia.get("devices", []) if isinstance(nvidia, Mapping) else []
        gpu = None
        if isinstance(devices, list):
            gpu = next((d for d in devices if isinstance(d, Mapping)
                        and d.get("index") == policy.gpu_index), None)
        free_vram = (_byte_count(gpu.get("vram_free_bytes"))
                     if gpu is not None and gpu.get("vram_status") == "observed" else None)
        if (not isinstance(nvidia, Mapping)
                or nvidia.get("status") != "observed"):
            free_vram = None

        checks = {
            "available_ram": _check(available, policy.min_available_ram_mib * MIB),
            "system_commit": _check(commit_pct, maximum=policy.max_commit_percent),
            "free_vram": _check(free_vram, policy.min_free_vram_mib * MIB),
        }
        samples.append({
            "sample": index,
            "available_ram_bytes": available,
            "system_commit_percent": round(commit_pct, 3) if commit_pct is not None else None,
            "free_vram_bytes": free_vram,
            "checks": checks,
            "source": {
                "ram": ram.get("source"),
                "commit": (ram.get("commit_source")
                           if ram.get("commit_status") == "observed" else None),
                "vram": nvidia.get("source") if isinstance(nvidia, Mapping) else None,
            },
        })
    failures = [{"sample": s["sample"], "check": name} for s in samples
                for name, status in s["checks"].items() if status == "blocked"]
    missing = [{"sample": s["sample"], "check": name} for s in samples
               for name, status in s["checks"].items() if status == "unknown"]
    status = "blocked" if failures else "unknown" if missing else "pass"
    return {
        "schema_version": 1,
        "kind": "resource_readiness_observation",
        "status": status,
        "policy": {
            "min_available_ram_mib": policy.min_available_ram_mib,
            "max_commit_percent": policy.max_commit_percent,
            "min_free_vram_mib": policy.min_free_vram_mib,
            "gpu_index": policy.gpu_index,
        },
        "sample_count": len(samples),
        "samples": samples,
        "blocked_checks": failures,
        "unknown_checks": missing,
        "startup_authorized": False,
        "model_compatibility": "not_assessed",
        "technical_execution": "not_started",
        "visual_acceptance": "not_assessed",
        "confirmation": (
            "Observations only. A passing sample does not authorize startup or inference."
        ),
    }
