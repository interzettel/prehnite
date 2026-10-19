"""Eight-GiB SDXL pilot: zero-network dry run and human-score contract."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

from prehnite.engine import Engine
from prehnite.manifest import load_manifest, load_profile, validate_job
from prehnite.registry import validate_capability
from prehnite.schema import Endpoint

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/manifest-8g-sdxl-pilot.yaml"
LOCAL = ROOT / "examples/profile-8g-sdxl-pilot.yaml"
DEMO = ROOT / "examples/profile-8g-sdxl-offline-demo.yaml"


def _module():
    spec = importlib.util.spec_from_file_location("score_8g_pilot", ROOT / "scripts/score_8g_pilot.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pilot_has_ten_distinct_seeded_native_images_and_no_paid_fallback(tmp_path):
    manifest = load_manifest(MANIFEST)
    assert len(manifest.assets) == 10
    assert len({asset.seed for asset in manifest.assets}) == 10
    assert len({asset.output.image for asset in manifest.assets}) == 10
    assert all(not asset.targets and asset.prompt for asset in manifest.assets)
    for profile_path in (LOCAL, DEMO):
        profile = load_profile(profile_path)
        validate_job(manifest, profile, tmp_path)
        assert profile.variants == ["native_1k"]
        assert profile.costs.max_usd == 0
        assert profile.costs.allow_paid is False
        assert profile.costs.allow_cloud_uploads is False
        assert profile.policy.maximum_attempts == 1
        assert profile.policy.uncertain == "accept_unverified"
        assert profile.segmentation.provider == "disabled"
        assert profile.upscale.provider == "disabled"
        assert profile.judge.provider == "demo"
    assert load_profile(LOCAL).generation.provider == "comfyui"
    assert load_profile(DEMO).generation.provider == "demo"


def test_only_demo_native_1k_is_newly_allowed_not_paid_fal():
    validate_capability(Endpoint(provider="demo", model="synthetic"),
                        "generate", ratio="3:4", tier="1k")
    with pytest.raises(ValueError, match="does not support tier"):
        validate_capability(
            Endpoint(provider="fal", model="blackforestlabs/flux-3/klein/text-to-image"),
            "generate", ratio="3:4", tier="1k"
        )


def test_real_ten_asset_manifest_runs_reliably_in_offline_demo(tmp_path):
    manifest = load_manifest(MANIFEST)
    profile = load_profile(DEMO)
    workspace = tmp_path / "workspace"
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    first = Engine(manifest, profile, workspace, inputs)
    try:
        report = first.run()
        assert len(report["asset_results"]) == 10
        assert all(r["status"] == "accepted" for r in report["asset_results"].values())
        assert all(r.get("visual_quality_verified") is False
                   for r in report["asset_results"].values())
        digests = {k: r["outputs_sha256"] for k, r in report["asset_results"].items()}
        stage_count = len(report.get("operations_detail", []))
        assert report["cost_estimated_or_reserved_usd"] == 0
    finally:
        first.journal.close()
    second = Engine(manifest, profile, workspace, inputs)
    try:
        repeated = second.run()
        assert len(repeated["asset_results"]) == 10
        assert {k: r["outputs_sha256"] for k, r in repeated["asset_results"].items()} == digests
        assert len(repeated.get("operations_detail", [])) == stage_count
        assert repeated["cost_estimated_or_reserved_usd"] == 0
    finally:
        second.journal.close()


def _private_receipt(tmp_path):
    source = _module()
    plan = source.plan(MANIFEST)
    root = tmp_path / "private-output"
    root.mkdir()
    entries = []
    for i, asset in enumerate(plan["assets"]):
        destination = root / asset["output"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (768, 1024), (i * 19, i * 13, i * 7)).save(destination)
        entries.append({
            "id": asset["id"], "outcome": "generated",
            "relative_output": asset["output"],
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "decision": "accept",
            "rubric": dict.fromkeys(plan["review_dimensions"], 4),
            "elapsed_seconds": 20 + i,
            "sampled_peak_vram_mib": 5000 + i,
            "min_available_ram_mib": 6500 - i,
        })
    receipt = {
        "schema_version": 1, "batch_id": plan["batch_id"],
        "origin": "synthetic_demo", "operator": "CI fixture",
        "reviewer": "Synthetic reviewer",
        "reviewed_at": datetime.now(tz=timezone.utc).isoformat(),
        "model_sha256": "1" * 64, "workflow_sha256": "2" * 64,
        "assets": entries,
    }
    receipt_path = tmp_path / "review.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return source, root, receipt_path, receipt


def test_synthetic_review_math_never_claims_real_image_acceptance(tmp_path):
    source, root, receipt_path, data = _private_receipt(tmp_path)
    result = source.evaluate(MANIFEST, root, receipt_path)
    assert result["reviewed_items"] == 10
    assert result["accepted_yield_percent"] == 100.0
    assert result["generated_images_checked"] == 10
    assert result["resource_sample_count"] == 10
    assert result["seconds_per_accepted_image"] == 24.5
    assert result["independently_verified"] is False
    assert result["eligible_as_accepted_real_batch"] is False
    assert "operator_report_only" in result["outcome"]


def test_rejected_failed_generation_counts_as_failure_without_fake_output(tmp_path):
    source, root, receipt_path, data = _private_receipt(tmp_path)
    data["assets"][0] = {
        "id": data["assets"][0]["id"], "outcome": "failed",
        "decision": "reject", "failure_reason": "cuda_oom",
        "elapsed_seconds": 20,
        "sampled_peak_vram_mib": None,
        "min_available_ram_mib": None,
    }
    receipt_path.write_text(json.dumps(data), encoding="utf-8")
    result = source.evaluate(MANIFEST, root, receipt_path)
    assert result["generated_images_checked"] == 9
    assert result["failed_generation_attempts"] == 1
    assert result["accepted_yield_percent"] == 90.0
    assert result["resource_sample_count"] == 9
    assert result["rejection_reasons"] == {"cuda_oom": 1}


def test_forger_and_invalid_review_fields_fail_closed(tmp_path):
    source, root, receipt_path, data = _private_receipt(tmp_path)
    for edit in (
        lambda d: d["assets"][0].update({"sha256": "0" * 64}),
        lambda d: d["assets"][0].update({"elapsed_seconds": True}),
        lambda d: d["assets"][0].update({"rubric": {"prompt_adherence": 5}}),
        lambda d: d["assets"][0].update({"decision": "maybe"}),
        lambda d: d["assets"].append(deepcopy(d["assets"][0])),
        lambda d: d.update({"origin": "real_local_comfyui"}),
        lambda d: d.update({"reviewed_at": "2026-10-19T10:30:00"}),
    ):
        tampered = deepcopy(data)
        edit(tampered)
        receipt_path.write_text(json.dumps(tampered), encoding="utf-8")
        with pytest.raises(ValueError):
            source.evaluate(MANIFEST, root, receipt_path)
