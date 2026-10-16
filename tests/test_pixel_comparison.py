"""Conservative image-grid diagnostics; no unaligned subtraction or paid services."""
from __future__ import annotations

import hashlib
import json
import zipfile

import pytest
from PIL import Image
from typer.testing import CliRunner

from prehnite.artifacts import ArtifactIntegrityError
from prehnite.cli import app
from prehnite.images import image_info
from prehnite.pixel_comparison import MAX_METRIC_PIXELS, compare_slot
from prehnite.reporting import export_report, package
from prehnite.store import Journal


def sample(tmp_path, *, size=(24, 32), with_cutout=False, source=True, batch="grid"):
    workspace, inputs = tmp_path / "workspace", tmp_path / "inputs"
    inputs.mkdir(exist_ok=True)
    j = Journal(workspace, batch)
    original = inputs / "reference.png"
    Image.new("RGB", size, (80, 120, 160)).save(original)
    selected = j.root / "selected/photos/base.png"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_bytes(original.read_bytes())
    outputs = ["photos/base.png"]
    hashes = {outputs[0]: image_info(selected)["sha256"]}
    cutouts = {}
    if with_cutout:
        rel = "cutouts/subject.png"
        dest = j.root / "selected" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        im = Image.new("RGBA", size, (80, 120, 160, 255))
        im.putpixel((3, 4), (80, 120, 160, 128))
        im.save(dest)
        outputs.append(rel)
        hashes[rel] = image_info(dest)["sha256"]
        cutouts["subject"] = rel
    asset = {"id": "one", "output": {"image": outputs[0], "cutouts": cutouts}}
    if source:
        asset["source"] = "reference.png"
        j.set_fact("input_file_sha256", {"one": image_info(original)["sha256"]})
    else:
        asset["prompt"] = "PRIVATE PROMPT DO NOT LEAK"
    j.set_fact("manifest", {"assets": [asset]})
    j.set_fact("results", {"one": {
        "status": "accepted", "outputs": outputs, "outputs_sha256": hashes,
        "reason": "SECRET INTERNAL REASON",
    }})
    return j, inputs, original, selected


def update_digest(j, rel):
    data = j.fact("results")
    dest = j.root / "selected" / rel
    data["one"]["outputs_sha256"][rel] = image_info(dest)["sha256"]
    j.set_fact("results", data)


def test_identical_verified_original_has_zero_changed_pixels_and_private_evidence(tmp_path):
    j, inputs, _, _ = sample(tmp_path)
    try:
        result = compare_slot(j, "one", inputs=inputs, same_grid_asserted=True)
        assert result["status"] == "comparable"
        assert result["registration"] == "operator_asserted_same_pixel_grid_no_computed_transform"
        assert result["geometric_transform"] is None
        assert result["metrics"]["changed_pixel_count"] == 0
        assert result["metrics"]["mean_composited_channel_delta_0_1"] == 0
        assert result["human_quality_judgment"] is None
        assert result["actual_provider_invoice_usd"] is None
        root = j.root / "reviews"
        assert (root / "one-difference-original.png").is_file()
        record = json.loads((root / "one-difference-original.json").read_text())
        assert record == result
        assert hashlib.sha256((root / "one-difference-original.png").read_bytes()).hexdigest() == (
            record["heatmap_sha256"])
        html = (root / "one-difference-original.html").read_text()
        assert "Native 1:1" in html and "Encoded delta heatmap" in html
        assert "Operator-asserted pixel grid" in html
        assert "connect-src 'none'" in html and "<script" not in html
        assert "PRIVATE PROMPT" not in html and "SECRET INTERNAL REASON" not in html
    finally:
        j.close()


