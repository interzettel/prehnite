"""Offline economics and attempt telemetry: no provider keys or network calls."""
from __future__ import annotations

import json
import math

import pytest
from PIL import Image

from prehnite.economics import batch_economics
from prehnite.engine import Engine
from prehnite.providers import Result
from prehnite.reporting import export_report
from prehnite.schema import Endpoint, Manifest, Profile
from prehnite.store import Journal


def mk_task(index, cost=0.025):
    return {"task_key": f"asset-{index}:generate", "stage": "generation",
            "status": "completed", "provider": "fal", "model": "fixture",
            "reserved_usd": cost, "data": {}}


def mk_attempt(key, outcome="completed", elapsed=25.0):
    return {"task_key": key, "stage": "generation",
            "provider": "fal", "outcome": outcome,
            "elapsed_ms": elapsed}


def test_90_asset_reserved_cost_per_accepted_and_retries_without_invoices():
    tasks = [mk_task(i) for i in range(90)]
    results = {
        f"asset-{i}": {"status": "accepted" if i < 72 else "rejected"}
        for i in range(90)
    }
    attempts = [mk_attempt(t["task_key"]) for t in tasks]
    for i in range(7):
        attempts.append(mk_attempt(tasks[i]["task_key"], "failed", 10.0))
    # A killed worker leaves an open attempt; it contributes no measured time.
    attempts.append(mk_attempt(tasks[8]["task_key"], "incomplete", None))
    summary = batch_economics(tasks, results, attempts)
    assert summary["reserved_usd_total"] == pytest.approx(2.25)
    assert summary["accepted_assets"] == 72
    assert summary["asset_status_counts"] == {"accepted": 72, "rejected": 18}
    assert summary["reserved_usd_per_accepted_asset"] == 0.03125
    assert summary["actual_invoiced_usd_total"] is None
    assert summary["actual_invoiced_usd_per_accepted_asset"] is None
    assert summary["actual_invoice_verified"] is False
    assert summary["provider_reported_usd_partial_total"] is None
    assert summary["provider_reported_operation_count"] == 0
    assert summary["attempts_started"] == 98
    assert summary["attempts_with_observed_duration"] == 97
    assert summary["attempts_without_finished_timing"] == 1
    assert summary["retry_attempts"] == 8
    assert summary["stages"]["generation"]["operations"] == 90
    assert summary["stages"]["generation"]["retry_attempts"] == 8
    assert summary["stages"]["generation"]["observed_elapsed_ms_p95"] == 25.0
    assert summary["stages"]["generation"]["observed_elapsed_ms_median"] == 25.0


def test_no_accepted_assets_does_not_claim_zero_per_accepted():
    tasks = [mk_task(0), mk_task(1)]
    results = {"asset-0": {"status": "rejected"}, "asset-1": {"status": "error"}}
    data = batch_economics(tasks, results, [])
    assert data["accepted_assets"] == 0
    assert data["reserved_usd_per_accepted_asset"] is None
    assert data["attempts_with_observed_duration"] == 0
    assert data["stages"]["generation"]["observed_elapsed_ms_p95"] is None


def test_provider_reported_is_labeled_partial_not_verified_invoice():
    tasks = [mk_task(i) for i in range(3)]
    tasks[0]["data"]["provider_reported_usd"] = 0.012
    tasks[1]["data"]["provider_reported_usd"] = 0.011
    result = batch_economics(tasks, {"a": {"status": "accepted"}}, [])
    assert result["reserved_usd_total"] == 0.075
    assert result["provider_reported_usd_partial_total"] == 0.023
    assert result["provider_reported_operation_count"] == 2
    assert result["actual_invoiced_usd_total"] is None
    assert result["reserved_usd_per_accepted_asset"] == 0.075


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.5, True, "not-a-number"])
def test_invalid_money_is_rejected(value):
    with pytest.raises(ValueError, match="USD"):
        batch_economics([mk_task(0, value)], {}, [])


@pytest.mark.parametrize("outcome,elapsed", [
    ("completed", None), ("failed", float("nan")), ("completed", -1),
    ("incomplete", 3.5), ("unknown", 3.5),
])
def test_incomplete_or_invalid_timing_cannot_be_misreported(outcome, elapsed):
    with pytest.raises(ValueError):
        batch_economics([mk_task(0)], {}, [mk_attempt("asset-0:generate",
                                                       outcome, elapsed)])


