"""Offline P08-A03 evidence and fallback contract tests.

All records here are synthetic. No ComfyUI, Torch, CUDA, network or GPU is
touched. The tests prove fail-closed control behavior, not real OOM recovery.
"""
from __future__ import annotations

import copy
import json
import math
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


def set_preflight(bundle: dict, **values: object) -> None:
    sample = {
        "available_ram_mib": 8000.0,
        "system_commit_percent": 45.0,
        "free_vram_mib": 7000.0,
    }
    sample.update(values)
    bundle["preflight"]["samples"] = [sample]


def set_run_timing(bundle: dict, position: int, start: str, finish: str,
                   latency: float) -> None:
    run = bundle["runs"][position]
    run["started_at"] = start
    run["finished_at"] = finish
    run["latency_seconds"] = latency


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
    assert plan["hardware"]["cleanup_limit_seconds"] == 60
    assert plan["hardware"]["total_workload_includes"] == ["startup", "three_runs", "cleanup"]
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
    assert report["integrity"]["independently_verified"] is False


def test_preflight_equality_at_all_floors_passes():
    bundle = synthetic_bundle()
    set_preflight(bundle, available_ram_mib=6000.0, system_commit_percent=80.0,
                  free_vram_mib=5000.0)
    assert validate_evidence(bundle)["verdict"] == "pass"


@pytest.mark.parametrize("field,value", [
    ("available_ram_mib", 5999.999),
    ("system_commit_percent", 80.001),
    ("free_vram_mib", 4999.999),
])
def test_preflight_one_unit_beyond_each_floor_blocks(field, value):
    bundle = synthetic_bundle()
    set_preflight(bundle, **{field: value})
    report = validate_evidence(bundle)
    assert report["verdict"] == "blocked"
    assert report["failure_code"] == "insufficient_resources"


def test_reported_pass_with_unsafe_measurement_is_rejected():
    bundle = synthetic_bundle()
    bundle["preflight"]["status"] = "pass"
    set_preflight(bundle, available_ram_mib=10.0)
    assert validate_evidence(bundle)["failure_code"] == "insufficient_resources"


@pytest.mark.parametrize("field,value", [
    ("available_ram_mib", True),
    ("system_commit_percent", "45"),
    ("free_vram_mib", None),
    ("system_commit_percent", math.nan),
    ("available_ram_mib", math.inf),
    ("free_vram_mib", -1),
])
def test_invalid_preflight_measurements_are_incomplete(field, value):
    bundle = synthetic_bundle()
    set_preflight(bundle, **{field: value})
    assert validate_evidence(bundle)["verdict"] == "incomplete"


def test_missing_preflight_samples_are_incomplete():
    bundle = synthetic_bundle()
    bundle["preflight"].pop("samples")
    assert validate_evidence(bundle)["verdict"] == "incomplete"


def test_blocked_preflight_stops_before_startup():
    bundle = synthetic_bundle()
    bundle["preflight"] = {
        "status": "blocked",
        "blocked_checks": [{"check": "available_ram"}],
    }
    report = validate_evidence(bundle)
    assert report["verdict"] == "blocked"
    assert report["failure_code"] == "insufficient_resources"
    assert report["prompts_submitted"] == 0


def test_startup_timeout_stops_without_prompts():
    bundle = synthetic_bundle()
    bundle["startup"] = {
        "count": 1,
        "supervised": True,
        "ready": False,
        "reason": "timeout",
        "prompts_submitted_before_ready": 0,
        "required_nodes_present": False,
    }
    report = validate_evidence(bundle)
    assert report["verdict"] == "blocked"
    assert report["failure_code"] == "startup_timeout"
    assert report["prompts_submitted"] == 0


def test_missing_startup_count_is_rejected():
    bundle = synthetic_bundle()
    bundle["startup"].pop("count")
    assert validate_evidence(bundle)["failure_code"] == "startup_count_invalid"


@pytest.mark.parametrize("count", [0, 2, True, "1"])
def test_startup_count_must_be_exactly_one_integer(count):
    bundle = synthetic_bundle()
    bundle["startup"]["count"] = count
    assert validate_evidence(bundle)["failure_code"] == "startup_count_invalid"