def test_single_pixel_delta_is_measured_without_quality_rating(tmp_path):
    j, inputs, _, base = sample(tmp_path)
    try:
        with Image.open(base) as original:
            changed = original.copy()
        changed.putpixel((4, 5), (255, 0, 0))
        changed.save(base)
        update_digest(j, "photos/base.png")
        outcome = compare_slot(j, "one", inputs=inputs, same_grid_asserted=True)
        assert outcome["metrics"]["changed_pixel_count"] == 1
        assert outcome["metrics"]["changed_pixel_fraction"] == round(1 / (24 * 32), 8)
        assert outcome["metrics"]["mean_composited_channel_delta_0_1"] > 0
        assert outcome["human_quality_judgment"] is None
        with Image.open(j.root / "reviews/one-difference-original.png") as heat:
            assert heat.getpixel((4, 5))[0] > 0
            assert heat.getpixel((0, 0)) == (0, 0, 0)
    finally:
        j.close()


def test_mismatched_geometry_returns_named_refusal_without_heatmap(tmp_path):
    j, inputs, _, base = sample(tmp_path)
    try:
        Image.new("RGB", (24, 33), (80, 120, 160)).save(base)
        update_digest(j, "photos/base.png")
        result = compare_slot(j, "one", inputs=inputs, same_grid_asserted=True)
        assert result["status"] == "not_comparable"
        assert result["reason_code"] == "geometry_mismatch"
        assert result["reference_dimensions"] == [24, 32]
        assert result["candidate_dimensions"] == [24, 33]
        assert result["metrics"] is None
        assert not (j.root / "reviews/one-difference-original.png").exists()
    finally:
        j.close()


def test_same_size_translation_requires_manual_attestation_and_is_not_quality(tmp_path):
    j, inputs, _, base = sample(tmp_path)
    try:
        with Image.open(base) as im:
            img = im.copy()
        img.putpixel((1, 1), (255, 0, 0))
        img.putpixel((2, 1), (0, 255, 0))
        img.save(base)
        update_digest(j, "photos/base.png")
        with pytest.raises(ValueError, match="attestation"):
            compare_slot(j, "one", inputs=inputs)
        assert not (j.root / "reviews/one-difference-original.json").exists()
        r = compare_slot(j, "one", inputs=inputs, same_grid_asserted=True)
        assert r["registration"].startswith("operator_asserted")
        assert r["geometric_transform"] is None
        assert r["metrics"]["changed_pixel_count"] == 2
    finally:
        j.close()


def test_exif_orientation_six_is_refused_not_silently_rotated(tmp_path):
    j, inputs, original, _ = sample(tmp_path)
    try:
        image = Image.new("RGB", (24, 32), "green")
        exif = Image.Exif()
        exif[274] = 6
        original.unlink()
        source = inputs / "rotated.jpg"
        image.save(source, exif=exif)
        manifest = j.fact("manifest")
        manifest["assets"][0]["source"] = "rotated.jpg"
        j.set_fact("manifest", manifest)
        j.set_fact("input_file_sha256", {"one": image_info(source)["sha256"]})
        result = compare_slot(j, "one", inputs=inputs, same_grid_asserted=True)
        assert result["status"] == "not_comparable"
        assert result["reason_code"] == "orientation_unresolved"
    finally:
        j.close()


def test_conflicting_icc_profiles_refused_without_visual_delta(tmp_path):
    j, inputs, _, base = sample(tmp_path)
    try:
        Image.new("RGB", (24, 32), "red").save(base, icc_profile=b"untrusted-profile-blob")
        update_digest(j, "photos/base.png")
        result = compare_slot(j, "one", inputs=inputs, same_grid_asserted=True)
        assert result["status"] == "not_comparable"
        assert result["reason_code"] == "color_profile_mismatch"
        assert not (j.root / "reviews/one-difference-original.html").exists()
    finally:
        j.close()


