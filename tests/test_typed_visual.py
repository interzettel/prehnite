"""No-service Jev visual evaluation preflight and typed-mock regressions."""
from __future__ import annotations

import hashlib
import io
import json
from decimal import Decimal

import pytest
from PIL import Image, ImageOps

from prehnite.artifacts import ArtifactIntegrityError
from prehnite.typed_visual import (
    MAX_IMAGE_BYTES, MODEL, Question, parse_mock_answers, preflight,
    prepare_still_image, validate_questions,
)


def mock_input(tmp_path, *, kind="RGB", size=(480, 360), exif=None):
    root = tmp_path / "private-inputs"
    root.mkdir()
    source = root / "private.png"
    image = Image.new(kind, size, (20, 92, 69) if kind == "RGB"
                      else (20, 92, 69, 130))
    kwargs = {"exif": exif} if exif is not None else {}
    image.save(source, **kwargs)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return root, source, digest


def questions():
    return (Question("is_present", "noul"),
            Question("category", "choice", ("product", "none")),
            Question("composition", "score"),
            Question("region", "box", presence_key="is_present"))


def answer(present=True):
    return {"is_present": {"value": present, "confidence": .91},
            "category": {"value": "product", "confidence": .8},
            "composition": {"value": .72, "confidence": .51},
            "region": {"value": [0.1, 0.2, 0.8, 0.9] if present else None,
                       "confidence": .79}}


def approve(image, qs=None, **overrides):
    params = dict(allow_paid=True, allow_cloud_uploads=True,
                  allow_experimental_images=True, allow_experimental_box=True,
                  input_token_ceiling=8000, max_usd=Decimal("0.001"))
    params.update(overrides)
    return preflight(image, qs or questions(), **params)


def test_source_digest_and_metadata_stripped_before_mock_preflight(tmp_path):
    root, src, digest = mock_input(tmp_path)
    image = prepare_still_image(root, src.name, digest)
    assert image.source_sha256 == digest
    assert image.format == "jpg"
    assert 280 <= image.width <= 1568
    assert image.byte_count == len(image.data)
    assert src.name not in repr(image)
    with Image.open(io.BytesIO(image.data)) as result:
        assert result.format == "JPEG"
        assert not result.getexif()
        assert result.info.get("icc_profile") is None
    permit = approve(image)
    assert permit.model == MODEL
    assert permit.status == "local_preflight_only_no_dispatch"
    assert permit.reserved_usd == Decimal("0.000336")
    assert permit.experimental_long_context is False


def test_opt_ins_missing_any_guard_never_prepare_permit(tmp_path):
    root, src, digest = mock_input(tmp_path)
    media = prepare_still_image(root, src.name, digest)
    for field in ("allow_paid", "allow_cloud_uploads", "allow_experimental_images",
                  "allow_experimental_box"):
        with pytest.raises(PermissionError):
            approve(media, **{field: False})
    with pytest.raises(ValueError, match="pinned"):
        approve(media, model="jev-latest")
    with pytest.raises(PermissionError, match="USD"):
        approve(media, max_usd=Decimal("0.000001"))


def test_missing_price_or_image_token_limit_is_not_guessed(tmp_path):
    root, src, digest = mock_input(tmp_path)
    media = prepare_still_image(root, src.name, digest)
    for token_bound in (None, True, 0, -1, 64001):
        with pytest.raises(ValueError):
            approve(media, input_token_ceiling=token_bound)
    with pytest.raises(ValueError):
        approve(media, max_usd=0.5)
    for price in (Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValueError, match="pricing"):
            approve(media, price_usd_per_million=price)


def test_context_extension_separate_explicit_opt_in(tmp_path):
    root, src, digest = mock_input(tmp_path)
    media = prepare_still_image(root, src.name, digest)
    permit = approve(media, allow_long_context=True, input_token_ceiling=65500,
                     max_usd=Decimal("1"))
    assert permit.experimental_long_context is True
    with pytest.raises(ValueError, match="context"):
        approve(media, allow_long_context=True,
                input_token_ceiling=262001, max_usd=Decimal("1"))


def test_actual_sample_bytes_cannot_be_tampered_after_preparation(tmp_path):
    root, src, digest = mock_input(tmp_path)
    media = prepare_still_image(root, src.name, digest)
    from dataclasses import replace
    with pytest.raises(ArtifactIntegrityError):
        approve(replace(media, data=media.data + b"!"))
    with pytest.raises(ArtifactIntegrityError):
        approve(replace(media, prepared_sha256="a" * 64))
    src.write_bytes(b"changed")
    with pytest.raises(ArtifactIntegrityError):
        prepare_still_image(root, src.name, digest)


