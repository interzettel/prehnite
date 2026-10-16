"""No-network rights, hash, geometry and privacy gates for real-image evaluation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from prehnite.real_cutout_eval import EvaluationRefused, evaluate, run


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def example(tmp_path):
    root = tmp_path / "private-corpus"
    root.mkdir()
    source = Image.new("RGB", (48, 48), (110, 180, 90))
    gold = Image.new("L", source.size, 0)
    ImageDraw.Draw(gold).ellipse((8, 8, 39, 39), fill=255)
    gold.putpixel((7, 24), 80)
    proposed = gold.copy()
    proposed.putpixel((7, 24), 0)
    paths = {"source": root / "private-photo.png",
             "reference": root / "manually-reviewed-alpha.png",
             "candidate": root / "model-estimate.png"}
    for path, image in ((paths["source"], source),
                        (paths["reference"], gold),
                        (paths["candidate"], proposed)):
        image.save(path)
    item = {
        "cohort": "portrait-hair",
        "rights": {"source_type": "owner-authorized",
                   "right_to_process_attested": True},
        "reference_review": "reviewed",
        "paths": {key: path.name for key, path in paths.items()},
        "sha256": {key: _sha(path) for key, path in paths.items()},
    }
    return root, {"schema_version": 1, "items": [item]}, paths


def test_soft_alpha_reference_metrics_and_privacy_proof(tmp_path):
    root, manifest, files = example(tmp_path)
    report = tmp_path / "private-metrics.json"
    manifest_file = tmp_path / "intake.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    result = run(manifest_file, root, report)
    assert result["count"] == 1
    assert result["paid_usd"] == 0
    assert result["provider_requests"] == 0
    assert result["human_visual_acceptance_established"] is False
    assert result["rights_independently_verified"] is False
    scores = result["items"][0]["metrics"]
    assert 0 < scores["normalized_alpha_mae"] < 0.002
    assert scores["binary_iou_128"] == 1.0  # low-opacity hair still matters for MAE
    assert scores["alpha_sad_pixels"] > 0
    assert scores["normalized_edge_mae_3x3"] > 0
    assert result["per_cohort"]["portrait-hair"]["count"] == 1
    private = report.read_text()
    assert "private-photo.png" not in private
    assert "manually-reviewed-alpha.png" not in private
    assert str(root.resolve()) not in private
    assert "model-estimate.png" not in private
    assert report.read_bytes().startswith(b"{")
    # Scorer is observational. All source assets remain byte-identical.
    assert all(_sha(path) == manifest["items"][0]["sha256"][key]
               for key, path in files.items())


def test_reference_not_reviewed_has_no_implicit_quality_acceptance(tmp_path):
    root, manifest, _ = example(tmp_path)
    manifest["items"][0]["reference_review"] = "unreviewed"
    result = evaluate(manifest, root)
    assert result["items"][0]["reference_review"] == "unreviewed"
    assert result["items"][0]["human_visual_acceptance"] == "not_assessed"


@pytest.mark.parametrize("violation,reason", [
    ("no_attestation", "processing_rights_not_attested"),
    ("bad_license", "third_party_license_provenance_incomplete"),
    ("sha_mismatch", "input_sha256_mismatch"),
    ("absolute", "unsafe_relative_path"),
    ("traversal", "unsafe_relative_path"),
    ("bad_cohort", "unsupported_cohort"),
    ("unknown_review", "reference_review_status_required"),
])
def test_invalid_provenance_and_inputs_are_refused(tmp_path, violation, reason):
    root, manifest, files = example(tmp_path)
    item = manifest["items"][0]
    if violation == "no_attestation":
        item["rights"]["right_to_process_attested"] = False
    elif violation == "bad_license":
        item["rights"] = {"source_type": "third-party-licensed",
                          "right_to_process_attested": True,
                          "license_id": "MIT"}
    elif violation == "sha_mismatch":
        item["sha256"]["candidate"] = "0" * 64
    elif violation == "absolute":
        item["paths"]["source"] = str(files["source"].resolve())
    elif violation == "traversal":
        item["paths"]["source"] = "../outside.png"
    elif violation == "bad_cohort":
        item["cohort"] = "unverified"
    elif violation == "unknown_review":
        item["reference_review"] = "probably good"
    with pytest.raises(EvaluationRefused, match=reason):
        evaluate(manifest, root)


def test_third_party_rights_require_provenance_and_do_not_leak_it(tmp_path):
    root, manifest, _ = example(tmp_path)
    item = manifest["items"][0]
    item["rights"] = {
        "source_type": "third-party-licensed",
        "right_to_process_attested": True,
        "license_id": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source_url": "https://example.org/photo",
        "creator": "A creator whose name must not leak into private reports",
    }
    result = evaluate(manifest, root)
    serialized = json.dumps(result)
    assert "A creator" not in serialized
    assert "example.org" not in serialized
    assert result["rights_independently_verified"] is False


def test_matte_geometry_and_source_hash_protected(tmp_path):
    root, manifest, files = example(tmp_path)
    Image.new("L", (47, 48), 255).save(files["candidate"])
    manifest["items"][0]["sha256"]["candidate"] = _sha(files["candidate"])
    with pytest.raises(EvaluationRefused, match="source_reference_candidate_dimensions_mismatch"):
        evaluate(manifest, root)


def test_grayscale_png_or_explicit_rgba_alpha_only(tmp_path):
    root, manifest, files = example(tmp_path)
    with Image.open(files["candidate"]) as old:
        rgba = Image.new("RGBA", old.size, (255, 255, 255, 0))
        rgba.putalpha(old)
        rgba.save(files["candidate"])
    manifest["items"][0]["sha256"]["candidate"] = _sha(files["candidate"])
    assert evaluate(manifest, root)["count"] == 1
    with Image.open(files["candidate"]) as old:
        old.convert("RGB").save(files["candidate"])
    manifest["items"][0]["sha256"]["candidate"] = _sha(files["candidate"])
    with pytest.raises(EvaluationRefused, match="matte_must_be_grayscale_or_rgba_png"):
        evaluate(manifest, root)


def test_no_report_can_replace_private_source_or_matte(tmp_path):
    root, manifest, files = example(tmp_path)
    mf = tmp_path / "manifest.json"
    mf.write_text(json.dumps(manifest))
    with pytest.raises(EvaluationRefused, match="report_output_overlaps_inputs"):
        run(mf, root, files["candidate"])
    assert _sha(files["candidate"]) == manifest["items"][0]["sha256"]["candidate"]
    with pytest.raises(EvaluationRefused, match="report_output_overlaps_inputs"):
        run(mf, root, mf)
    assert mf.read_text().startswith("{")


def test_empty_and_unbounded_corpus_refused(tmp_path):
    root, manifest, _ = example(tmp_path)
    manifest_original_item = manifest["items"][0]
    manifest["items"] = []
    with pytest.raises(EvaluationRefused, match="invalid_manifest_item_count"):
        evaluate(manifest, root)
    manifest["items"] = [manifest_original_item] * 201
    with pytest.raises(EvaluationRefused, match="invalid_manifest_item_count"):
        evaluate(manifest, root)

def test_empty_reference_matte_never_scores_as_perfect_iou(tmp_path):
    root, manifest, files = example(tmp_path)
    Image.new("L", (48, 48), 0).save(files["reference"])
    manifest["items"][0]["sha256"]["reference"] = _sha(files["reference"])
    with pytest.raises(EvaluationRefused, match="empty_reference_mask_cannot_establish_quality"):
        evaluate(manifest, root)