def test_alpha_fringe_and_hidden_rgb_separated_by_black_white_composites(tmp_path):
    j, _, _, base = sample(tmp_path, source=False, with_cutout=True)
    try:
        result = compare_slot(j, "one", cutout="subject", same_grid_asserted=True)
        assert result["status"] == "comparable"
        assert result["comparison"] == "base_vs_cutout"
        assert result["metrics"]["candidate_partial_alpha_fraction"] == round(1 / (24 * 32), 8)
        assert result["metrics"]["reference_partial_alpha_fraction"] == 0
        assert result["metrics"]["changed_pixel_count"] == 1
        assert (j.root / "reviews/one-difference-cutout.html").exists()
        # Both alpha zero pixels should compare as identical on both backgrounds
        # regardless of their hidden RGB channel values.
        im = Image.new("RGBA", (24, 32), (10, 20, 30, 0))
        im.save(base)
        rel = "cutouts/subject.png"
        cutout_path = j.root / "selected" / rel
        Image.new("RGBA", (24, 32), (200, 210, 220, 0)).save(cutout_path)
        update_digest(j, "photos/base.png")
        update_digest(j, rel)
        hidden = compare_slot(j, "one", cutout="subject", same_grid_asserted=True)
        assert hidden["metrics"]["changed_pixel_count"] == 0
    finally:
        j.close()


def test_tampered_recorded_image_never_generates_new_evidence(tmp_path):
    j, inputs, _, base = sample(tmp_path)
    try:
        base.write_bytes(b"not an image")
        with pytest.raises(ArtifactIntegrityError):
            compare_slot(j, "one", inputs=inputs, same_grid_asserted=True)
        assert not (j.root / "reviews/one-difference-original.json").exists()
    finally:
        j.close()


def test_original_symlink_escape_is_rejected_even_with_matching_hash(tmp_path):
    j, inputs, src, _ = sample(tmp_path)
    try:
        outside = tmp_path / "outside.png"
        outside.write_bytes(src.read_bytes())
        src.unlink()
        try:
            src.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("Local symlinks not enabled for this OS/account")
        with pytest.raises(ValueError, match="approved input root"):
            compare_slot(j, "one", inputs=inputs, same_grid_asserted=True)
    finally:
        j.close()


def test_pixel_budget_block_is_explicit_and_does_not_decode_for_metrics(tmp_path):
    j, inputs, original, base = sample(tmp_path)
    try:
        assert MAX_METRIC_PIXELS == 4_000_000
        Image.new("RGB", (2001, 2000), (80, 120, 160)).save(original)
        base.write_bytes(original.read_bytes())
        j.set_fact("input_file_sha256", {"one": image_info(original)["sha256"]})
        update_digest(j, "photos/base.png")
        result = compare_slot(j, "one", inputs=inputs, same_grid_asserted=True)
        assert result["status"] == "not_comparable"
        assert result["reason_code"] == "metric_pixel_budget_exceeded"
        assert not (j.root / "reviews/one-difference-original.png").exists()
    finally:
        j.close()


def test_cli_explicit_attestation_and_default_zip_stays_identical(tmp_path):
    j, inputs, _, _ = sample(tmp_path, batch="cli-pixel")
    try:
        export_report(j)
        existing = package(j).read_bytes()
    finally:
        j.close()
    base = ["compare", "cli-pixel", "--asset", "one",
            "--workspace", str(tmp_path / "workspace"),
            "--inputs", str(inputs)]
    runner = CliRunner()
    no = runner.invoke(app, base)
    assert no.exit_code != 0
    assert "attestation" in str(no.exception) or "attestation" in no.output
    yes = runner.invoke(app, base + ["--assume-same-grid"])
    assert yes.exit_code == 0, yes.output
    out = json.loads(yes.output)
    assert out["status"] == "comparable"
    j = Journal(tmp_path / "workspace", "cli-pixel")
    try:
        assert package(j).read_bytes() == existing
        with zipfile.ZipFile(package(j)) as z:
            assert not any("difference" in p for p in z.namelist())
    finally:
        j.close()


def test_prompt_source_and_unapproved_cutout_are_denied(tmp_path):
    j, inputs, _, _ = sample(tmp_path, source=False)
    try:
        with pytest.raises(ValueError, match="no original"):
            compare_slot(j, "one", inputs=inputs, same_grid_asserted=True)
        with pytest.raises(ValueError, match="not a recorded selected output"):
            compare_slot(j, "one", cutout="fictional", same_grid_asserted=True)
        with pytest.raises(ValueError, match="Choose exactly one"):
            compare_slot(j, "one", same_grid_asserted=True)
    finally:
        j.close()