def test_startup_must_be_supervised():
    bundle = synthetic_bundle()
    bundle["startup"]["supervised"] = False
    assert validate_evidence(bundle)["failure_code"] == "startup_not_supervised"


def test_startup_equality_at_120_seconds_passes():
    bundle = synthetic_bundle()
    bundle["startup"]["started_at"] = "2026-10-19T16:43:00+00:00"
    bundle["startup"]["finished_at"] = "2026-10-19T16:45:00+00:00"
    bundle["startup"]["elapsed_seconds"] = 120.0
    assert validate_evidence(bundle)["verdict"] == "pass"


def test_startup_beyond_120_seconds_blocks():
    bundle = synthetic_bundle()
    bundle["startup"]["started_at"] = "2026-10-19T16:42:59+00:00"
    bundle["startup"]["finished_at"] = "2026-10-19T16:45:00+00:00"
    bundle["startup"]["elapsed_seconds"] = 121.0
    report = validate_evidence(bundle)
    assert report["failure_code"] == "startup_limit_exceeded"


def test_startup_elapsed_must_match_timestamps():
    bundle = synthetic_bundle()
    bundle["startup"]["elapsed_seconds"] = 50.0
    assert validate_evidence(bundle)["verdict"] == "incomplete"


@pytest.mark.parametrize("start,finish", [
    ("2026-10-19T16:45:00+00:00", "2026-10-19T16:44:50+00:00"),
    ("2026-10-19T16:44:50", "2026-10-19T16:45:00"),
])
def test_startup_timestamp_chronology_and_timezone(start, finish):
    bundle = synthetic_bundle()
    bundle["startup"]["started_at"] = start
    bundle["startup"]["finished_at"] = finish
    assert validate_evidence(bundle)["verdict"] == "incomplete"


def test_missing_prompts_before_ready_is_rejected():
    bundle = synthetic_bundle()
    bundle["startup"].pop("prompts_submitted_before_ready")
    assert validate_evidence(bundle)["verdict"] == "incomplete"


def test_prompt_before_ready_blocks():
    bundle = synthetic_bundle()
    bundle["startup"]["prompts_submitted_before_ready"] = 1
    assert validate_evidence(bundle)["failure_code"] == "startup_contract_violation"


def test_missing_required_nodes_blocks():
    bundle = synthetic_bundle()
    bundle["startup"]["required_nodes_present"] = False
    report = validate_evidence(bundle)
    assert report["failure_code"] == "required_nodes_missing"


def test_run_equality_at_300_seconds_passes():
    bundle = synthetic_bundle()
    set_run_timing(bundle, 0, "2026-10-19T16:45:01+00:00",
                   "2026-10-19T16:50:01+00:00", 300.0)
    set_run_timing(bundle, 1, "2026-10-19T16:50:02+00:00",
                   "2026-10-19T16:50:04+00:00", 2.0)
    set_run_timing(bundle, 2, "2026-10-19T16:50:05+00:00",
                   "2026-10-19T16:50:07+00:00", 2.0)
    bundle["cleanup"].update({
        "started_at": "2026-10-19T16:50:08+00:00",
        "finished_at": "2026-10-19T16:50:09+00:00",
        "elapsed_seconds": 1.0,
    })
    assert validate_evidence(bundle)["verdict"] == "pass"


def test_run_beyond_300_seconds_blocks():
    bundle = synthetic_bundle()
    set_run_timing(bundle, 0, "2026-10-19T16:45:01+00:00",
                   "2026-10-19T16:50:02+00:00", 301.0)
    report = validate_evidence(bundle)
    assert report["failure_code"] == "run_limit_exceeded"


def test_run_latency_must_match_timestamps():
    bundle = synthetic_bundle()
    bundle["runs"][0]["latency_seconds"] = 10.0
    assert validate_evidence(bundle)["verdict"] == "incomplete"


def test_run_timestamps_must_be_aware_and_ordered():
    bundle = synthetic_bundle()
    bundle["runs"][1]["started_at"] = "2026-10-19T16:45:04"
    assert validate_evidence(bundle)["verdict"] == "incomplete"
    bundle = synthetic_bundle()
    bundle["runs"][1]["started_at"] = "2026-10-19T16:45:00+00:00"
    assert validate_evidence(bundle)["verdict"] == "incomplete"


