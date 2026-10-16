"""Offline regression evidence: actionable codes without unsafe retries or secrets."""
from __future__ import annotations

import hashlib
import json
import zipfile

import pytest
from PIL import Image

from prehnite.artifacts import ArtifactIntegrityError
from prehnite.engine import BudgetExceeded, Engine
from prehnite.failures import (RecoveryBlocked, classify_asset,
                              classify_exception, classify_task, summarize_failures)
from prehnite.reporting import export_report
from prehnite.schema import Endpoint, Manifest, Profile


def make_engine(tmp_path, *, paid=False, cutout=False, batch="failure-fixture"):
    asset = {
        "id": "slot", "prompt": "offline fixture", "aspect_ratio": "3:4",
        "target_size": [192, 256], "output": {"image": "slot.png",
            "cutouts": {"subject": "subject.png"} if cutout else {}},
        "targets": ["subject"] if cutout else [],
    }
    manifest = Manifest.model_validate({"id": batch, "assets": [asset]})
    profile = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "segmentation": {"provider": "demo", "model": "simple-mask"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
        "costs": {"allow_paid": paid, "allow_cloud_uploads": paid,
                  "max_usd": 0.10 if paid else 0,
                  "estimates_usd": {"generation:2k": 0.02} if paid else {}},
    })
    return Engine(manifest, profile, tmp_path)


@pytest.mark.parametrize(
    ("error", "stage", "provider", "code", "action"),
    [
        (BudgetExceeded("budget private"), "generation", "fal", "budget_limit",
         "request_budget_review"),
        (PermissionError("not allowed"), "judge", "anthropic",
         "authorization_required", "obtain_explicit_consent"),
        (RecoveryBlocked("remote secret"), "generation", "fal",
         "remote_reconciliation_required", "manual_reconcile_before_retry"),
        (ArtifactIntegrityError("/private/file.png"), "asset", "local",
         "artifact_integrity", "inspect_and_restore_artifact"),
        (TimeoutError("credential hidden"), "generation", "fal",
         "remote_transport_uncertain", "manual_reconcile_before_retry"),
        (TimeoutError("secret"), "segmentation", "demo",
         "local_transport_failure", "inspect_and_retry_nonpaid"),
        (ValueError("bad pixels"), "segmentation", "demo",
         "technical_validation", "inspect_invalid_artifact"),
    ],
)
def test_stable_typed_failures_do_not_echo_secrets(error, stage, provider, code, action):
    classified = classify_exception(error, stage=stage, provider=provider)
    assert classified["code"] == code
    assert classified["next_action"] == action
    assert classified["automatic_resubmit_allowed"] is False
    assert not any("secret" in str(value) or "private" in str(value)
                   for value in classified.values())


def test_persisted_crash_without_remote_receipt_is_fail_closed():
    rows = [
        {"task_key": "unsafe-token:1", "stage": "generation",
         "status": "submitting", "provider": "fal",
         "request_id": None, "data": {"error": "secret"}},
        {"task_key": "unsafe-token:2", "stage": "generation",
         "status": "submitted", "provider": "fal",
         "request_id": "external-private-request-id", "data": {}},
        {"task_key": "unsafe-token:3", "stage": "segmentation",
         "status": "running", "provider": "demo", "request_id": None, "data": {}},
    ]
    summary = summarize_failures(rows, {"slot": {"status": "error"}})
    assert summary["stage_failure_counts"] == {
        "local_stage_incomplete": 1, "remote_request_pending": 1,
        "remote_submission_ambiguous": 1,
    }
    assert len(summary["unresolved_operations"]) == 3
    for entry in summary["unresolved_operations"]:
        assert len(entry["task_key_sha256"]) == 64
        assert entry["automatic_resubmit_allowed"] is False
    assert "external-private-request-id" not in json.dumps(summary)
    assert "unsafe-token" not in json.dumps(summary)
    assert "secret" not in json.dumps(summary)
    assert classify_task(rows[0])["next_action"] == "manual_reconcile_before_retry"
    assert classify_task(rows[1])["next_action"] == "inspect_existing_request"


def test_nonpaid_stage_exception_surfaces_codes_in_json_csv_and_zip(monkeypatch, tmp_path):
    engine = make_engine(tmp_path)
    class BrokenDemo:
        def generate(self, *args, **kwargs):
            raise TimeoutError("secret=abc123; https://private-host.example/v1")
    monkeypatch.setattr("prehnite.engine.get_provider", lambda endpoint: BrokenDemo())
    try:
        report = engine.run()
        result = report["asset_results"]["slot"]
        assert result["status"] == "error"
        assert result["failure"]["code"] == "local_transport_failure"
        assert result["failure"]["automatic_resubmit_allowed"] is False
        task = engine.journal.tasks()[0]
        assert task["data"]["failure"]["code"] == "local_transport_failure"
        assert report["failure_summary"]["asset_failure_counts"]["local_transport_failure"] == 1
        assert report["failure_summary"]["stage_failure_counts"]["local_transport_failure"] == 1
        assert report["failure_summary"]["schema_version"] == 1
        summary_json = json.dumps(report["failure_summary"])
        assert "private-host" not in summary_json and "abc123" not in summary_json
        text = (engine.journal.root / "operations.csv").read_text()
        assert "failure_code,next_action" in text
        assert "local_transport_failure" in text
        assert "Machine-readable failures" in (engine.journal.root / "report.html").read_text()
        with zipfile.ZipFile(engine.journal.root / "prehnite-failure-fixture.zip") as z:
            raw = json.loads(z.read("_prehnite/report.json"))
            assert raw["failure_summary"]["schema_version"] == 1
            assert z.testzip() is None
    finally:
        engine.journal.close()


