"""Offline operator-reviewed source handoff: never regenerates, weakens policy or overwrites source."""
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from prehnite.engine import Engine
from prehnite.manifest import validate_job
from prehnite.schema import Manifest, Profile
from prehnite.store import Journal


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def packet(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    img = inputs / "reviewed-source.png"
    Image.new("RGB", (768, 1024), (130, 140, 150)).save(img)
    review = inputs / "original-human-review.md"
    review.write_text(
        "Original owner reviewed candidate: accepted for next stage.\n"
        "Target is table lamp excluding cord and tabletop.\n", encoding="utf-8")
    original_hash = digest(review)
    source_hash = digest(img)
    claims = {
        "schema_version": 1,
        "source_batch": "sdxl-1k-generation",
        "candidate_sha256": source_hash,
        "original_review_sha256": original_hash,
        "verdict": "accepted_for_next_stage",
        "target_phrase": "table lamp",
        "include": ["lamp body", "lampshade"],
        "exclude": ["power cord", "tabletop", "cast shadow", "background"],
    }
    attestation = inputs / "review-handoff.json"
    attestation.write_text(json.dumps(claims, sort_keys=True), encoding="utf-8")
    manifest = Manifest.model_validate({
        "id": "reviewed-cutout-new-batch",
        "assets": [{
            "id": "desk-lamp", "source": img.name,
            "aspect_ratio": "3:4", "target_size": [768, 1024],
            "targets": ["table-lamp"],
            "output": {
                "image": "photos/desk-lamp-reviewed.png",
                "cutouts": {"table-lamp": "cutouts/lamp.png"},
            },
        }],
        "handoff": {
            "source_batch": claims["source_batch"],
            "candidate_sha256": source_hash,
            "review_receipt": attestation.name,
            "review_receipt_sha256": digest(attestation),
            "review_document": review.name,
            "review_document_sha256": original_hash,
            "verdict": claims["verdict"],
            "target_phrase": claims["target_phrase"],
            "include": claims["include"],
            "exclude": claims["exclude"],
        },
    })
    profile = Profile.model_validate({
        "variants": [],
        "generation": {"provider": "disabled"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "disabled"},
        "segmentation": {"provider": "comfyui", "model": "user-segmentation",
                         "options": {"workflow": "cutout_api.json",
                                     "input_node": "1", "target_node": "4",
                                     "target_input": "prompt", "output_node": "6"}},
        "policy": {"maximum_attempts": 1, "uncertain": "reject"},
        "costs": {"allow_paid": False, "allow_cloud_uploads": False,
                  "max_usd": 0},
    })
    return inputs, manifest, profile, tmp_path / "workspace", claims


def test_verified_packet_accepts_for_segmentation_only(packet):
    inputs, manifest, profile, workspace, claims = packet
    validate_job(manifest, profile, inputs)
    assert not workspace.exists()


def test_handoff_runs_no_generation_or_judge_and_stages_pending_outputs(packet, monkeypatch):
    inputs, manifest, profile, workspace, claims = packet
    captured = []
    def fake_cutout(self, asset, selected, name, attempt, target_output, *, target_prompt=None):
        captured.append({"target": name, "phrase": target_prompt,
                         "src_sha": digest(selected), "attempt": attempt})
        target_output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (768, 1024), (55, 80, 100, 0)).save(target_output)
    monkeypatch.setattr(Engine, "cutout", fake_cutout)
    def never_generate(*args, **kwargs):
        pytest.fail("Reviewed handoff must not generate, even in dry-run tests")
    monkeypatch.setattr(Engine, "generate", never_generate)
    source_before = (inputs / "reviewed-source.png").read_bytes()
    review_before = (inputs / "original-human-review.md").read_bytes()
    original_root = workspace / "batches" / claims["source_batch"]
    engine = Engine(manifest, profile, workspace, inputs=inputs)
    try:
        report = engine.run()
        result = report["asset_results"]["desk-lamp"]
        assert result["status"] == "review_pending"
        assert result["cutout_status"] == "awaiting_human_review"
        assert result["generation_skipped"] is True
        assert result["automatic_quality_verified"] is False
        assert result["cutout_quality_verified"] is False
        assert engine.journal.fact("human_review_handoff")["review_receipt_sha256"]
        assert report["human_review_handoff"]["verdict"] == "accepted_for_next_stage"
        assert captured == [{"target": "table-lamp", "phrase": "table lamp",
                             "src_sha": claims["candidate_sha256"], "attempt": 1}]
        assert (engine.journal.root / "review_pending" / "cutouts/lamp.png").is_file()
        assert not (engine.journal.root / "selected").exists()
        # No unintended second local invocation, even on an explicit rerun.
        engine.run()
        assert len(captured) == 1
    finally:
        engine.journal.close()
    assert not original_root.exists()
    assert (inputs / "reviewed-source.png").read_bytes() == source_before
    assert (inputs / "original-human-review.md").read_bytes() == review_before