def test_orphan_and_mismatched_attempts_refused():
    with pytest.raises(ValueError, match="unknown"):
        batch_economics([mk_task(0)], {}, [mk_attempt("nonexistent")])
    mismatch = mk_attempt("asset-0:generate")
    mismatch["stage"] = "upscaling"
    with pytest.raises(ValueError, match="does not match"):
        batch_economics([mk_task(0)], {}, [mismatch])


def test_attempts_are_durable_and_not_double_finished(tmp_path):
    j = Journal(tmp_path, "metrics")
    try:
        j.put("demo:generate", "generation", "submitting",
              provider="demo", reserved_usd=0)
        first = j.begin_attempt("demo:generate", "generation", "demo")
        second = j.begin_attempt("demo:generate", "generation", "demo")
        j.finish_attempt(second, "completed", 12.5)
        with pytest.raises(ValueError, match="already finished"):
            j.finish_attempt(second, "failed", 100)
        with pytest.raises(ValueError):
            j.finish_attempt(first, "complete-but-not-real", -1)
        assert [a["outcome"] for a in j.attempts()] == ["incomplete", "completed"]
        assert j.attempts()[0]["elapsed_ms"] is None
        assert j.attempts()[1]["elapsed_ms"] == 12.5
        assert j.reserved() == 0
    finally:
        j.close()
    reopened = Journal(tmp_path, "metrics")
    try:
        assert len(reopened.attempts()) == 2
    finally:
        reopened.close()


def _job():
    manifest = Manifest.model_validate({
        "id": "economics-local",
        "assets": [{
            "id": "portrait", "prompt": "deterministic local demo",
            "aspect_ratio": "3:4", "target_size": [192, 256],
            "output": {"image": "portrait.png"},
        }],
    })
    profile = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
    })
    return manifest, profile


def test_actual_local_batch_export_contains_truthful_telemetry_and_html(tmp_path):
    manifest, profile = _job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        result = engine.run()
        e = result["economics"]
        assert e["accepted_assets"] == 1
        assert e["reserved_usd_total"] == 0
        assert e["reserved_usd_per_accepted_asset"] == 0
        assert e["actual_invoiced_usd_total"] is None
        assert e["attempts_with_observed_duration"] >= 1
        assert "generation" in e["stages"]
        assert e["stages"]["generation"]["observed_elapsed_ms_p95"] is not None
        html = (engine.journal.root / "report.html").read_text()
        assert "Reserved estimate per accepted asset" not in html  # lower-case label
        assert "reserved estimate per accepted asset" in html
        assert "not actual invoices" in html
        assert "provider inference" in html
        assert json.loads((engine.journal.root/"report.json").read_text())["economics"] == e
        original_count = e["attempts_started"]
        again = engine.run()
        assert again["economics"]["attempts_started"] == original_count
    finally:
        engine.journal.close()


def test_unfinished_paid_retry_does_not_count_as_second_reservation(tmp_path):
    manifest, profile = _job()
    costs = profile.costs.model_copy(update={
        "allow_paid": True, "allow_cloud_uploads": True,
        "max_usd": 0.1, "estimates_usd": {"generation:2k": 0.04},
    })
    profile = profile.model_copy(update={"costs": costs})
    engine = Engine(manifest, profile, tmp_path)
    destination = engine.journal.root/"remote.png"
    request_id = "recoverable-opaque"
    def fail(on_submit, resume_id, staged):
        assert resume_id is None
        on_submit(request_id)
        raise TimeoutError("connection failed after ID persistence")
    try:
        with pytest.raises(TimeoutError):
            engine.stage("portrait:generate", "generation",
                         Endpoint(provider="fal", model="mock"),
                         destination, fail, "generation:2k")
        first = export_report(engine.journal)["economics"]
        assert first["reserved_usd_total"] == 0.04
        assert first["attempts_started"] == 1
        assert first["attempts_with_observed_duration"] == 1
        def recover(on_submit, resume_id, staged):
            assert resume_id == request_id
            assert on_submit is not None
            Image.new("RGB", (192, 256), "teal").save(staged)
            return Result(staged, request_id)
        engine.stage("portrait:generate", "generation",
                     Endpoint(provider="fal", model="mock"),
                     destination, recover, "generation:2k")
        complete = export_report(engine.journal)["economics"]
        assert complete["reserved_usd_total"] == 0.04
        assert complete["attempts_started"] == 2
        assert complete["retry_attempts"] == 1
        assert complete["stages"]["generation"]["attempts_failed"] == 1
        assert complete["stages"]["generation"]["attempts_completed"] == 1
    finally:
        engine.journal.close()
