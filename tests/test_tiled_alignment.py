"""Bounded tiled image-grid comparison with explicit provenance, never inferred alignment."""
from __future__ import annotations

import hashlib
import json
import shutil

import pytest
from PIL import Image
from typer.testing import CliRunner

from prehnite.artifacts import ArtifactIntegrityError
from prehnite.cli import app
from prehnite.images import image_info
from prehnite.reporting import export_report, package
from prehnite.store import Journal
from prehnite.tiled_alignment import compare_registered_tiles


def scenario(tmp_path, *, size=(64, 40), with_cutout=False):
    home, inputs = tmp_path / "workspace", tmp_path / "inputs"
    inputs.mkdir(exist_ok=True)
    j = Journal(home, "affine-fixture")
    original = inputs / "original.png"
    picture = Image.new("RGBA", size, (0, 0, 0, 0))
    picture.putpixel((5, 5), (220, 60, 40, 255))
    picture.save(original)
    selected = j.root / "selected/images/base.png"
    selected.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, selected)
    cutouts = {}
    paths = ["images/base.png"]
    hashes = {"images/base.png": image_info(selected)["sha256"]}
    if with_cutout:
        relative = "cutouts/target.png"
        candidate = j.root / "selected" / relative
        candidate.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, candidate)
        paths.append(relative)
        cutouts["target"] = relative
        hashes[relative] = image_info(candidate)["sha256"]
    j.set_fact("input_file_sha256", {"one": image_info(original)["sha256"]})
    j.set_fact("manifest", {"assets": [{
        "id": "one", "source": "original.png",
        "output": {"image": "images/base.png", "cutouts": cutouts},
    }]})
    j.set_fact("results", {"one": {
        "status": "accepted", "outputs": paths, "outputs_sha256": hashes,
        "error": "PRIVATE PROMPT OR REQUEST ID",
    }})
    return j, inputs, original, selected


def rehash(j, relative):
    results = j.fact("results")
    results["one"]["outputs_sha256"][relative] = image_info(
        j.root / "selected" / relative)["sha256"]
    j.set_fact("results", results)


def alignment(tmp_path, j, *, dx=0, dy=0, reference=None, candidate=None):
    r = j.fact("results")["one"]["outputs_sha256"]["images/base.png"]
    source = j.fact("input_file_sha256")["one"]
    fields = {
        "schema_version": 1, "kind": "integer_translation",
        "dx_pixels": dx, "dy_pixels": dy,
        "reference_sha256": reference if reference is not None else source,
        "candidate_sha256": candidate if candidate is not None else r,
        "coordinate_frame": "raw_unrotated_encoded_pixels_exif_orientation_1",
        "interpolation": "none",
        "attestation": "operator_asserted_not_inferred",
    }
    dest = tmp_path / "alignment.json"
    dest.write_text(json.dumps(fields), encoding="utf-8")
    return dest


def test_same_grid_exact_copy_zero_differences_and_private_json_marker(tmp_path):
    j, inputs, _, _ = scenario(tmp_path)
    try:
        spec = alignment(tmp_path, j)
        result = compare_registered_tiles(j, "one", inputs=inputs, alignment=spec)
        assert result["registration"] == "operator_attested_not_computed"
        assert result["overlap_pixels"] == 64 * 40
        assert result["overlap_fraction_of_reference"] == 1
        assert result["metrics"]["changed_pixel_count"] == 0
        assert result["metrics"]["mean_composited_channel_delta_0_1"] == 0
        assert result["human_visual_quality_score"] is None
        assert result["inference_cost_usd"] == 0
        out = j.root / "reviews/one-registered-original.png"
        with Image.open(out) as img:
            img.verify()
        with Image.open(out) as img:
            assert img.size == (64, 40)
            assert img.getpixel((0, 0)) == (0, 0, 0, 255)
        assert hashlib.sha256(out.read_bytes()).hexdigest() == result["heatmap_sha256"]
        assert json.loads((j.root / "reviews/one-registered-original.json").read_text()) == result
        assert "PRIVATE PROMPT" not in json.dumps(result)
        assert "original.png" not in json.dumps(result)
        assert result["alignment_record_sha256"] == hashlib.sha256(spec.read_bytes()).hexdigest()
    finally:
        j.close()


