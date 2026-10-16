"""Operator-authored affine contract: no resampling, no quality inference."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from prehnite.affine_contract import (
    ALPHA, ATTESTATION, BOUNDARY, FRAME, INTERPOLATION, PROFILE,
    validate_affine_record, validate_affine_for_slot,
)
from prehnite.artifacts import ArtifactIntegrityError
from prehnite.cli import app
from prehnite.images import image_info
from prehnite.store import Journal

REF_SHA = "1" * 64
CAND_SHA = "2" * 64


def contract(*, forward=None, inverse=None, ref_sha=REF_SHA,
             cand_sha=CAND_SHA) -> dict:
    return {
        "schema_version": 2,
        "kind": "affine_2d",
        "reference_sha256": ref_sha, "candidate_sha256": cand_sha,
        "reference_to_candidate": forward if forward is not None else
            [[1, 0, 0], [0, 1, 0]],
        "candidate_to_reference": inverse if inverse is not None else
            [[1, 0, 0], [0, 1, 0]],
        "coordinate_frame": FRAME, "interpolation": INTERPOLATION,
        "boundary": BOUNDARY, "color_profile_policy": PROFILE,
        "alpha_policy": ALPHA, "attestation": ATTESTATION,
    }


def evaluate(record: dict, *, ref=(48, 32), cand=(48, 32)) -> dict:
    return validate_affine_record(json.dumps(record).encode(), REF_SHA, CAND_SHA, ref, cand)


def test_identity_has_full_continuous_overlap_and_no_executed_pixels():
    result = evaluate(contract())
    assert result["schema_version"] == 2
    assert result["continuous_center_domain_overlap_fraction"] == 1
    assert result["reference_to_candidate"] == [[1.0, 0.0, 0.0],
                                                 [0.0, 1.0, 0.0]]
    assert result["valid_discrete_sample_count"] is None
    assert result["interpolation_executed"] is False
    assert result["pixel_difference_metrics"] is None
    assert result["operator_attestation_not_verified"] is True
    assert result["human_visual_quality_score"] is None
    assert not {"prompt", "path", "asset_id"} & set(result)


def test_known_translation_valid_overlap_and_no_border_scoring():
    result = evaluate(contract(forward=[[1, 0, 3], [0, 1, -2]],
                               inverse=[[1, 0, -3], [0, 1, 2]]))
    expected = round((48 - 1 - 3) * (32 - 1 - 2) / ((48 - 1) * (32 - 1)), 8)
    assert result["continuous_center_domain_overlap_fraction"] == expected
    assert result["valid_discrete_sample_count"] is None


def test_operator_supplied_ninety_degree_rotation_rectangular_frames():
    # candidate(x',y') = (reference_height - 1 - y, x)
    result = evaluate(contract(
        forward=[[0, -1, 31], [1, 0, 0]],
        inverse=[[0, 1, 0], [-1, 0, 31]]
    ), cand=(32, 48))
    assert result["continuous_center_domain_overlap_fraction"] == 1
    assert result["interpolation_executed"] is False


def test_scale_and_crop_have_defined_continuous_overlap():
    scaled = evaluate(contract(
        forward=[[2, 0, 0], [0, 2, 0]],
        inverse=[[0.5, 0, 0], [0, 0.5, 0]],
    ), cand=(96, 64))
    assert scaled["continuous_center_domain_overlap_fraction"] == 1
    cropped = evaluate(contract(), cand=(35, 30))
    expected = round(34 * 29 / (47 * 31), 8)
    assert cropped["continuous_center_domain_overlap_fraction"] == expected


@pytest.mark.parametrize("fwd,inv", [
    ([[0, 0, 0], [0, 1, 0]], [[1, 0, 0], [0, 1, 0]]),
    ([[1, 0, 0], [0, 0.00001, 0]], [[1, 0, 0], [0, 100000, 0]]),
    ([[9, 0, 0], [0, 1, 0]], [[1 / 9, 0, 0], [0, 1, 0]]),
    ([[1, 0, 8200], [0, 1, 0]], [[1, 0, -8200], [0, 1, 0]]),
    ([[True, 0, 0], [0, 1, 0]], [[1, 0, 0], [0, 1, 0]]),
    ([[1, 0, 0], [0, 1, 0]], [[1, 0, 1], [0, 1, 0]]),
])
def test_reject_singular_unsafe_or_inconsistent_transforms(fwd, inv):
    with pytest.raises(ValueError):
        evaluate(contract(forward=fwd, inverse=inv))


def test_nan_inf_and_boolean_contract_values_never_become_numbers():
    for value in (float("nan"), float("inf"), float("-inf"), True, "1"):
        invalid = contract()
        invalid["reference_to_candidate"][0][0] = value
        with pytest.raises(ValueError):
            evaluate(invalid)


def test_reject_hash_tamper_extra_fields_and_unapproved_resampling():
    bogus = contract(cand_sha="a" * 64)
    with pytest.raises(ArtifactIntegrityError):
        evaluate(bogus)
    invalid = contract()
    invalid["upload_to"] = "https://unauthorized.example"
    with pytest.raises(ValueError, match="unsupported"):
        evaluate(invalid)
    for key, value in (
        ("interpolation", "bicubic"),
        ("attestation", "auto_detected"),
        ("alpha_policy", "unpremultiplied"),
        ("coordinate_frame", "exif_auto_rotate"),
        ("schema_version", True),
    ):
        bad = contract()
        bad[key] = value
        with pytest.raises(ValueError):
            evaluate(bad)


def test_zero_overlap_and_insufficient_overlap_refused():
    for tx in (47, 46):
        with pytest.raises(ValueError, match="overlap"):
            evaluate(contract(forward=[[1, 0, tx], [0, 1, 0]],
                              inverse=[[1, 0, -tx], [0, 1, 0]]))


def test_24mp_header_budget_supported_without_pixel_decode():
    result = evaluate(contract(), ref=(6000, 4000), cand=(6000, 4000))
    assert result["continuous_center_domain_overlap_fraction"] == 1
    with pytest.raises(ValueError, match="oversized"):
        evaluate(contract(), ref=(6001, 4000), cand=(6001, 4000))


def test_json_byte_budget_and_unexpected_fields_fail_closed():
    with pytest.raises(ValueError, match="4 KiB"):
        validate_affine_record(b" " * 4097, REF_SHA, CAND_SHA, (48, 32), (48, 32))
    with pytest.raises(ValueError, match="Invalid JSON"):
        validate_affine_record(b'{"schema_version":', REF_SHA, CAND_SHA, (48, 32), (48, 32))


def case(tmp_path):
    root = tmp_path / "workspace"
    original_root = tmp_path / "source"
    original_root.mkdir()
    source = original_root / "reference.png"
    Image.new("RGBA", (48, 32), (25, 125, 35, 255)).save(source)
    journal = Journal(root, "affine-demo")
    selected = journal.root / "selected/photo/one.png"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_bytes(source.read_bytes())
    sha = image_info(source)["sha256"]
    journal.set_fact("manifest", {"assets": [{
        "id": "one", "source": "reference.png",
        "output": {"image": "photo/one.png", "cutouts": {}},
    }]})
    journal.set_fact("input_file_sha256", {"one": sha})
    journal.set_fact("results", {"one": {
        "status": "accepted",
        "outputs": ["photo/one.png"],
        "outputs_sha256": {"photo/one.png": sha},
        "provider_request_id": "NEVER_SHOW_THIS",
    }})
    spec = tmp_path / "v2-affine.json"
    spec.write_text(json.dumps(contract(ref_sha=sha, cand_sha=sha)))
    return journal, original_root, source, selected, spec


def test_cli_validates_actual_recorded_source_without_any_output_artifact(tmp_path):
    journal, inputs, _, _, spec = case(tmp_path)
    try:
        result = validate_affine_for_slot(
            journal, "one", alignment=spec, inputs=inputs)
        assert result["comparison"] == "original_vs_base"
        assert result["pixel_difference_metrics"] is None
        assert not (journal.root / "reviews").exists()
    finally:
        journal.close()
    run = CliRunner().invoke(app, [
        "validate-affine", "affine-demo", "--asset", "one",
        "--alignment", str(spec), "--workspace", str(tmp_path / "workspace"),
        "--inputs", str(inputs),
    ])
    assert run.exit_code == 0, run.output
    result = json.loads(run.output)
    assert result["interpolation_executed"] is False
    assert "NEVER_SHOW_THIS" not in run.output


def test_stale_original_and_mismatched_profiles_are_rejected(tmp_path):
    journal, inputs, source, selected, spec = case(tmp_path)
    try:
        Image.new("RGBA", (48, 32), (200, 0, 0)).save(source)
        with pytest.raises(ArtifactIntegrityError):
            validate_affine_for_slot(journal, "one", alignment=spec, inputs=inputs)
        selected_info = image_info(selected)
        with Image.open(selected) as im:
            im.save(selected, icc_profile=b"DIFFERENT_PROFILE")
        result = journal.fact("results")
        result["one"]["outputs_sha256"]["photo/one.png"] = image_info(selected)["sha256"]
        journal.set_fact("results", result)
        original_image = Image.new("RGBA", (48, 32), (25, 125, 35, 255))
        original_image.save(source)
        spec.write_text(json.dumps(contract(
            ref_sha=image_info(source)["sha256"],
            cand_sha=image_info(selected)["sha256"],
        )))
        with pytest.raises(ValueError, match="color_profile_mismatch"):
            validate_affine_for_slot(journal, "one", alignment=spec, inputs=inputs)
    finally:
        journal.close()


def test_source_symlink_escape_rejected(tmp_path):
    journal, inputs, source, _, spec = case(tmp_path)
    try:
        outside = tmp_path / "outside.png"
        outside.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("Symlink operations not enabled")
        with pytest.raises(ValueError, match="approved"):
            validate_affine_for_slot(journal, "one", alignment=spec, inputs=inputs)
    finally:
        journal.close()
