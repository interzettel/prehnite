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
    _count_components_and_holes,
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
    assert report["file_integrity"]["status"] == "passed"
    assert report["file_integrity"]["model_sha256"] == {
        "detector": digest(report_path.parent.parent / "model.pth")}
    assert report["stages"]["dependency_compatibility"]["status"] == "unverified"
    assert report["stages"]["technical_execution"]["status"] == "unverified"
    assert report["resource_observation"] is None
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
        assert row["metrics"]["hole_components"] == 0
        assert row["metrics"]["foreground_rgb_expansion_applied"] is True
        assert row["metrics"]["transparent_rgb_replaced_pixels"] > 0
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
    with pytest.raises(CutoutContractError, match="evidence"):
        create_acceptance_record(
            quality_report=report_path, candidate_id=candidate_id,
            reviewer="independent reviewer", decision="accepted",
            scope="must include evidence", evidence=[],
            output=tmp_path / "missing-evidence.json",
        )



def test_topology_counts_hole_components_and_all_border_seeds():
    one = Image.new("L", (64, 64), 0)
    draw = ImageDraw.Draw(one)
    draw.rectangle((0, 0, 63, 63), fill=255)
    draw.rectangle((20, 20, 29, 29), fill=0)  # 100-pixel hole
    two = Image.new("L", (64, 64), 0)
    draw = ImageDraw.Draw(two)
    draw.rectangle((0, 0, 63, 63), fill=255)
    draw.rectangle((20, 20, 24, 29), fill=0)  # 50 pixels
    draw.rectangle((35, 20, 39, 29), fill=0)  # 50 pixels
    assert _count_components_and_holes(one) == (1, 1, 100)
    assert _count_components_and_holes(two) == (1, 2, 100)

    corner = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(corner).rectangle((0, 0, 20, 20), fill=255)
    assert _count_components_and_holes(corner) == (1, 0, 0)


def write_resource_observation(tmp_path: Path, status: str,
                               *, startup_authorized: bool = False) -> Path:
    path = tmp_path / f"resource-{status}.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "kind": "resource_readiness_observation",
        "status": status,
        "startup_authorized": startup_authorized,
        "model_compatibility": "not_assessed",
        "technical_execution": "not_started",
        "visual_acceptance": "not_assessed",
    }), encoding="utf-8")
    return path


@pytest.mark.parametrize(("status", "expected"), [
    ("pass", "passed"), ("blocked", "blocked"), ("unknown", "unverified"),
])
def test_pr159_observation_is_adapted_without_authorizing_execution(
        tmp_path, status, expected):
    source, mask, _, _, _, recipe_path = write_fixture(tmp_path)
    resource = write_resource_observation(tmp_path, status)
    out = tmp_path / f"out-{status}"
    report_path = run_cutout_qa(
        recipe_path, source=source, mask=mask, workflow_root=tmp_path,
        models_root=tmp_path, output_dir=out, resource_readiness=resource)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["stages"]["resource_readiness"]["status"] == expected
    assert report["resource_observation"]["observation_status"] == status
    assert report["resource_observation"]["startup_authorized"] is False
    assert report["stages"]["technical_execution"]["status"] == "unverified"


def test_missing_resource_observation_fails_closed(tmp_path):
    source, mask, _, _, _, recipe_path = write_fixture(tmp_path)
    with pytest.raises(CutoutContractError, match="regular file"):
        run_cutout_qa(recipe_path, source=source, mask=mask,
                      workflow_root=tmp_path, models_root=tmp_path,
                      output_dir=tmp_path / "out",
                      resource_readiness=tmp_path / "does-not-exist.json")


def test_resource_observation_that_authorizes_startup_is_refused(tmp_path):
    source, mask, _, _, _, recipe_path = write_fixture(tmp_path)
    resource = write_resource_observation(tmp_path, "pass", startup_authorized=True)
    with pytest.raises(CutoutContractError, match="authorize"):
        run_cutout_qa(recipe_path, source=source, mask=mask,
                      workflow_root=tmp_path, models_root=tmp_path,
                      output_dir=tmp_path / "out", resource_readiness=resource)


def test_qa_refuses_to_overwrite_an_existing_report(tmp_path):
    source, mask, _, _, _, recipe_path = write_fixture(tmp_path)
    out = tmp_path / "out"
    report_path = run_cutout_qa(recipe_path, source=source, mask=mask,
                                workflow_root=tmp_path, models_root=tmp_path,
                                output_dir=out)
    before = report_path.read_bytes()
    with pytest.raises(CutoutContractError, match="new or empty"):
        run_cutout_qa(recipe_path, source=source, mask=mask,
                      workflow_root=tmp_path, models_root=tmp_path, output_dir=out)
    assert report_path.read_bytes() == before


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


def test_documented_run_invocation_parses_without_invalid_manifest_flag(tmp_path):
    manifest = tmp_path / "manifest.yaml"
    profile = tmp_path / "profile.yaml"
    manifest.write_text("id: nope\n", encoding="utf-8")
    profile.write_text("{}\n", encoding="utf-8")
    result = CliRunner().invoke(app, [
        "run", str(manifest), "--profile", str(profile),
        "--workspace", str(tmp_path / "workspace"),
        "--inputs", str(tmp_path / "inputs"),
    ])
    # The files are invalid YAML, so the command may fail after parsing; the
    # important regression is that the documented positional form is accepted
    # and that --manifest is not accepted.
    assert "No such option: --manifest" not in result.output
    bad = CliRunner().invoke(app, [
        "run", "--manifest", str(manifest), "--profile", str(profile),
    ])
    assert "No such option: --manifest" in bad.output


def test_cli_exit_code_distinguishes_failed_qa(tmp_path):
    source, mask, _, _, _, recipe_path = write_fixture(tmp_path, mask_mode="empty")
    result = CliRunner().invoke(app, [
        "cutout-qa", "--recipe", str(recipe_path), "--source", str(source),
        "--mask", str(mask), "--workflow-root", str(tmp_path),
        "--models-root", str(tmp_path), "--output", str(tmp_path / "failed-out"),
    ])
    assert result.exit_code == 2
    assert (tmp_path / "failed-out" / "cutout-quality.json").is_file()


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
