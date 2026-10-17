"""Read-only technical evidence must not imply image quality or change source data."""
import json
import hashlib

import pytest
from PIL import Image

from prehnite import trial_evidence as evidence


@pytest.fixture
def pair(tmp_path, monkeypatch):
    images = tmp_path / "outputs"
    images.mkdir()
    Image.new("RGB", (128, 192), (90, 60, 40)).save(images / "generated.png")
    matte = Image.new("RGBA", (128, 192), (50, 100, 150, 255))
    for x in range(64):
        for y in range(192):
            matte.putpixel((x, y), (50, 100, 150, 0))
    matte.save(images / "cutout.png")
    monkeypatch.setattr(evidence, "hardware_report", lambda: {
        "hardware_tier_certified": False, "performance_benchmarked": False,
        "os": {"system": "synthetic-test-only"},
    })
    return images, tmp_path / "receipt.json"


def make(pair, **kwargs):
    images, target = pair
    return evidence.evidence_receipt(
        root=images, generated="generated.png", cutout="cutout.png",
        output=target, **kwargs
    )


def test_real_technical_receipt_is_create_only_hash_bound_and_not_quality_claim(pair):
    root, report_path = pair
    originals = [(p.read_bytes(), p.stat().st_mtime_ns) for p in
                 [root / "generated.png", root / "cutout.png"]]
    report = make(pair)
    assert report_path.is_file()
    assert report["geometry_match"] is True
    assert report["alpha_has_transparency_and_content"] is True
    assert report["human_review"] == "unreviewed"
    assert report["human_review_independently_verified"] is False
    assert report["quality_scores"] == "not_measured_without_reviewed_alpha_reference"
    assert report["calls_during_evidence_creation"] == 0
    assert report["operator_measurements"]["status"] == "not_provided"
    assert report["assets"]["cutout"]["sha256"] == hashlib.sha256(
        (root / "cutout.png").read_bytes()).hexdigest()
    assert originals == [(p.read_bytes(), p.stat().st_mtime_ns) for p in
                         [root / "generated.png", root / "cutout.png"]]
    assert json.loads(report_path.read_text())["schema_version"] == 1
    with pytest.raises(FileExistsError):
        make(pair)


def test_optional_owner_measured_performance_is_labelled_unverified(pair):
    report = make(pair, elapsed_seconds=34.2, peak_vram_mib=6400,
                  measurement_method="nvidia-smi sampled per second during run",
                  human_review="accepted")
    assert report["operator_measurements"]["status"] == "owner_supplied_unverified"
    assert report["operator_measurements"]["peak_vram_mib"] == 6400
    assert report["human_review"] == "accepted"
    assert report["human_review_independently_verified"] is False


@pytest.mark.parametrize("elapsed,peak,method", [
    (1.0, None, None), (None, 500, None),
    (float("nan"), None, "wall clock"), (-2.0, None, "wall clock"),
    (None, 0, "nvidia-smi"), (None, None, "manual"),
])
def test_invalid_metrics_refused_without_writes(pair, elapsed, peak, method):
    with pytest.raises(ValueError):
        make(pair, elapsed_seconds=elapsed, peak_vram_mib=peak,
             measurement_method=method)
    assert not pair[1].exists()


def test_opaque_rgba_masquerading_as_cutout_refused(pair):
    root, output = pair
    Image.new("RGBA", (128, 192), (10, 20, 30, 255)).save(root / "cutout.png")
    with pytest.raises(ValueError, match="transparent"):
        make(pair)
    assert not output.exists()


def test_mask_only_grayscale_refused(pair):
    root, output = pair
    Image.new("L", (128, 192), 128).save(root / "cutout.png")
    with pytest.raises(ValueError, match="RGBA PNG"):
        make(pair)
    assert not output.exists()


def test_mismatched_dimensions_refused(pair):
    root, output = pair
    Image.new("RGBA", (256, 256), (0, 0, 0, 0)).save(root / "cutout.png")
    with pytest.raises(ValueError, match="geometries differ|transparent"):
        make(pair)
    assert not output.exists()


def test_path_traversal_and_output_overlap_refused(pair):
    root, output = pair
    with pytest.raises(ValueError, match="Path traversal|canonical"):
        evidence.evidence_receipt(root=root, generated="../elsewhere.png",
                                  cutout="cutout.png", output=output)
    with pytest.raises(ValueError, match="outside"):
        evidence.evidence_receipt(root=root, generated="generated.png",
                                  cutout="cutout.png", output=root / "report.json")
    assert not output.exists()


def test_overwrite_never_allowed(pair):
    root, output = pair
    output.write_text("DO NOT OVERWRITE", encoding="utf-8")
    with pytest.raises(FileExistsError):
        make(pair)
    assert output.read_text() == "DO NOT OVERWRITE"