def test_input_root_symlink_and_traversal_refused(tmp_path):
    root, src, digest = mock_input(tmp_path)
    with pytest.raises((ValueError, ArtifactIntegrityError)):
        prepare_still_image(root, "../private.png", digest)
    outside = tmp_path / "outside.png"
    outside.write_bytes(src.read_bytes())
    src.unlink()
    try:
        src.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this account")
    with pytest.raises(ArtifactIntegrityError, match="escapes"):
        prepare_still_image(root, src.name, digest)


def test_exif_is_normalized_and_gps_metadata_removed(tmp_path):
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "PRIVATE PROMPT OR LOCATION"
    root, src, digest = mock_input(tmp_path, exif=exif)
    prepared = prepare_still_image(root, src.name, digest)
    assert (prepared.width, prepared.height) == (360, 480)
    assert b"PRIVATE PROMPT" not in prepared.data
    with Image.open(io.BytesIO(prepared.data)) as image:
        assert not image.getexif()
        assert image.getpixel((0, 0))


def test_rgba_preserved_and_unsupported_color_profile_rejected(tmp_path):
    root, src, digest = mock_input(tmp_path, kind="RGBA")
    prepared = prepare_still_image(root, src.name, digest)
    assert prepared.format == "png"
    with Image.open(io.BytesIO(prepared.data)) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 130
    Image.new("RGB", (480, 360)).save(src, icc_profile=b"fake-profile")
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="ICC-tagged"):
        prepare_still_image(root, src.name, digest)


def test_image_dimension_policy_and_oversized_source_refused(tmp_path):
    root, src, _ = mock_input(tmp_path)
    Image.new("RGB", (100, 480)).save(src)
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="280px"):
        prepare_still_image(root, src.name, sha)
    Image.new("RGB", (2700, 2400)).save(src)
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    prepared = prepare_still_image(root, src.name, sha)
    assert prepared.width == 1568
    assert 280 <= prepared.height <= 1568


def test_malformed_question_configurations_refused():
    with pytest.raises(ValueError, match="2–12"):
        Question("choice", "choice", ("only",))
    with pytest.raises(ValueError, match="presence"):
        Question("region", "box")
    with pytest.raises(ValueError, match="Unsafe"):
        Question("SEND_SECRETS!", "noul")
    with pytest.raises(ValueError, match="Box must reference"):
        validate_questions((Question("present", "choice", ("yes", "no")),
                            Question("region", "box", presence_key="present")))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_questions((Question("foo", "score"), Question("foo", "noul")))


def test_typed_answers_validated_without_promoting_to_acceptance():
    result = parse_mock_answers(questions(), answer())
    assert result["status"] == "mock_evaluation_only_no_provider_dispatch"
    assert result["automatic_acceptance_authorized"] is False
    assert result["answers"]["region"]["value"] == [0.1, 0.2, 0.8, 0.9]
    assert result["answers"]["is_present"]["value"] is True
    assert result["answers"]["composition"]["human_verified"] is False
    assert "quality_score" not in json.dumps(result)


def test_absence_gates_boxes_and_prevents_false_detection():
    result = parse_mock_answers(questions(), answer(False))
    assert result["answers"]["region"]["value"] is None
    invalid = answer(False)
    invalid["region"]["value"] = [0.1, 0.1, 0.3, 0.3]
    with pytest.raises(ValueError, match="Absent"):
        parse_mock_answers(questions(), invalid)


@pytest.mark.parametrize("box", [
    [0, 0, 1.1, 1], [-0.1, 0, 1, 1], [0.1, 0, 0.1, 0.2],
    [0.7, .1, .6, .2], ["0", 0, 1, 1], [True, 0, 1, 1],
    [0, float("nan"), 1, 1], [0, 0, float("inf"), 1], [0, 1],
])
def test_box_invalid_or_unbounded_is_refused(box):
    invalid = answer()
    invalid["region"]["value"] = box
    with pytest.raises(ValueError):
        parse_mock_answers(questions(), invalid)


def test_malformed_provider_mock_reply_and_unexpected_fields_refused():
    for invalid in [
        None, {}, {"x": {"value": True}},
        dict(answer(), extraneous={"value": True, "confidence": 1}),
    ]:
        with pytest.raises(ValueError):
            parse_mock_answers(questions(), invalid)
    for field, value in [
        ("is_present", 1), ("category", "undeclared"),
        ("composition", -1), ("composition", True),
    ]:
        invalid = answer()
        invalid[field]["value"] = value
        with pytest.raises(ValueError):
            parse_mock_answers(questions(), invalid)
    invalid = answer()
    invalid["is_present"]["confidence"] = float("nan")
    with pytest.raises(ValueError):
        parse_mock_answers(questions(), invalid)
    invalid = answer()
    invalid["region"]["hidden_prompt"] = "PRIVATE PASSWORD"
    with pytest.raises(ValueError, match="unexpected"):
        parse_mock_answers(questions(), invalid)
