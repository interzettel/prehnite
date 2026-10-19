"""S03-A04: synthetic oracle matte retention and honest underlay diagnostics."""
from __future__ import annotations

import hashlib
import json

import pytest
from PIL import Image, ImageDraw

from prehnite.cutout_quality import CutoutContractError, _alpha_metrics, run_cutout_qa
from prehnite.matte_evidence import MatteEvidenceRefused, evaluate_reference_matte
from test_cutout_quality import write_fixture


def oracle_fixture(tmp_path):
    source, mask, _workflow, _model, recipe, recipe_path = write_fixture(tmp_path)
    size = (128, 160)
    foreground = Image.new("RGB", size, (224, 68, 42))
    # Use an independently defined *soft* oracle alpha, never a blurred SAM
    # silhouette. Connected mesh with open holes, hair-like 1px strands, glass-
    # like partially transmissive region (not an optical refraction simulator).
    alpha = Image.new("L", size, 0)
    draw = ImageDraw.Draw(alpha)
    draw.rectangle((19, 35, 85, 114), fill=255)
    draw.rectangle((40, 28, 62, 35), fill=170)
    draw.line((60, 28, 98, 28), fill=96, width=1)
    draw.line((62, 29, 109, 32), fill=110, width=1)
    draw.rectangle((86, 50, 117, 100), fill=144)
    draw.rectangle((24, 45, 51, 91), fill=162)
    for x in (28, 36, 44):
        for y in (51, 63, 75):
            draw.rectangle((x, y, x + 3, y + 3), fill=0)
    # Reference foreground color is supplied in *straight* RGB and explicitly
    # not a photograph already composited over a backdrop.
    foreground.save(source)
    alpha.save(mask)
    recipe["source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    recipe["alpha_candidates"] = [{
        "id": "oracle-preserve",
        "sigma_px": 0.65,
        "transition_mode": "preserve_trusted_soft",
        "soft_alpha_sha256": hashlib.sha256(mask.read_bytes()).hexdigest(),
        "foreground_rgb_origin": "straight_foreground_rgb",
    }]
    recipe["qa"]["max_partial_alpha_fraction"] = 0.50
    recipe_path.write_text(json.dumps(recipe, sort_keys=True), encoding="utf-8")
    return source, mask, recipe, recipe_path, foreground, alpha


def test_soft_alpha_coverage_uses_correct_reference(tmp_path):
    _, _, _, _, _, original_alpha = oracle_fixture(tmp_path)
    # Legacy binary-feather QA deliberately compares against a hard silhouette.
    legacy = _alpha_metrics(original_alpha, original_alpha)
    assert legacy["coverage_delta"] > 0.05
    # Trusted soft-alpha preservation has its own explicit reference mode and
    # measures identical supplied alpha against itself, including transmission.
    trusted = _alpha_metrics(original_alpha, original_alpha, trusted_soft_alpha=True)
    assert trusted["coverage_delta"] == 0.0
    assert trusted["hard_iou"] == legacy["hard_iou"] == 1.0
    assert trusted["hole_components"] == legacy["hole_components"]


