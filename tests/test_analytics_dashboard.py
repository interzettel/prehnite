"""Offline production analytics and gallery integration regressions."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile

import pytest
from PIL import Image

from prehnite.analytics import build_analytics, render_analytics, write_analytics
from prehnite.engine import Engine
from prehnite.reporting import export_report, package
from prehnite.schema import Manifest, Profile
from prehnite.store import Journal


def _tasks():
    return [
        {"task_key": "a:generate", "stage": "generation", "status": "completed",
         "provider": "fal", "model": "test", "reserved_usd": 0.2,
         "tokens_in": 0, "tokens_out": 0,
         "data": {"secret": "private-dont-render"}},
        {"task_key": "b:judge", "stage": "judge", "status": "submitted",
         "provider": "anthropic", "model": "test", "reserved_usd": 0.03,
         "tokens_in": 200, "tokens_out": 60, "data": {}},
    ]


def _attempts():
    return [
        {"task_key": "a:generate", "stage": "generation", "provider": "fal",
         "outcome": "failed", "elapsed_ms": 10.0},
        {"task_key": "a:generate", "stage": "generation", "provider": "fal",
         "outcome": "completed", "elapsed_ms": 30.0},
        {"task_key": "b:judge", "stage": "judge", "provider": "anthropic",
         "outcome": "incomplete", "elapsed_ms": None},
    ]


def _manifest():
    return {"assets": [
        {"id": "a", "source": "photos/input.png", "aspect_ratio": "3:4"},
        {"id": "b", "prompt": "SECRET PROMPT", "aspect_ratio": "16:9"},
        {"id": "c", "prompt": "not sent", "aspect_ratio": "3:4"},
        {"id": "d", "source": "another.png", "aspect_ratio": "1:1"},
    ]}


def test_partial_batch_snapshot_cohorts_cost_unknowns_and_retry_histogram():
    results = {
        "a": {"status": "accepted"},
        "b": {"status": "error", "failure": {"code": "remote_request_pending"},
              "reason": "secret-request-id-123"},
        "d": {"status": "failed_cutouts"},
    }
    data = build_analytics(_manifest(), results, _tasks(), _attempts())
    assert data["schema_version"] == 1
    assert data["required_assets"] == 4
    assert data["processed_assets"] == 3
    assert data["asset_status_counts"] == {
        "accepted": 1, "failed_cutouts": 1, "rejected": 0, "error": 1, "pending": 1,
    }
    assert data["accepted_percent_of_required"] == 25.0
    assert sum(x["requested"] for x in data["input_mode"]) == 4
    assert sum(x["accepted"] for x in data["aspect_ratio"]) == 1
    assert data["current_asset_failure_codes"] == {
        "failed_cutouts": 1, "remote_request_pending": 1
    }
    assert data["current_unfinished_stage_states"] == {"submitted": 1}
    assert data["retry_distribution"] == {
        "no_invocation_recorded": 0, "one_invocation": 1,
        "two_invocations": 1, "three_or_more": 0,
    }
    assert data["reserved_usd"] == 0.23
    assert data["reserved_usd_per_accepted_asset"] == 0.23
    assert data["actual_invoiced_usd"] is None
    assert data["verified_invoice"] is False
    assert data["providers"][0]["provider"] == "anthropic"
    assert data["providers"][0]["observed_local_ms_p95"] is None
    assert data["providers"][0]["attempts_without_finished_timing"] == 1
    assert data["providers"][1]["observed_local_ms_p95"] == 30.0
    assert data["total_tokens_in"] == 200
    assert "secret-request-id" not in json.dumps(data)
    assert "SECRET PROMPT" not in json.dumps(data)
    assert "private-dont-render" not in json.dumps(data)


def test_analytics_csv_is_versioned_stable_and_no_raw_identifiers(tmp_path):
    data = build_analytics(_manifest(), {"a": {"status": "accepted"}},
                           _tasks(), _attempts())
    write_analytics(tmp_path, data)
    original = [(tmp_path / x).read_bytes() for x in ("analytics.json", "analytics.csv")]
    write_analytics(tmp_path, data)
    assert [(tmp_path / x).read_bytes() for x in
            ("analytics.json", "analytics.csv")] == original
    text = (tmp_path / "analytics.csv").read_text()
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    assert rows and set(x["schema_version"] for x in rows) == {"1"}
    assert {"provider", "stage", "retry_distribution", "asset_status"} <= {
        x["section"] for x in rows}
    assert "SECRET PROMPT" not in text
    assert "a:generate" not in text
    assert "secret-request-id" not in text
    assert json.loads((tmp_path / "analytics.json").read_text()) == data


def test_html_charts_escape_untrusted_values_and_never_execute_scripts():
    data = build_analytics(
        _manifest(),
        {"a": {"status": "accepted"},
         "b": {"status": "error",
               "failure": {"code": '<script>alert(1)</script>'}}},
        _tasks(), _attempts())
    page = render_analytics(data)
    assert "Delivery states" in page
    assert "Source type" in page
    assert "Stage efficiency" in page
    assert "Observed p95 ms" in page
    assert "Required-slot completion" in page
    assert "Verified invoice:</strong> unknown" in page
    assert "error" in data["current_asset_failure_codes"]
    assert "<script" not in page
    assert "onerror=" not in page
    assert 'aria-label="Accepted:' in page


def test_zero_acceptance_or_unknown_timing_are_not_fabricated():
    rows = [{"task_key": "z", "stage": "generation", "status": "running",
             "provider": "demo", "reserved_usd": 0.0,
             "tokens_in": 0, "tokens_out": 0, "data": {}}]
    a = build_analytics({"assets": [{"id": "z", "prompt": "safe"}]},
                        {"z": {"status": "error"}}, rows,
                        [{"task_key": "z", "stage": "generation",
                          "provider": "demo", "outcome": "incomplete",
                          "elapsed_ms": None}])
    assert a["accepted_assets"] == 0
    assert a["reserved_usd_per_accepted_asset"] is None
    assert a["stages"]["generation"]["observed_elapsed_ms_p95"] is None
    assert a["providers"][0]["observed_local_ms_p95"] is None
    assert "unknown" in render_analytics(a)


def _small_batch(tmp_path):
    manifest = Manifest.model_validate({"id": "analytic-batch", "assets": [
        {"id": "one", "prompt": "offline demo", "target_size": [192, 256],
         "aspect_ratio": "3:4", "output": {"image": "one.png"}}
    ]})
    profile = Profile.model_validate({
        "variants": ["native_4k"], "generation": {"provider": "demo",
                                                   "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
    })
    return Engine(manifest, profile, tmp_path)


def test_gallery_contains_dashboard_no_network_and_zip_receipts_are_correct(tmp_path):
    engine = _small_batch(tmp_path)
    try:
        report = engine.run()
        assert report["analytics"]["schema_version"] == 1
        assert report["analytics"]["accepted_assets"] == 1
        assert report["analytics"]["asset_status_counts"]["accepted"] == 1
        gallery = (engine.journal.root / "gallery.html").read_text()
        assert "BATCH INTELLIGENCE / V1" in gallery
        assert "Production snapshot" in gallery
        assert "Verified invoice:" in gallery
        assert "Selected: one.png" in gallery
        assert "connect-src 'none'" in gallery
        assert "<script" not in gallery
        assert "https://" not in gallery
        assert re.search(r'data:image/(?:png|jpeg);base64,', gallery)
        archive = engine.journal.root / "prehnite-analytic-batch.zip"
        original = archive.read_bytes()
        assert package(engine.journal).read_bytes() == original
        with zipfile.ZipFile(archive) as z:
            names = set(z.namelist())
            assert {"_prehnite/analytics.json", "_prehnite/analytics.csv",
                    "_prehnite/gallery.html"} <= names
            assert z.testzip() is None
            receipt = json.loads(z.read("_prehnite/archive-manifest.json"))
            for name, digest in receipt["sha256"].items():
                assert hashlib.sha256(z.read(name)).hexdigest() == digest
            assert json.loads(z.read("_prehnite/analytics.json")) == report["analytics"]
        again = engine.run()
        assert again["analytics"] == report["analytics"]
        assert package(engine.journal).read_bytes() == original
    finally:
        engine.journal.close()


def test_offline_gallery_90_items_and_no_new_external_assets(tmp_path):
    journal = Journal(tmp_path, "dashboard-90")
    try:
        assets = [{"id": f"slot-{i:03d}", "aspect_ratio": "1:1"}
                  for i in range(90)]
        journal.set_fact("manifest", {"assets": assets})
        journal.set_fact("results", {
            a["id"]: {"status": "rejected" if idx % 10 == 0 else "pending",
                      "outputs": []}
            for idx, a in enumerate(assets)
        })
        report = export_report(journal)
        assert report["analytics"]["required_assets"] == 90
        assert report["analytics"]["asset_status_counts"]["rejected"] == 9
        page = (journal.root / "gallery.html").read_text()
        assert page.count('class="asset"') == 90
        assert "90 assets" in page
        assert "Delivery states" in page
        assert "Aspect ratios" in page
        assert len(page.encode()) < 200_000
        assert not re.search(r'<script|<link|src="https?://', page)
    finally:
        journal.close()
