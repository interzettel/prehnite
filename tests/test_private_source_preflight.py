"""Offline privacy, byte-integrity and decoder tests for private pilot intake."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from prehnite.private_source_preflight import (
    SourcePreflightRefused, check_private_sources, run
)
from prehnite.real_cutout_eval import evaluate


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixtures(tmp_path):
    root = tmp_path / "private-assets"
    root.mkdir()
    objects = []
    for name, role, color in (
        ("WH-S003/front.webp", "front", (190, 119, 73)),
        ("WH-S014/care_label.webp", "care_label", (235, 238, 223)),
    ):
        path = root / name
        path.parent.mkdir(parents=True)
        Image.new("RGB", (64, 80), color).save(path, format="WEBP", quality=90)
        objects.append({
            "path": name, "role": role,
            "sha256": _hash(path), "size": path.stat().st_size,
        })
    return root, {"schema_version": 1, "objects": objects}


def test_verified_source_only_preflight_is_private_and_never_claims_iou(tmp_path):
    root, manifest = _fixtures(tmp_path)
    report = tmp_path / "source-only.json"
    original = {p.name: _hash(p) for p in root.rglob("*.webp")}
    mf = tmp_path / "manifest.json"
    mf.write_text(json.dumps(manifest))
    result = run(mf, root, report)
    assert result["decoded_source_count"] == 2
    assert result["roles"] == {"front": 1, "care_label": 1}
    assert result["local_byte_hashes_verified"] is True
    assert result["ground_truth_masks_supplied"] == 0
    assert result["mask_iou_calculated"] is False
    assert result["paid_usd"] == 0
    assert result["provider_requests"] == 0
    assert all(x["width"] == 64 and x["height"] == 80 for x in result["items"])
    text = report.read_text()
    assert "WH-S003" not in text
    assert "WH-S014" not in text
    assert str(root.resolve()) not in text
    assert "image/webp" not in text
    assert all(_hash(p) == original[p.name] for p in root.rglob("*.webp"))


@pytest.mark.parametrize("problem,reason", [
    ("tamper", "source_sha256_mismatch"),
    ("size", "source_byte_size_mismatch"),
    ("absolute", "unsafe_source_path"),
    ("traversal", "unsafe_source_path"),
    ("duplicate", "duplicate_source_path"),
    ("invalidrole", "invalid_source_role"),
])
def test_unverifiable_assets_are_rejected_without_leaking_name(tmp_path, problem, reason):
    root, manifest = _fixtures(tmp_path)
    one = manifest["objects"][0]
    if problem == "tamper":
        path = root / one["path"]
        # Flip one trailing byte without altering the file length.
        binary = bytearray(path.read_bytes())
        binary[-1] ^= 1
        path.write_bytes(binary)
    if problem == "size":
        one["size"] += 10
    if problem == "absolute":
        one["path"] = str((root / one["path"]).resolve())
    if problem == "traversal":
        one["path"] = "../elsewhere.webp"
    if problem == "duplicate":
        manifest["objects"].append(dict(one))
    if problem == "invalidrole":
        one["role"] = "ground_truth"
    with pytest.raises(SourcePreflightRefused, match=reason):
        check_private_sources(manifest, root)


def test_wrong_file_signature_is_rejected_even_when_hash_matches(tmp_path):
    root, manifest = _fixtures(tmp_path)
    path = root / manifest["objects"][0]["path"]
    Image.new("RGB", (64, 80), (15, 20, 50)).save(path, format="PNG")
    manifest["objects"][0]["sha256"] = _hash(path)
    manifest["objects"][0]["size"] = path.stat().st_size
    with pytest.raises(SourcePreflightRefused, match="not_webp_source"):
        check_private_sources(manifest, root)


def test_corrupt_webp_rejected_with_valid_hash(tmp_path):
    root, manifest = _fixtures(tmp_path)
    path = root / manifest["objects"][0]["path"]
    path.write_bytes(b"RIFF" + b"\x00" * 24)
    manifest["objects"][0]["sha256"] = _hash(path)
    manifest["objects"][0]["size"] = path.stat().st_size
    with pytest.raises(SourcePreflightRefused, match="source_image_decode_failed"):
        check_private_sources(manifest, root)


def test_preflight_report_cannot_overwrite_any_source(tmp_path):
    root, manifest = _fixtures(tmp_path)
    mf = tmp_path / "manifest.json"
    mf.write_text(json.dumps(manifest))
    with pytest.raises(SourcePreflightRefused, match="report_overlaps_private_inputs"):
        run(mf, root, root / "source-report.json")
    with pytest.raises(SourcePreflightRefused, match="report_overlaps_private_inputs"):
        run(mf, root, mf)


def test_real_alpha_scorer_accepts_webp_source_but_requires_separate_mattes(tmp_path):
    root, _ = _fixtures(tmp_path)
    source = root / "WH-S003/front.webp"
    gold = root / "reference.png"
    candidate = root / "candidate.png"
    Image.new("L", (64, 80), 255).save(gold)
    Image.new("L", (64, 80), 255).save(candidate)
    payload = {
        "schema_version": 1, "items": [{
            "cohort": "opaque-product", "reference_review": "unreviewed",
            "rights": {"source_type": "owner-authorized",
                       "right_to_process_attested": True},
            "paths": {"source": "WH-S003/front.webp",
                      "reference": "reference.png", "candidate": "candidate.png"},
            "sha256": {"source": _hash(source),
                       "reference": _hash(gold), "candidate": _hash(candidate)},
        }]
    }
    result = evaluate(payload, root)
    assert result["items"][0]["metrics"]["binary_iou_128"] == 1.0
    assert result["items"][0]["reference_review"] == "unreviewed"
    assert result["human_visual_acceptance_established"] is False
