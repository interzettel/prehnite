"""S03-A03: pixel-level true background-spill removal with collision safety.

Tests use mathematically independently constructed composites and do not
claim real-photo matting or imply permission to run any model.
"""
from __future__ import annotations

import json

import pytest
from PIL import Image, ImageDraw

from prehnite.color_spill import ColorSpillRefused, unmix_known_uniform_background
from prehnite.cutout_quality import CutoutContractError, run_cutout_qa

from test_cutout_quality import write_fixture


BG = (20, 180, 130)
FG = (235, 54, 32)


def fixture():
    image = Image.new("RGB", (48, 48), BG)
    hard = Image.new("L", image.size, 0)
    alpha = Image.new("L", image.size, 0)
    ImageDraw.Draw(hard).rectangle((12, 12, 35, 35), fill=255)
    ImageDraw.Draw(image).rectangle((12, 12, 35, 35), fill=FG)
    ImageDraw.Draw(alpha).rectangle((12, 12, 35, 35), fill=255)
    return image, alpha, hard


def blended(foreground, background, alpha):
    return tuple(round((alpha * foreground[c] + (255 - alpha) * background[c]) / 255)
                 for c in range(3))


def error(left, right):
    return sum(abs(left[c] - right[c]) for c in range(3))


@pytest.mark.parametrize("level", [80, 128, 192, 224])
def test_true_unmix_removes_measured_spill_and_keeps_silhouette(level):
    source, alpha, hard = fixture()
    coordinate = (12, 22)
    dirty = blended(FG, BG, level)
    source.putpixel(coordinate, dirty)
    alpha.putpixel(coordinate, level)
    before = source.tobytes()
    original_alpha = alpha.tobytes()
    corrected, metrics = unmix_known_uniform_background(
        source, alpha, hard, background_rgb=BG
    )
    restored = corrected.getpixel(coordinate)
    assert error(restored, FG) <= 4  # bounded 8-bit rounding
    assert error(restored, FG) < error(dirty, FG)
    assert metrics["color_spill_corrected_edge_pixels"] == 1
    assert metrics["color_spill_clipped_edge_pixels"] == 0
    assert metrics["color_spill_alpha_modified_pixels"] == 0
    assert source.tobytes() == before
    assert alpha.tobytes() == original_alpha
    assert hard.getpixel(coordinate) == 255


def test_background_colored_product_regions_are_not_deleted():
    source, alpha, hard = fixture()
    inner = (20, 20)
    boundary = (12, 20)
    # Deliberately product-colored-to-match-background: cannot be safely
    # auto-excised. The actual alpha and both source RGB pixels must survive.
    source.putpixel(inner, BG)
    source.putpixel(boundary, BG)
    alpha.putpixel(boundary, 192)
    corrected, metrics = unmix_known_uniform_background(
        source, alpha, hard, background_rgb=BG
    )
    assert corrected.getpixel(inner) == BG
    assert corrected.getpixel(boundary) == BG
    assert alpha.getpixel(inner) == 255
    assert alpha.getpixel(boundary) == 192
    assert hard.getpixel(inner) == hard.getpixel(boundary) == 255
    assert metrics["color_spill_background_color_collision_preserved_pixels"] == 1
    assert metrics["color_spill_corrected_edge_pixels"] == 0


def test_fully_opaque_subject_rgb_never_changes_even_if_color_matches_backdrop():
    source, alpha, hard = fixture()
    ImageDraw.Draw(source).rectangle((18, 18, 27, 27), fill=BG)
    original = source.tobytes()
    corrected, metrics = unmix_known_uniform_background(
        source, alpha, hard, background_rgb=BG
    )
    assert corrected.tobytes() == original
    assert metrics["color_spill_corrected_edge_pixels"] == 0


@pytest.mark.parametrize(("variant", "reason"), [
    ("wrong_border", "background_not_uniform_or_mismatched"),
    ("cropped_subject", "foreground_touches_frame"),
    ("insufficient_alpha", "unmix_clipping_exceeds_declared_limit"),
    ("invalid_geometry", "rgb_alpha_hard_geometry_mismatch"),
])
def test_refuses_unsafe_background_or_color_math(variant, reason):
    source, alpha, hard = fixture()
    if variant == "wrong_border":
        source.putpixel((0, 0), (255, 0, 0))
    elif variant == "cropped_subject":
        hard.putpixel((0, 3), 255)
    elif variant == "insufficient_alpha":
        source.putpixel((12, 22), (255, 255, 255))
        alpha.putpixel((12, 22), 80)
    elif variant == "invalid_geometry":
        alpha = Image.new("L", (12, 12), 0)
    with pytest.raises(ColorSpillRefused, match=reason):
        unmix_known_uniform_background(source, alpha, hard, background_rgb=BG)


def test_low_alpha_edge_abstains_instead_of_amplifying_noise():
    source, alpha, hard = fixture()
    source.putpixel((12, 22), (126, 126, 126))
    alpha.putpixel((12, 22), 32)
    corrected, metrics = unmix_known_uniform_background(
        source, alpha, hard, background_rgb=BG
    )
    assert corrected.getpixel((12, 22)) == (126, 126, 126)
    assert metrics["color_spill_low_alpha_skipped_pixels"] == 1
    assert metrics["color_spill_corrected_edge_pixels"] == 0


def test_opt_in_qa_recipe_generates_distinct_spill_candidate_without_acceptance(tmp_path):
    source, mask, _, _, recipe, recipe_path = write_fixture(tmp_path)
    recipe["alpha_candidates"][0]["color_spill"] = {
        "background_rgb": [240, 230, 220],
        "border_tolerance": 8,
        "min_alpha": 48,
        "max_clipped_fraction": 0.25,
    }
    recipe_path.write_text(json.dumps(recipe, sort_keys=True), encoding="utf-8")
    report_path = run_cutout_qa(
        recipe_path, source=source, mask=mask, workflow_root=tmp_path,
        models_root=tmp_path, output_dir=tmp_path / "out",
    )
    result = json.loads(report_path.read_text(encoding="utf-8"))
    candidates = {row["id"]: row for row in result["candidates"]}
    assert candidates["candidate-a"]["metrics"]["color_spill_unmix_applied"] is True
    assert candidates["candidate-b"]["metrics"]["color_spill_unmix_applied"] is False
    assert result["visual_acceptance"] == "not_recorded"
    assert result["owner_final_acceptance"] == "not_recorded"
    assert all(row["review_status"] == "review_pending" for row in result["candidates"])
    assert result["stages"]["technical_execution"]["status"] == "unverified"


def test_invalid_operator_background_fails_closed_before_any_candidate_output(tmp_path):
    source, mask, _, _, recipe, recipe_path = write_fixture(tmp_path)
    recipe["alpha_candidates"][0]["color_spill"] = {
        "background_rgb": [0, 0, 0],
    }
    recipe_path.write_text(json.dumps(recipe, sort_keys=True), encoding="utf-8")
    with pytest.raises(CutoutContractError, match="color_spill_refused"):
        run_cutout_qa(
            recipe_path, source=source, mask=mask, workflow_root=tmp_path,
            models_root=tmp_path, output_dir=tmp_path / "out",
        )
    assert not (tmp_path / "out" / "candidate-a.png").exists()
    assert not (tmp_path / "out" / "cutout-quality.json").exists()
