"""Offline P08-A03 evidence and fallback contract tests.

All records here are synthetic. No ComfyUI, Torch, CUDA, network or GPU is
touched. The tests prove fail-closed control behavior, not real OOM recovery.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from prehnite.benchmark_evidence import (
    EXPECTED_RUNS,
    RunController,
    canonical_digest,
    experiment_plan,
    profile_digest,
    simulated_fallback_scenarios,
    validate_evidence,
)

FIXTURE = Path(__file__).parent / "fixtures" / "p08_a03" / "valid_evidence.json"


def synthetic_bundle() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_plan_is_bounded_and_not_authorized():
    plan = experiment_plan()
    assert plan["status"] == "preparation_only_not_authorized"
    assert plan["hardware"]["max_startups"] == 1
    assert plan["hardware"]["max_runs"] == EXPECTED_RUNS
    assert plan["hardware"]["max_attempts"] == EXPECTED_RUNS
    assert plan["hardware"]["retries"] == 0
    assert plan["hardware"]["startup_limit_seconds"] == 120
    assert plan["hardware"]["per_run_limit_seconds"] == 300
    assert plan["hardware"]["total_workload_limit_seconds"] == 900
    assert plan["preflight"] == {
        "min_available_ram_mib": 6000,
        "max_commit_percent": 80,
        "min_free_vram_mib": 5000,
    }
    assert plan["profile"]["deterministic_output_required"] is False
    assert plan["profile"]["sampled_peak_is_absolute_peak"] is False


def test_fixture_profile_digest_matches():
    bundle = synthetic_bundle()
    assert bundle["runs"][0]["profile_digest"] == profile_digest(bundle["profile"])


def test_valid_synthetic_evidence_passes_without_identical_outputs():
    bundle = synthetic_bundle()
    hashes = {run["output_sha256"] for run in bundle["runs"]}
    assert len(hashes) == EXPECTED_RUNS
    report = validate_evidence(bundle)
    assert report["verdict"] == "pass"
    assert report["run_count"] == EXPECTED_RUNS
    assert report["outputs_distinct"] is True
    assert report["fallback_required"] is False


@pytest.mark.parametrize("metric", [
    {"status": "blocked", "blocked_checks": [{"check": "available_ram"}]},
    {"status": "blocked", "blocked_checks": [{"check": "free_vram"}]},
    {"status": "blocked", "blocked_checks": [{"check": "system_commit"}]},
])
def test_insufficient_resources_stop_before_startup(metric):
    bundle = synthetic_bundle()
    bundle["preflight"] = metric
    report = validate_evidence(bundle)
    assert report["verdict"] == "blocked"
    assert report["failure_code"] == "insufficient_resources"
    assert report["prompts_submitted"] == 0


def test_startup_timeout_stops_without_prompts():
    bundle = synthetic_bundle()
    bundle["startup"] = {
        "ready": False,
        "reason": "timeout",
        "prompts_submitted_before_ready": 0,
        "required_nodes_present": False,
    }
    report = validate_evidence(bundle)
    assert report["verdict"] == "blocked"
    assert report["failure_code"] == "startup_timeout"
    assert report["prompts_submitted"] == 0


def test_missing_required_nodes_blocks():
    bundle = synthetic_bundle()
    bundle["startup"]["required_nodes_present"] = False
    report = validate_evidence(bundle)
    assert report["failure_code"] == "required_nodes_missing"


@pytest.mark.parametrize("status,code", [
    ("failed", "inference_failed"),
    ("terminated", "process_terminated"),
    ("unknown", "unknown_outcome"),
])
def test_non_success_run_blocks_without_retry(status, code):
    bundle = synthetic_bundle()
    bundle["runs"][1]["status"] = status
    bundle["runs"][1]["failure_code"] = code
    report = validate_evidence(bundle)
    assert report["verdict"] == "blocked"
    assert report["failure_code"] == code
    assert report["prompts_submitted"] == 2


def test_cuda_oom_is_classified_and_blocked():
    bundle = synthetic_bundle()
    bundle["runs"][0]["status"] = "failed"
    bundle["runs"][0]["cuda_error"] = "CUDA out of memory"
    report = validate_evidence(bundle)
    assert report["failure_code"] == "cuda_oom"
    assert report["prompts_submitted"] == 1


def test_first_run_failure_counts_the_submitted_prompt():
    bundle = synthetic_bundle()
    bundle["runs"][0]["status"] = "failed"
    report = validate_evidence(bundle)
    assert report["prompts_submitted"] == 1


def test_cuda_error_on_success_is_blocked():
    bundle = synthetic_bundle()
    bundle["runs"][2]["cuda_error"] = "CUDA error"
    report = validate_evidence(bundle)
    assert report["failure_code"] == "cuda_error"


def test_duplicate_prompt_is_blocked():
    bundle = synthetic_bundle()
    bundle["runs"][1]["prompt_id"] = bundle["runs"][0]["prompt_id"]
    report = validate_evidence(bundle)
    assert report["failure_code"] == "duplicate_prompt"


def test_artifact_overwrite_is_blocked():
    bundle = synthetic_bundle()
    bundle["runs"][1]["output_path"] = bundle["runs"][0]["output_path"]
    report = validate_evidence(bundle)
    assert report["failure_code"] == "artifact_overwrite"


def test_corrupt_or_missing_output_hash_is_incomplete():
    bundle = synthetic_bundle()
    bundle["runs"][2]["output_sha256"] = "not-a-sha256"
    report = validate_evidence(bundle)
    assert report["verdict"] == "incomplete"


def test_profile_mismatch_is_blocked():
    bundle = synthetic_bundle()
    bundle["runs"][1]["profile_digest"] = "0" * 64
    report = validate_evidence(bundle)
    assert report["failure_code"] == "profile_mismatch"


def test_retry_is_blocked():
    bundle = synthetic_bundle()
    bundle["runs"][0]["retry_count"] = 1
    report = validate_evidence(bundle)
    assert report["failure_code"] == "retry_attempted"


def test_three_runs_are_required_not_four():
    bundle = synthetic_bundle()
    bundle["runs"].append(copy.deepcopy(bundle["runs"][0]))
    report = validate_evidence(bundle)
    assert report["failure_code"] == "incorrect_run_count"
    assert report["prompts_submitted"] == 0


@pytest.mark.parametrize("field", [
    "latency_seconds",
    "peak_vram_mib",
    "min_free_vram_mib",
    "min_available_ram_mib",
    "max_commit_percent",
])
def test_invalid_telemetry_is_incomplete(field):
    bundle = synthetic_bundle()
    bundle["runs"][0][field] = -1 if field != "latency_seconds" else 0
    report = validate_evidence(bundle)
    assert report["verdict"] == "incomplete"


@pytest.mark.parametrize("cleanup_change", [
    {"remaining_processes": [123]},
    {"listener_open": True},
    {"cache_removed": False},
    {"environment_restored": False},
])
def test_cleanup_must_be_proven(cleanup_change):
    bundle = synthetic_bundle()
    bundle["cleanup"].update(cleanup_change)
    report = validate_evidence(bundle)
    assert report["failure_code"] == "cleanup_incomplete"


def test_controller_records_three_and_refuses_a_fourth():
    controller = RunController()
    for run in synthetic_bundle()["runs"]:
        assert controller.record(run) is True
    assert controller.can_start is False
    assert controller.record(synthetic_bundle()["runs"][0]) is False
    assert len(controller.runs) == EXPECTED_RUNS


def test_controller_refuses_duplicate_prompt_and_stops():
    controller = RunController()
    first, second = synthetic_bundle()["runs"][:2]
    assert controller.record(first) is True
    duplicate = dict(second, prompt_id=first["prompt_id"])
    assert controller.record(duplicate) is False
    assert controller.stop_code == "duplicate_prompt"
    assert len(controller.runs) == 1
    assert controller.can_start is False


def test_controller_refuses_output_path_reuse():
    controller = RunController()
    first, second = synthetic_bundle()["runs"][:2]
    assert controller.record(first) is True
    reused = dict(second, output_path=first["output_path"])
    assert controller.record(reused) is False
    assert controller.stop_code == "artifact_overwrite"


def test_controller_stops_after_failure_without_retry():
    controller = RunController()
    first = dict(synthetic_bundle()["runs"][0], status="terminated")
    assert controller.record(first) is True
    assert controller.stop_code == "process_terminated"
    assert controller.can_start is False
    assert controller.record(synthetic_bundle()["runs"][1]) is False
    assert len(controller.runs) == 1


def test_simulated_fallbacks_are_deterministic_and_hardware_free():
    scenarios = simulated_fallback_scenarios()
    expected = {
        "insufficient_ram",
        "insufficient_vram",
        "startup_timeout",
        "inference_failure",
        "process_termination",
        "unknown_outcome",
        "duplicate_prompt",
        "artifact_overwrite",
    }
    assert {item["scenario"] for item in scenarios} == expected
    assert all(item["prompts_submitted"] <= 1 for item in scenarios)
    assert canonical_digest({"scenarios": scenarios}) == canonical_digest(
        {"scenarios": simulated_fallback_scenarios()}
    )