def test_paid_transport_without_id_never_attempts_second_dispatch(tmp_path):
    engine = make_engine(tmp_path, paid=True)
    seen = []
    destination = engine.journal.root / "unsafe-stage.png"
    def timeout(on_submit, resume_id, staging):
        seen.append(resume_id)
        raise TimeoutError("provider key must not enter summary")
    ep = Endpoint(provider="fal", model="synthetic-remote")
    try:
        with pytest.raises(TimeoutError):
            engine.stage("slot:paid", "generation", ep, destination,
                         timeout, "generation:2k")
        record = engine.journal.get("slot:paid")
        assert record["status"] == "uncertain"
        assert record["data"]["failure"]["code"] == "remote_transport_uncertain"
        summary = export_report(engine.journal)["failure_summary"]
        assert summary["stage_failure_counts"] == {"remote_submission_ambiguous": 1}
        with pytest.raises(RecoveryBlocked):
            engine.stage("slot:paid", "generation", ep, destination,
                         timeout, "generation:2k")
        assert seen == [None]
        assert engine.journal.reserved() == pytest.approx(0.02)
    finally:
        engine.journal.close()


def test_paid_request_with_known_id_resumes_without_resubmitting(tmp_path):
    engine = make_engine(tmp_path, paid=True, batch="known-id")
    ep = Endpoint(provider="fal", model="mock")
    destination = engine.journal.root / "queued.png"
    seen = []
    def break_after_id(on_submit, resume, staged):
        assert resume is None
        on_submit("receipt-123")
        raise TimeoutError("private output details")
    def recover(on_submit, resume, staged):
        seen.append(resume)
        assert resume == "receipt-123"
        Image.new("RGB", (192, 256), "blue").save(staged)
        from prehnite.providers import Result
        return Result(staged, "receipt-123")
    try:
        with pytest.raises(TimeoutError):
            engine.stage("slot:remote", "generation", ep, destination,
                         break_after_id, "generation:2k")
        first = export_report(engine.journal)["failure_summary"]
        assert first["stage_failure_counts"] == {"remote_request_pending": 1}
        assert first["unresolved_operations"][0]["request_id_present"] is True
        assert engine.journal.get("slot:remote")["request_id"] == "receipt-123"
        engine.stage("slot:remote", "generation", ep, destination,
                     recover, "generation:2k")
        assert seen == ["receipt-123"]
        assert not export_report(engine.journal)["failure_summary"]["unresolved_operations"]
        assert engine.journal.reserved() == pytest.approx(0.02)
    finally:
        engine.journal.close()


def test_existing_accepted_output_corruption_has_integrity_failure(tmp_path):
    engine = make_engine(tmp_path, batch="corruption-fixture")
    try:
        initial = engine.run()
        assert initial["asset_results"]["slot"]["status"] == "accepted"
        Image.new("RGB", (192, 256), "purple").save(
            engine.journal.root / "selected/slot.png")
        after = engine.run()
        result = after["asset_results"]["slot"]
        assert result["status"] == "error"
        assert result["integrity_error"] is True
        assert result["failure"]["code"] == "artifact_integrity"
        assert after["failure_summary"]["asset_failure_counts"] == {"artifact_integrity": 1}
    finally:
        engine.journal.close()


def test_cutout_failure_is_typed_and_does_not_reject_base_image(monkeypatch, tmp_path):
    engine = make_engine(tmp_path, cutout=True, batch="cutout-failure")
    def invalid(*args, **kwargs):
        raise ValueError("coverage below threshold")
    monkeypatch.setattr("prehnite.engine.make_cutout", invalid)
    try:
        output = engine.run()["asset_results"]["slot"]
        assert output["status"] == "failed_cutouts"
        assert output["failure"]["code"] == "cutout_validation_failed"
        assert output["outputs"] == ["slot.png"]
        assert engine.journal.fact("results")["slot"]["outputs"] == ["slot.png"]
    finally:
        engine.journal.close()


def test_budget_stop_has_typed_batch_failure_without_new_stage(monkeypatch, tmp_path):
    engine = make_engine(tmp_path, batch="budget-failure")
    def reject(asset):
        raise BudgetExceeded("do not purchase")
    monkeypatch.setattr(engine, "process", reject)
    try:
        with pytest.raises(BudgetExceeded):
            engine.run()
        report = json.loads((engine.journal.root / "report.json").read_text())
        assert report["batch_failure"]["code"] == "budget_limit"
        assert report["economics"]["actual_invoice_verified"] is False
        assert engine.journal.tasks() == []
    finally:
        engine.journal.close()


def test_backward_compatibility_accepted_and_old_rejected_assets():
    summary = summarize_failures(
        [{"task_key": "completed", "stage": "generation", "status": "completed",
          "provider": "demo", "request_id": None, "data": {}}],
        {"accepted": {"status": "accepted"}, "legacy": {"status": "rejected"},
         "old": {"status": "failed_cutouts"}})
    assert summary["stage_failure_counts"] == {}
    assert summary["asset_failure_counts"] == {
        "asset_rejected": 1, "cutout_validation_failed": 1,
    }
    assert classify_asset("accepted") is None