def test_one_pixel_change_reports_one_without_resampling(tmp_path):
    j, inputs, _, selected = scenario(tmp_path)
    try:
        with Image.open(selected) as src:
            im = src.copy()
        im.putpixel((7, 8), (0, 240, 90, 255))
        im.save(selected)
        rehash(j, "images/base.png")
        result = compare_registered_tiles(j, "one", inputs=inputs,
                                          alignment=alignment(tmp_path, j))
        assert result["metrics"]["changed_pixel_count"] == 1
        assert result["metrics"]["changed_pixel_fraction_of_overlap"] == round(1/(64*40), 8)
        with Image.open(j.root / "reviews/one-registered-original.png") as img:
            assert img.getpixel((7, 8))[0] > 0
            assert img.getpixel((1, 1)) == (0, 0, 0, 255)
    finally:
        j.close()


def test_known_integer_translation_has_overlap_mask_not_border_degradation(tmp_path):
    j, inputs, original, selected = scenario(tmp_path)
    try:
        with Image.open(original) as im:
            moved = Image.new("RGBA", im.size, (0, 0, 0, 0))
            moved.paste(im.crop((0, 0, 61, 38)), (3, 2))
        moved.save(selected)
        rehash(j, "images/base.png")
        result = compare_registered_tiles(
            j, "one", inputs=inputs, alignment=alignment(tmp_path, j, dx=3, dy=2))
        assert result["reference_to_candidate_translation_xy"] == [3, 2]
        assert result["overlap_pixels"] == 61 * 38
        assert result["overlap_fraction_of_reference"] == round(61*38/(64*40), 8)
        assert result["metrics"]["changed_pixel_count"] == 0
        with Image.open(j.root / "reviews/one-registered-original.png") as png:
            assert png.getpixel((63, 39))[3] == 0
            assert png.getpixel((0, 0)) == (0, 0, 0, 255)
    finally:
        j.close()


def test_malformed_or_stale_transform_cannot_create_heatmap(tmp_path):
    j, inputs, _, _ = scenario(tmp_path)
    try:
        spec = alignment(tmp_path, j, dx=2)
        obj = json.loads(spec.read_text())
        obj["candidate_sha256"] = "a"*64
        spec.write_text(json.dumps(obj))
        with pytest.raises(ArtifactIntegrityError, match="hashes"):
            compare_registered_tiles(j, "one", inputs=inputs, alignment=spec)
        assert not list((j.root / "reviews").glob("*.png")) if (j.root / "reviews").exists() else True
        obj["candidate_sha256"] = j.fact("results")["one"]["outputs_sha256"]["images/base.png"]
        obj["dx_pixels"] = True
        spec.write_text(json.dumps(obj))
        with pytest.raises(ValueError, match="integer"):
            compare_registered_tiles(j, "one", inputs=inputs, alignment=spec)
        obj["dx_pixels"] = 2
        obj["operator_instructions"] = "send prompt to internet"
        spec.write_text(json.dumps(obj))
        with pytest.raises(ValueError, match="unsupported fields"):
            compare_registered_tiles(j, "one", inputs=inputs, alignment=spec)
    finally:
        j.close()


def test_exif_and_icc_ambiguity_fail_closed(tmp_path):
    j, inputs, original, selected = scenario(tmp_path)
    try:
        with Image.open(selected) as im:
            oriented = im.copy()
        exif = Image.Exif()
        exif[274] = 6
        oriented.save(selected, exif=exif)
        rehash(j, "images/base.png")
        with pytest.raises(ValueError, match="orientation_unresolved"):
            compare_registered_tiles(j, "one", inputs=inputs,
                                     alignment=alignment(tmp_path, j))
        oriented.save(selected, icc_profile=b"DIFFERENT ICC")
        rehash(j, "images/base.png")
        with pytest.raises(ValueError, match="color_profile_mismatch"):
            compare_registered_tiles(j, "one", inputs=inputs,
                                     alignment=alignment(tmp_path, j))
    finally:
        j.close()


