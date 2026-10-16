"""Ground-truth / refusal regressions for synthetic difficult cutout matrix."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from prehnite.repair import RepairRefused, diagnose, run_product_repair
from prehnite.store import Journal


def _suite():
    script = Path(__file__).resolve().parents[1] / "scripts" / "repair_challenge_benchmark.py"
    spec = importlib.util.spec_from_file_location("repair_challenge_benchmark", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_all_challenge_cases_are_unique_and_split_across_cohorts():
    module = _suite()
    cases = module.CASES
    assert len(cases) >= 16
    assert len(set(c.slug for c in cases)) == len(cases)
    assert any(c.cohort == "portrait" for c in cases)
    assert any(c.material == "glass" for c in cases)
    assert any(c.category.startswith("Product") for c in cases)
    assert all(c.expectation in ("technically_accepted", "human_review") for c in cases)


def test_challenge_full_matrix_references_and_replay_are_deterministic(tmp_path):
    module = _suite()
    first = module.run(tmp_path)
    assert first["cases"] == len(module.CASES)
    assert first["accepted"] >= 3
    assert first["review"] >= 12
    report = json.loads(Path(first["report_json"]).read_text())
    assert report["provider_requests"] == 0
    assert report["additional_paid_usd"] == 0
    assert report["benchmark_reference_used_by_repair"] is False
    assert report["production_quality_established"] is False
    assert all(row["expected"] == row["actual"] for row in report["cases"])
    assert all(row["output_sha256"] is None for row in report["cases"]
               if row["actual"] == "human_review")
    for row in report["cases"]:
        assert len(row["source_sha256"]) == 64
        assert len(row["reference_sha256"]) == 64
        if row["actual"] == "technically_accepted":
            assert row["after"]["iou"] > row["before"]["iou"]
            assert row["after"]["alpha_mae"] < row["before"]["alpha_mae"]
            assert row["after"]["edge_mae"] < row["before"]["edge_mae"]
            assert row["logical_attempt_count"] == 1
    assert "data:image/png;base64," in Path(first["report_html"]).read_text()
    second = module.run(tmp_path)
    assert first["cases"] == second["cases"]
    replay = json.loads(Path(second["report_json"]).read_text())
    for earlier, current in zip(report["cases"], replay["cases"]):
        assert earlier["actual"] == current["actual"]
        assert earlier["source_sha256"] == current["source_sha256"]
        assert earlier["defective_sha256"] == current["defective_sha256"]
        assert earlier["output_sha256"] == current["output_sha256"]
        assert earlier["logical_attempt_count"] == current["logical_attempt_count"]


def test_reference_never_alters_runtime_decision(tmp_path):
    module = _suite()
    case = next(c for c in module.CASES if c.slug == "opaque-flat")
    fixture = module.create_fixture(tmp_path, case)
    with Image.open(fixture["reference"]) as image:
        bogus = Image.new("L", image.size, 0)
    # Intentionally poison withheld truth after inputs are created.
    bogus.save(fixture["reference"])
    journal = Journal(tmp_path, "challenge-poisoned-truth")
    try:
        result = run_product_repair(journal, fixture["source"], fixture["defective"],
                                    asset_id="one", target_id="one", material="opaque")
    finally:
        journal.close()
    assert result["status"] == "technically_accepted"


@pytest.mark.parametrize("slug,reason", [
    ("smooth-gradient", "background_not_uniform"),
    ("checkerboard", "background_not_uniform"),
    ("cast-shadow", "background_not_uniform"),
    ("two-products", "multiple_mask_islands_require_selection"),
    ("frame-crop", "subject_touches_frame"),
    ("color-collision", "interior_background_collision_or_hole"),
    ("interior-mask-hole", "interior_transparency_requires_review"),
    ("furniture-hole", "interior_transparency_requires_review"),
    ("thick-halo", "interior_background_collision_or_hole"),
    ("clean-mask", "no_verifiable_background_fringe"),
    ("glass", "material_not_qualified_for_opaque_repair"),
    ("sheer-fabric", "material_not_qualified_for_opaque_repair"),
    ("portrait-hair", "portrait_or_other_cohort_unsupported"),
])
def test_negative_challenge_has_specific_fail_closed_reason(tmp_path, slug, reason):
    module = _suite()
    case = next(c for c in module.CASES if c.slug == slug)
    files = module.create_fixture(tmp_path, case)
    journal = Journal(tmp_path, "case-" + slug)
    try:
        result = run_product_repair(
            journal, files["source"], files["defective"],
            asset_id="asset", target_id="part",
            cohort=case.cohort, material=case.material)
    finally:
        journal.close()
    assert result["status"] == "human_review"
    assert result["reason"] == reason
    assert result["would_spend_usd"] == 0