def test_run_indexes_must_be_exact_and_ordered():
    bundle = synthetic_bundle()
    bundle["runs"][1]["run_index"] = 1
    assert validate_evidence(bundle)["verdict"] == "incomplete"
    bundle = synthetic_bundle()
    bundle["runs"][2]["run_index"] = 4
    assert validate_evidence(bundle)["verdict"] == "incomplete"


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


def test_missing_cuda_error_field_is_not_implicit_none():
    bundle = synthetic_bundle()
    bundle["runs"][0].pop("cuda_error")
    assert validate_evidence(bundle)["verdict"] == "incomplete"


def test_duplicate_prompt_is_blocked():
    bundle = synthetic_bundle()
    bundle["runs"][1]["prompt_id"] = bundle["runs"][0]["prompt_id"]
    assert validate_evidence(bundle)["failure_code"] == "duplicate_prompt"


def test_missing_retry_count_is_not_treated_as_zero():
    bundle = synthetic_bundle()
    bundle["runs"][0].pop("retry_count")
    assert validate_evidence(bundle)["verdict"] == "incomplete"


def test_retry_is_blocked():
    bundle = synthetic_bundle()
    bundle["runs"][0]["retry_count"] = 1
    assert validate_evidence(bundle)["failure_code"] == "retry_attempted"


def test_artifact_overwrite_is_blocked():
    bundle = synthetic_bundle()
    bundle["runs"][1]["output_path"] = bundle["runs"][0]["output_path"]
    assert validate_evidence(bundle)["failure_code"] == "artifact_overwrite"


def test_corrupt_or_missing_output_hash_is_incomplete():
    bundle = synthetic_bundle()
    bundle["runs"][2]["output_sha256"] = "not-a-sha256"
    assert validate_evidence(bundle)["verdict"] == "incomplete"


@pytest.mark.parametrize("field", [
    "latency_seconds", "peak_vram_mib", "min_free_vram_mib",
    "min_available_ram_mib", "max_commit_percent",
])
def test_invalid_telemetry_is_incomplete(field):
    bundle = synthetic_bundle()
    bundle["runs"][0][field] = -1 if field != "latency_seconds" else 0
    assert validate_evidence(bundle)["verdict"] == "incomplete"


@pytest.mark.parametrize("field", ["peak_vram_mib", "min_free_vram_mib",
                                     "min_available_ram_mib", "max_commit_percent"])
def test_boolean_metrics_are_not_numbers(field):
    bundle = synthetic_bundle()
    bundle["runs"][0][field] = True
    assert validate_evidence(bundle)["verdict"] == "incomplete"