def test_preserves_hair_mesh_glass_like_fractional_alpha_and_measured_zero_halo(tmp_path):
    source, mask, _, recipe_path, foreground, alpha = oracle_fixture(tmp_path)
    report_path = run_cutout_qa(
        recipe_path, source=source, mask=mask, workflow_root=tmp_path,
        models_root=tmp_path, output_dir=tmp_path / "out",
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(report["candidates"]) == 1
    row = report["candidates"][0]
    assert row["status"] == "passed", {"reasons": row["rejection_reasons"], "metrics": row["metrics"]}
    assert row["review_status"] == "review_pending"
    assert report["visual_acceptance"] == "not_recorded"
    assert report["owner_final_acceptance"] == "not_recorded"
    assert row["metrics"]["soft_alpha_preserved"] is True
    assert row["metrics"]["straight_foreground_rgb_verified"] is False
    with Image.open(row["path"]) as actual:
        assert actual.mode == "RGBA"
        assert actual.getchannel("A").tobytes() == alpha.tobytes()
        oracle = foreground.convert("RGBA")
        oracle.putalpha(alpha)
        metrics = evaluate_reference_matte(actual, oracle)
    assert metrics["alpha_mae_255"] == 0
    assert metrics["oracle_fractional_alpha_mae_255"] == 0
    assert metrics["max_composited_transition_rgb_mae_255"] == 0
    assert metrics["oracle_fractional_pixels"] > 0


def test_oracle_detects_hair_loss_and_color_fringe_without_conflating_errors(tmp_path):
    *_, foreground, alpha = oracle_fixture(tmp_path)
    reference = foreground.convert("RGBA")
    reference.putalpha(alpha)
    lost_hair = reference.copy()
    lost_hair.putpixel((90, 28), (224, 68, 42, 0))
    hair_metrics = evaluate_reference_matte(lost_hair, reference)
    assert hair_metrics["oracle_fractional_alpha_mae_255"] > 0
    assert hair_metrics["max_composited_transition_rgb_mae_255"] > 0

    contaminated = reference.copy()
    contaminated.putpixel((86, 60), (32, 210, 182, 144))
    spill_metrics = evaluate_reference_matte(contaminated, reference)
    assert spill_metrics["alpha_mae_255"] == 0
    assert spill_metrics["max_composited_transition_rgb_mae_255"] > 0


@pytest.mark.parametrize("bad", ["unbound", "wrong_hash", "wrong_origin", "spill"])
def test_opt_in_soft_matte_fail_closed_before_publishing(tmp_path, bad):
    source, mask, recipe, recipe_path, _, _ = oracle_fixture(tmp_path)
    spec = recipe["alpha_candidates"][0]
    if bad == "unbound":
        del spec["soft_alpha_sha256"]
    elif bad == "wrong_hash":
        spec["soft_alpha_sha256"] = "0" * 64
    elif bad == "wrong_origin":
        del spec["foreground_rgb_origin"]
    else:
        spec["color_spill"] = {"background_rgb": [0, 0, 0]}
    recipe_path.write_text(json.dumps(recipe, sort_keys=True), encoding="utf-8")
    with pytest.raises((ValueError, CutoutContractError)):
        run_cutout_qa(
            recipe_path, source=source, mask=mask, workflow_root=tmp_path,
            models_root=tmp_path, output_dir=tmp_path / "out",
        )
    assert not (tmp_path / "out" / "oracle-preserve.png").exists()


@pytest.mark.parametrize("mutation", ["rgb_mask", "wrong_resolution"])
def test_soft_alpha_refuses_colorized_mask_or_wrong_resolution(tmp_path, mutation):
    source, mask, _, recipe_path, _, _ = oracle_fixture(tmp_path)
    # Close the read handle before rewriting: Windows does not permit replacing
    # an open image file, and cross-platform correctness matters here.
    with Image.open(mask) as original:
        changed = original.copy()
    if mutation == "rgb_mask":
        changed = changed.convert("RGB")
    else:
        changed = changed.resize((64, 80))
    changed.save(mask)
    with pytest.raises(CutoutContractError, match="soft_alpha_must_be_exact_L_PNG"):
        run_cutout_qa(recipe_path, source=source, mask=mask, workflow_root=tmp_path,
                      models_root=tmp_path, output_dir=tmp_path / "out")
    assert not (tmp_path / "out" / "oracle-preserve.png").exists()


def test_reference_flags_premultiplied_rgb_misdeclared_as_straight(tmp_path):
    *_, foreground, alpha = oracle_fixture(tmp_path)
    reference = foreground.convert("RGBA")
    reference.putalpha(alpha)
    incorrect = reference.copy()
    x, y = 92, 60  # partially transmissive glass-like panel
    r, g, b, a = incorrect.getpixel((x, y))
    incorrect.putpixel((x, y), (r * a // 255, g * a // 255, b * a // 255, a))
    # Alpha can match exactly while RGB premultiplication causes a dark fringe.
    measured = evaluate_reference_matte(incorrect, reference)
    assert measured["alpha_mae_255"] == 0
    assert measured["max_composited_transition_rgb_mae_255"] > 0


def test_oracle_refuses_non_reference_or_non_partial_inputs():
    image = Image.new("RGBA", (24, 24), (20, 40, 60, 255))
    with pytest.raises(MatteEvidenceRefused, match="reference_has_no_fractional_alpha"):
        evaluate_reference_matte(image, image)
    with pytest.raises(MatteEvidenceRefused, match="straight_rgba_inputs_required"):
        evaluate_reference_matte(image.convert("RGB"), image)
    with pytest.raises(MatteEvidenceRefused, match="reference_geometry_mismatch"):
        evaluate_reference_matte(image, Image.new("RGBA", (23, 24), (0, 0, 0, 128)))