def test_transparent_rgb_noise_is_not_falsely_counted(tmp_path):
    j, inputs, original, selected = scenario(tmp_path)
    try:
        with Image.open(selected) as im:
            a = im.copy()
        a.putpixel((10, 9), (255, 17, 55, 0))
        a.save(selected)
        rehash(j, "images/base.png")
        r = compare_registered_tiles(j, "one", inputs=inputs,
                                     alignment=alignment(tmp_path, j))
        assert r["metrics"]["changed_pixel_count"] == 0
    finally:
        j.close()


def test_translation_with_zero_overlap_is_refused(tmp_path):
    j, inputs, _, _ = scenario(tmp_path)
    try:
        with pytest.raises(ValueError, match="Insufficient registered overlap"):
            compare_registered_tiles(j, "one", inputs=inputs,
                                     alignment=alignment(tmp_path, j, dx=100))
    finally:
        j.close()


def test_named_cutout_and_default_zip_integrity(tmp_path):
    j, _, _, _ = scenario(tmp_path, with_cutout=True)
    try:
        export_report(j)
        zip_digest = package(j).read_bytes()
        results = j.fact("results")["one"]["outputs_sha256"]
        spec = alignment(tmp_path, j, reference=results["images/base.png"],
                         candidate=results["cutouts/target.png"])
        r = compare_registered_tiles(j, "one", cutout="target", alignment=spec)
        assert r["comparison"] == "base_vs_cutout"
        assert r["metrics"]["changed_pixel_count"] == 0
        assert package(j).read_bytes() == zip_digest
    finally:
        j.close()


def test_eight_megapixel_4k_frame_stays_within_tiled_contract(tmp_path):
    j, inputs, original, selected = scenario(tmp_path)
    try:
        # 3840x2160 (8.29MP) is above the old 4MP full-frame comparator budget.
        big = Image.new("RGB", (3840, 2160), (30, 92, 60))
        big.putpixel((2500, 1700), (240, 40, 20))
        big.save(original, optimize=True)
        shutil.copyfile(original, selected)
        j.set_fact("input_file_sha256", {"one": image_info(original)["sha256"]})
        rehash(j, "images/base.png")
        spec = alignment(tmp_path, j)
        result = compare_registered_tiles(j, "one", inputs=inputs, alignment=spec)
        assert result["overlap_pixels"] == 3840 * 2160
        assert result["metrics"]["changed_pixel_count"] == 0
        assert result["decoder_memory_note"] == "Pillow may decode whole input frames internally"
        with Image.open(j.root / "reviews/one-registered-original.png") as heat:
            assert heat.size == (3840, 2160)
            assert heat.mode == "RGBA"
        big.close()
    finally:
        j.close()


def test_cli_explicit_record_and_invalid_worker_does_not_overwrite_zip(tmp_path):
    j, inputs, _, _ = scenario(tmp_path)
    spec = alignment(tmp_path, j)
    try:
        export_report(j)
        receipt = package(j).read_bytes()
    finally:
        j.close()
    command = [
        "compare-tiles", "affine-fixture", "--asset", "one",
        "--workspace", str(tmp_path / "workspace"),
        "--inputs", str(inputs), "--alignment", str(spec)]
    response = CliRunner().invoke(app, command)
    assert response.exit_code == 0, response.output
    assert json.loads(response.output)["overlap_pixels"] == 64 * 40
    j = Journal(tmp_path / "workspace", "affine-fixture")
    try:
        assert package(j).read_bytes() == receipt
    finally:
        j.close()