@pytest.mark.parametrize("field", ["peak_vram_mib", "min_free_vram_mib",
                                     "min_available_ram_mib", "max_commit_percent"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_metrics_are_incomplete(field, value):
    bundle = synthetic_bundle()
    bundle["runs"][0][field] = value
    assert validate_evidence(bundle)["verdict"] == "incomplete"


def test_three_runs_are_required_not_four():
    bundle = synthetic_bundle()
    bundle["runs"].append(copy.deepcopy(bundle["runs"][0]))
    report = validate_evidence(bundle)
    assert report["failure_code"] == "incorrect_run_count"
    assert report["prompts_submitted"] == 0


def test_total_workload_beyond_900_seconds_blocks():
    bundle = synthetic_bundle()
    bundle["startup"].update({
        "started_at": "2026-10-19T16:00:00+00:00",
        "finished_at": "2026-10-19T16:00:10+00:00",
        "elapsed_seconds": 10.0,
    })
    for i, (start, finish) in enumerate((
        ("16:00:11", "16:05:10"),
        ("16:05:11", "16:10:10"),
        ("16:10:11", "16:15:10"),
    )):
        set_run_timing(
            bundle, i,
            f"2026-10-19T{start}+00:00",
            f"2026-10-19T{finish}+00:00",
            299.0,
        )
    bundle["cleanup"].update({
        "started_at": "2026-10-19T16:15:11+00:00",
        "finished_at": "2026-10-19T16:15:12+00:00",
        "elapsed_seconds": 1.0,
    })
    report = validate_evidence(bundle)
    assert report["failure_code"] == "workload_limit_exceeded"


def test_cleanup_equality_at_60_seconds_passes():
    bundle = synthetic_bundle()
    bundle["cleanup"].update({
        "started_at": "2026-10-19T16:45:10+00:00",
        "finished_at": "2026-10-19T16:46:10+00:00",
        "elapsed_seconds": 60.0,
    })
    assert validate_evidence(bundle)["verdict"] == "pass"


def test_cleanup_beyond_60_seconds_blocks():
    bundle = synthetic_bundle()
    bundle["cleanup"].update({
        "started_at": "2026-10-19T16:45:10+00:00",
        "finished_at": "2026-10-19T16:46:11+00:00",
        "elapsed_seconds": 61.0,
    })
    report = validate_evidence(bundle)
    assert report["failure_code"] == "cleanup_limit_exceeded"


def test_total_workload_equality_at_900_seconds_passes():
    bundle = synthetic_bundle()
    bundle["startup"].update({
        "started_at": "2026-10-19T16:00:00+00:00",
        "finished_at": "2026-10-19T16:00:10+00:00",
        "elapsed_seconds": 10.0,
    })
    for i, (start, finish) in enumerate((
        ("16:00:10", "16:05:06"),
        ("16:05:06", "16:10:02"),
        ("16:10:02", "16:14:58"),
    )):
        set_run_timing(
            bundle, i,
            f"2026-10-19T{start}+00:00",
            f"2026-10-19T{finish}+00:00",
            296.0,
        )
    bundle["cleanup"].update({
        "started_at": "2026-10-19T16:14:58+00:00",
        "finished_at": "2026-10-19T16:15:00+00:00",
        "elapsed_seconds": 2.0,
    })
    assert validate_evidence(bundle)["verdict"] == "pass"


def test_cleanup_timing_and_fields_are_required():
    bundle = synthetic_bundle()
    bundle["cleanup"].pop("elapsed_seconds")
    assert validate_evidence(bundle)["verdict"] == "incomplete"
    bundle = synthetic_bundle()
    bundle["cleanup"].pop("remaining_processes")
    assert validate_evidence(bundle)["verdict"] == "incomplete"


@pytest.mark.parametrize("cleanup_change", [
    {"remaining_processes": [123]},
    {"listener_open": True},
    {"cache_removed": False},
    {"environment_restored": False},
])
def test_cleanup_must_be_proven(cleanup_change):
    bundle = synthetic_bundle()
    bundle["cleanup"].update(cleanup_change)
    assert validate_evidence(bundle)["failure_code"] == "cleanup_incomplete"


@pytest.mark.parametrize("provenance", ["declared", "unverified", "synthetic"])
def test_untrusted_hash_provenance_cannot_pass(provenance):
    bundle = synthetic_bundle()
    bundle["integrity"]["output_hashes"] = provenance
    assert validate_evidence(bundle)["verdict"] == "incomplete"


def test_independent_rehash_claim_still_not_verified_by_public_validator():
    bundle = synthetic_bundle()
    bundle["integrity"]["output_hashes"] = "independently_rehashed"
    report = validate_evidence(bundle)
    assert report["verdict"] == "incomplete"
    assert report["fallback_required"] is True


def test_independent_rehash_manifest_is_declared_but_not_verified():
    bundle = synthetic_bundle()
    bundle["integrity"]["output_hashes"] = "independently_rehashed"
    bundle["integrity"]["independent_rehash_manifest"] = {
        "verifier": "synthetic-reviewer",
        "manifest_sha256": "f" * 64,
        "verified_at": "2026-10-19T17:00:00+00:00",
    }
    report = validate_evidence(bundle)
    assert report["verdict"] == "pass"
    assert report["integrity"]["independently_verified"] is False


def test_missing_integrity_is_incomplete():
    bundle = synthetic_bundle()
    bundle.pop("integrity")
    assert validate_evidence(bundle)["verdict"] == "incomplete"


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
