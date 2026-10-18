"""Deterministic resource policy checks; no hardware, network or model access."""
from __future__ import annotations

import pytest

from prehnite.resource_readiness import MIB, ReadinessPolicy, evaluate_readiness

POLICY = ReadinessPolicy(min_available_ram_mib=6000,
                         max_commit_percent=80,
                         min_free_vram_mib=5000)


def snapshot(ram=7500, used=35, limit=73, vram=7909, gpu_index=0):
    return {
        "ram": {"status": "observed", "source": "GlobalMemoryStatusEx",
                "available_bytes": ram * MIB,
                "commit_status": "observed", "commit_source": "GlobalMemoryStatusEx",
                "commit_used_bytes": used * MIB * 1024,
                "commit_limit_bytes": limit * MIB * 1024},
        "accelerators": {"nvidia": {"status": "observed", "source": "nvidia-smi",
                                    "devices": [{"index": gpu_index, "vram_status": "observed",
                                                 "vram_free_bytes": vram * MIB}]}}
    }


def test_pass_does_not_authorize_launch():
    report = evaluate_readiness([snapshot(), snapshot()], POLICY)
    assert report["status"] == "pass"
    assert report["startup_authorized"] is False
    assert report["technical_execution"] == "not_started"
    assert report["visual_acceptance"] == "not_assessed"
    assert report["sample_count"] == 2


def test_one_bad_sample_blocks_entire_window():
    report = evaluate_readiness([snapshot(), snapshot(ram=855), snapshot()], POLICY)
    assert report["status"] == "blocked"
    assert report["blocked_checks"] == [{"sample": 2, "check": "available_ram"}]


def test_over_commit_limit_blocks():
    report = evaluate_readiness([snapshot(used=65, limit=73)], POLICY)
    assert report["status"] == "blocked"
    assert report["blocked_checks"][0]["check"] == "system_commit"


def test_missing_commit_unknown_fails_closed():
    report = snapshot()
    report["ram"].pop("commit_used_bytes")
    assert evaluate_readiness([report], POLICY)["status"] == "unknown"


def test_unknown_gpu_is_not_treated_as_zero_or_as_a_pass():
    report = snapshot()
    report["accelerators"]["nvidia"] = {"status": "unavailable", "devices": []}
    result = evaluate_readiness([report], POLICY)
    assert result["status"] == "unknown"
    assert result["samples"][0]["free_vram_bytes"] is None


def test_wrong_gpu_index_is_unknown_not_reassigned():
    assert evaluate_readiness([snapshot(gpu_index=1)], POLICY)["status"] == "unknown"


def test_invalid_observations_cannot_grant_pass():
    report = snapshot()
    report["ram"]["available_bytes"] = True
    report["ram"]["commit_used_bytes"] = -1
    report["accelerators"]["nvidia"]["devices"][0]["vram_free_bytes"] = -1
    out = evaluate_readiness([report], POLICY)
    assert out["status"] == "unknown"
    assert len(out["unknown_checks"]) == 3


def test_breach_takes_precedence_over_unknown():
    report = snapshot(ram=855)
    report["ram"]["commit_status"] = "unavailable"
    assert evaluate_readiness([report], POLICY)["status"] == "blocked"


def test_missing_windows_commit_is_unknown():
    report = snapshot()
    report["ram"] = {"status": "observed", "source": "GlobalMemoryStatusEx",
                     "available_bytes": 7_000 * MIB}
    assert evaluate_readiness([report], POLICY)["status"] == "unknown"


def test_empty_samples_refused():
    with pytest.raises(ValueError, match="At least one"):
        evaluate_readiness([], POLICY)


@pytest.mark.parametrize("kwargs", [
    {"min_available_ram_mib": 0},
    {"max_commit_percent": float("nan")},
    {"max_commit_percent": 100},
    {"min_free_vram_mib": -1},
    {"gpu_index": -2},
])
def test_bad_policy_refused(kwargs):
    opts = {"min_available_ram_mib": 6000, "max_commit_percent": 80,
            "min_free_vram_mib": 5000, **kwargs}
    with pytest.raises(ValueError):
        ReadinessPolicy(**opts)
