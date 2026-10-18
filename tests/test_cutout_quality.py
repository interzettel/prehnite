"""Offline cutout contracts: configurable candidates, QA and explicit acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from typer.testing import CliRunner

from prehnite.cli import app
from prehnite.cutout_quality import (
    CutoutContractError,
    create_acceptance_record,
    load_recipe,
    run_cutout_qa,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_source(tmp_path: Path, *, disconnected: bool = False) -> Path:
    path = tmp_path / "source.png"
    image = Image.new("RGB", (128, 160), (240, 230, 220))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 108, 72), fill=(220, 190, 130))
    draw.rectangle((62, 72, 78, 130), fill=(120, 95, 70))
    draw.ellipse((25, 128, 112, 155), fill=(110, 85, 62))
    if disconnected:
        draw.rectangle((2, 2, 8, 8), fill=(20, 20, 20))
    image.save(path)
    return path


def write_mask(tmp_path: Path, mode: str = "normal") -> Path:
    path = tmp_path / "mask.png"
    mask = Image.new("L", (128, 160), 0)
    draw = ImageDraw.Draw(mask)
    if mode == "empty":
        pass
    elif mode == "full":
        draw.rectangle((0, 0, 127, 159), fill=255)
    elif mode == "inverted":
        draw.rectangle((0, 0, 127, 159), fill=255)
        draw.ellipse((20, 20, 108, 150), fill=0)
    elif mode == "multiple":
        draw.rectangle((20, 20, 108, 72), fill=255)
        draw.rectangle((2, 2, 8, 8), fill=255)
    else:
        draw.rectangle((20, 20, 108, 72), fill=255)
        draw.rectangle((62, 72, 78, 130), fill=255)
        draw.ellipse((25, 128, 112, 155), fill=255)
        # Deliberate one-pixel fringe band: candidate QA must not introduce
        # background RGB when alpha is softened.
        draw.rectangle((19, 19, 109, 73), fill=255)
        draw.rectangle((61, 72, 79, 131), fill=255)
    mask.save(path)
    return path


def write_fixture(tmp_path: Path, *, mask_mode: str = "normal",
                  disconnected_source: bool = False):
    source = write_source(tmp_path, disconnected=disconnected_source)
    mask = write_mask(tmp_path, mask_mode)
    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps({
        "1": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
        "4": {"class_type": "Segment", "inputs": {"image": ["1", 0], "prompt": "widget"}},
        "6": {"class_type": "SaveImage", "inputs": {"images": ["4", 0]}},
    }), encoding="utf-8")
    model = tmp_path / "model.pth"
    model.write_bytes(b"synthetic-model-bytes-for-test-only")
    recipe = {
        "schema_version": 1,
        "source": {"name": "source.png", "sha256": digest(source)},
        "target": {"id": "widget", "phrase": "a single widget",
                   "include": ["widget body"], "exclude": ["background"]},
        "workflow": {"path": "workflow.json", "sha256": digest(workflow),
                      "input_node": "1", "target_node": "4",
                      "target_input": "prompt", "output_node": "6"},
        "models": [{"role": "detector", "path": "model.pth",
                    "sha256": digest(model)}],
        "alpha_candidates": [
            {"id": "candidate-a", "sigma_px": 0.65, "preserve_core_px": 1},
            {"id": "candidate-b", "sigma_px": 1.0, "preserve_core_px": 1},
        ],
        "qa": {"max_partial_alpha_fraction": 0.10},
    }
    recipe_path = tmp_path / "cutout.json"
    recipe_path.write_text(json.dumps(recipe, sort_keys=True), encoding="utf-8")
    return source, mask, workflow, model, recipe, recipe_path


def test_two_candidates_are_qaed_without_automatic_acceptance(tmp_path):
    source, mask, _, _, _, recipe_path = write_fixture(tmp_path)
    out = tmp_path / "out"
    report_path = run_cutout_qa(recipe_path, source=source, mask=mask,
                                workflow_root=tmp_path, models_root=tmp_path,
                                output_dir=out)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(report["stages"]) == {
        "resource_readiness", "dependency_compatibility", "technical_execution",
        "segmentation_validity", "alpha_quality", "visual_acceptance",
        "owner_final_acceptance",
    }
    assert report["visual_acceptance"] == "not_recorded"
    assert report["owner_final_acceptance"] == "not_recorded"
    assert len(report["candidates"]) == 2
    assert {row["status"] for row in report["candidates"]} == {"passed"}
    assert report["recommended_candidate"] in {"candidate-a", "candidate-b"}
    assert report["stages"]["alpha_quality"]["status"] == "passed"
    for row in report["candidates"]:
        assert row["review_status"] == "review_pending"
        with Image.open(row["path"]) as candidate:
            assert candidate.mode == "RGBA"
            assert candidate.getchannel("A").getextrema() == (0, 255)
        assert digest(Path(row["path"])) == row["sha256"]
    assert load_recipe(recipe_path).alpha_candidates[0].sigma_px == 0.65


def test_candidate_hard_geometry_and_transparent_rgb_are_conservative(tmp_path):
    source, mask, _, _, _, recipe_path = write_fixture(tmp_path)
    out = tmp_path / "out"
    report_path = run_cutout_qa(recipe_path, source=source, mask=mask,
                                workflow_root=tmp_path, models_root=tmp_path,
                                output_dir=out)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    with Image.open(mask) as original:
        original_hard = original.convert("L").point(lambda x: 255 if x > 127 else 0)
    for row in report["candidates"]:
        with Image.open(row["path"]) as candidate:
            hard = candidate.getchannel("A").point(lambda x: 255 if x > 127 else 0)
            assert hard.size == original_hard.size
            if row["id"] == "candidate-a":
                assert hard.tobytes() == original_hard.tobytes()
            else:
                assert row["metrics"]["hard_iou"] >= 0.999
                assert row["metrics"]["max_narrow_width_delta_px"] <= 1
            assert candidate.getpixel((0, 0))[3] == 0
            assert candidate.getpixel((0, 0))[:3] != (240, 230, 220)
        assert row["metrics"]["components"] == 1
        assert row["metrics"]["holes"] == 0
        assert row["metrics"]["transparent_rgb_decontaminated"] is True
        assert row["metrics"]["partial_alpha_pixels"] > 0


@pytest.mark.parametrize("mode", ["empty", "full", "inverted", "multiple"])
def test_invalid_masks_produce_failed_or_review_stages(tmp_path, mode):
    source, mask, _, _, _, recipe_path = write_fixture(tmp_path, mask_mode=mode)
    out = tmp_path / "out"
    report_path = run_cutout_qa(recipe_path, source=source, mask=mask,
                                workflow_root=tmp_path, models_root=tmp_path,
                                output_dir=out)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["stages"]["segmentation_validity"]["status"] in {"failed", "needs_review"}
    assert report["stages"]["alpha_quality"]["status"] in {"failed", "blocked"}
    assert report["recommended_candidate"] is None
    assert report["visual_acceptance"] == "not_recorded"


@pytest.mark.parametrize("mutated", ["source", "model", "workflow"])
def test_altered_binding_bytes_are_refused_before_qa(tmp_path, mutated):
    source, mask, workflow, model, _, recipe_path = write_fixture(tmp_path)
    if mutated == "source":
        source.write_bytes(b"changed")
    elif mutated == "model":
        model.write_bytes(b"changed")
    else:
        workflow.write_text("{}", encoding="utf-8")
    with pytest.raises(CutoutContractError):
        run_cutout_qa(recipe_path, source=source, mask=mask,
                      workflow_root=tmp_path, models_root=tmp_path,
                      output_dir=tmp_path / "out")
    assert not (tmp_path / "out" / "cutout-quality.json").exists()


def test_acceptance_is_explicit_create_only_and_separates_owner_state(tmp_path):
    source, mask, _, _, _, recipe_path = write_fixture(tmp_path)
    out = tmp_path / "out"
    report_path = run_cutout_qa(recipe_path, source=source, mask=mask,
                                workflow_root=tmp_path, models_root=tmp_path,
                                output_dir=out)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    candidate_id = report["recommended_candidate"]
    record_path = tmp_path / "acceptance.json"
    record = create_acceptance_record(
        quality_report=report_path, candidate_id=candidate_id,
        reviewer="independent reviewer", decision="accepted",
        scope="This specific synthetic candidate at the supplied comparison scale.",
        evidence=[source, mask], output=record_path,
    )
    assert record["decision"] == "accepted"
    assert record["candidate_sha256"] == next(
        row["sha256"] for row in report["candidates"] if row["id"] == candidate_id)
    assert record["stages"]["visual_acceptance"]["status"] == "passed"
    assert record["stages"]["owner_final_acceptance"]["status"] == "not_recorded"
    with pytest.raises(FileExistsError):
        create_acceptance_record(
            quality_report=report_path, candidate_id=candidate_id,
            reviewer="independent reviewer", decision="accepted",
            scope="duplicate must not overwrite", evidence=[source],
            output=record_path,
        )



def test_cli_writes_report_and_keeps_visual_acceptance_unrecorded(tmp_path):
    source, mask, _, _, _, recipe_path = write_fixture(tmp_path)
    result = CliRunner().invoke(app, [
        "cutout-qa",
        "--recipe", str(recipe_path),
        "--source", str(source),
        "--mask", str(mask),
        "--workflow-root", str(tmp_path),
        "--models-root", str(tmp_path),
        "--output", str(tmp_path / "cli-out"),
    ])
    assert result.exit_code == 0, result.output
    report = json.loads((tmp_path / "cli-out" / "cutout-quality.json").read_text())
    assert report["visual_acceptance"] == "not_recorded"
    assert report["owner_final_acceptance"] == "not_recorded"
    assert "recommended_candidate" in result.output


def test_rejected_technical_candidate_cannot_be_accepted(tmp_path):
    source, mask, _, _, recipe, recipe_path = write_fixture(tmp_path)
    # Make the tolerance impossible so candidates are technically rejected;
    # QA still completes and writes evidence, but acceptance must refuse.
    recipe["qa"]["max_partial_alpha_fraction"] = 0.0001
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    report_path = run_cutout_qa(recipe_path, source=source, mask=mask,
                                workflow_root=tmp_path, models_root=tmp_path,
                                output_dir=tmp_path / "out")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["recommended_candidate"] is None
    with pytest.raises(CutoutContractError):
        create_acceptance_record(
            quality_report=report_path, candidate_id="candidate-a",
            reviewer="independent reviewer", decision="accepted",
            scope="must fail", evidence=[], output=tmp_path / "approval.json",
        )