@pytest.mark.parametrize("mutation", ["source", "review", "receipt", "wrong_verdict",
                                        "wrong_phrase", "missing_receipt"])
def test_mismatches_rejected_before_any_batch_or_network(packet, mutation):
    inputs, manifest, profile, workspace, claims = packet
    if mutation == "source":
        (inputs / "reviewed-source.png").write_bytes(b"tampered")
    elif mutation == "review":
        (inputs / "original-human-review.md").write_text("rejected")
    elif mutation == "receipt":
        (inputs / "review-handoff.json").write_text('{"verdict":"rejected"}')
    elif mutation == "wrong_verdict":
        with pytest.raises(ValueError):
            manifest.handoff.verdict = "rejected"
        # Assigning Pydantic models isn't validated unless reloaded; force
        # strict serialized-contract evaluation via model validation instead.
        return
    elif mutation == "wrong_phrase":
        manifest.handoff.target_phrase = "power cord"
    elif mutation == "missing_receipt":
        (inputs / "review-handoff.json").unlink()
    with pytest.raises((ValueError, FileNotFoundError, OSError)):
        Engine(manifest, profile, workspace, inputs=inputs)
    assert not (workspace / "batches").exists()


@pytest.mark.parametrize("change", [
    lambda p: setattr(p.policy, "maximum_attempts", 2),
    lambda p: setattr(p.policy, "uncertain", "accept_unverified"),
    lambda p: setattr(p.costs, "allow_paid", True),
    lambda p: setattr(p.costs, "allow_cloud_uploads", True),
    lambda p: setattr(p.cache, "enabled", True),
    lambda p: setattr(p.generation, "provider", "comfyui"),
    lambda p: setattr(p.judge, "provider", "demo"),
    lambda p: setattr(p.upscale, "provider", "demo"),
    lambda p: setattr(p.segmentation, "provider", "disabled"),
    lambda p: setattr(p, "variants", ["native_1k"]),
])
def test_reviewed_handoff_rejects_unsafe_profiles_before_journal(packet, change):
    inputs, manifest, profile, workspace, _ = packet
    change(profile)
    with pytest.raises(ValueError):
        Engine(manifest, profile, workspace, inputs=inputs)
    assert not (workspace / "batches").exists()


def test_handoff_rejects_wrong_source_batch_and_generated_prompts(packet):
    inputs, manifest, profile, workspace, claims = packet
    manifest.id = claims["source_batch"]
    with pytest.raises(ValueError, match="new batch ID"):
        validate_job(Manifest.model_validate(manifest.model_dump()), profile, inputs)


def test_reviewed_cutout_failure_never_auto_retries(packet, monkeypatch):
    inputs, manifest, profile, workspace, _ = packet
    calls = []
    def failed_cutout(*args, **kwargs):
        calls.append(1)
        raise ValueError("synthetic segmentation error")
    monkeypatch.setattr(Engine, "cutout", failed_cutout)
    engine = Engine(manifest, profile, workspace, inputs=inputs)
    try:
        report = engine.run()
        assert report["asset_results"]["desk-lamp"]["cutout_status"] == "failed"
        engine.run()
        assert len(calls) == 1
        assert report["asset_results"]["desk-lamp"]["status"] == "review_pending"
    finally:
        engine.journal.close()


def test_empty_variants_without_handoff_stays_invalid(packet):
    inputs, manifest, profile, workspace, _ = packet
    manifest.handoff = None
    with pytest.raises(ValueError, match="explicit reviewed-source handoff"):
        validate_job(manifest, profile, inputs)
