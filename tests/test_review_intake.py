"""Synthetic browser-review export fixtures; no real reviewer data in CI."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
import os

import pytest
from PIL import Image, ImageDraw

from prehnite.review_intake import ReviewIntakeRefused, _allowed_member, inspect, validate_export, write_report


def _mask(size=(60, 84), *, empty=False, grayscale=False) -> bytes:
    image = Image.new("L" if grayscale else "RGBA", size, 0 if grayscale else (0, 0, 0, 0))
    if not empty:
        ImageDraw.Draw(image).rectangle((8, 7, size[0]-8, size[1]-8),
                                         fill=255 if grayscale else (255, 255, 255, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _payload() -> dict:
    objects = []
    for id_, state in (
        ("WH-S001", "needs-work"), ("WH-S003", "approved"),
        ("WH-S005", "pending"), ("WH-S007", "skipped")
    ):
        reviewed = state != "pending"
        objects.append({
            "id": id_, "title": "Synthetic apparel", "category": "Test garment",
            "source_sha256": "a"*64, "original_candidate_mask_sha256": "b"*64,
            "dimensions": [60, 84], "status": state,
            "rating_1_to_5": 2 if state == "needs-work" else 4 if state == "approved" else None,
            "issue_flags": ["Background retained"] if state == "needs-work" else [],
            "reviewer_notes": "PRIVATE NOTE DO NOT EMIT",
            "manual_mask_edited": state == "needs-work",
            "brush_strokes": 3 if state == "needs-work" else 0,
            "reference_is_independent": False,
            "human_visually_accepted": state == "approved",
            "human_reviewed": reviewed,
            "reviewed_at": "2026-10-17T00:00:00Z" if reviewed else None,
            "output_mask_path": f"reviewed_masks/{id_}_human_reviewed.png" if reviewed else None,
            "target_rule": "Product only",
        })
    return {
        "schema_version": 1, "kind": "prehnite_human_mask_review",
        "dataset_id": "wearhouse-synthetic-pilot-2026-10-17-12-case-review-v1",
        "exported_at": "2026-10-17T00:00:00Z", "reviewer": "PRIVATE REVIEWER",
        "expected_images": 4, "reviewed_images": 3,
        "approved_count": 1, "needs_work_count": 1,
        "skipped_count": 1, "independent_ground_truth": False, "objects": objects,
    }


def _files():
    payload = _payload()
    return {
        "review_results.json": json.dumps(payload).encode("utf-8"),
        "feedback.txt": b"PRIVATE RAW FEEDBACK",
        "README.txt": b"synthetic test only",
        **{rec["output_mask_path"]: _mask() for rec in payload["objects"]
           if rec["output_mask_path"]},
    }


def _zip(tmp_path, files):
    file = tmp_path / "review.zip"
    with zipfile.ZipFile(file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return file


def _alter(files, fn):
    data = dict(files)
    payload = json.loads(data["review_results.json"])
    fn(payload)
    data["review_results.json"] = json.dumps(payload).encode()
    return data


def test_offline_zip_summary_and_privacy(tmp_path):
    zip_path = _zip(tmp_path, _files())
    out = tmp_path / "private-results"
    result = write_report(zip_path, out)
    assert (result["count"], result["reviewed"], result["pending"]) == (4, 3, 1)
    assert (result["visually_approved"], result["needs_work"], result["skipped"]) == (1, 1, 1)
    assert result["repair_triage_ids"] == ["WH-S001"]
    assert result["mean_review_rating"] == 3.0
    assert result["issue_frequency"] == {"Background retained": 1}
    assert result["independent_ground_truth_count"] == 0
    assert result["alpha_iou_measured"] is False
    assert result["objects"][1]["reviewed_mask"]["sha256"]
    assert result["objects"][2]["reviewed_mask"] is None
    assert "PRIVATE" not in (out / "validated_review.json").read_text()
    assert "PRIVATE" not in (out / "triage.txt").read_text()
    assert not list(out.glob("*.png"))
    with pytest.raises(ReviewIntakeRefused, match="destination_not_empty"):
        write_report(zip_path, out)


def test_folder_autosave_supported_without_mutation(tmp_path):
    saved = tmp_path / "selected-browser-folder"
    saved.mkdir()
    for name, content in _files().items():
        file = saved / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content)
    assert inspect(saved)["reviewed"] == 3
    with pytest.raises(ReviewIntakeRefused, match="output_overlaps_input"):
        write_report(saved, saved / "cannot-overwrite")


@pytest.mark.parametrize("change,code", [
    (lambda r: r.update(independent_ground_truth=True), "false_independent_ground_truth_claim"),
    (lambda r: r["objects"][0].update(reference_is_independent=True), "false_independent_ground_truth_claim"),
    (lambda r: r["objects"][0].update(human_visually_accepted=True), "inconsistent_visual_acceptance"),
    (lambda r: r["objects"][0].update(human_reviewed=False), "inconsistent_reviewed_flag"),
    (lambda r: r.update(approved_count=50), "review_counter_mismatch"),
    (lambda r: r.update(expected_images=12), "expected_image_count_mismatch"),
    (lambda r: r["objects"][1].update(id="WH-S001"), "duplicate_product_id"),
    (lambda r: r["objects"][1].update(output_mask_path="../../evil.png"), "incorrect_review_mask_path"),
    (lambda r: r["objects"][1].update(dimensions=[61, 84]), "review_mask_dimensions_mismatch"),
    (lambda r: r["objects"][0].update(issue_flags=["Fabricastic hallucination"]), "unknown_or_duplicate_issue_flags"),
    (lambda r: r["objects"][0].update(brush_strokes=0), "invalid_edit_record"),
    (lambda r: r["objects"][0].update(source_sha256="abcdef"), "invalid_source_or_candidate_hash"),
])
def test_false_claims_and_corrupted_metadata_refused(change, code):
    with pytest.raises(ReviewIntakeRefused, match=code):
        validate_export(_alter(_files(), change))


def test_missing_and_extra_alpha_mattes_refused(tmp_path):
    files = _files()
    files.pop("reviewed_masks/WH-S001_human_reviewed.png")
    with pytest.raises(ReviewIntakeRefused, match="review_mask_missing"):
        inspect(_zip(tmp_path, files))
    files = _files()
    files["reviewed_masks/WH-S005_human_reviewed.png"] = _mask()
    with pytest.raises(ReviewIntakeRefused, match="unexpected_or_missing_review_masks"):
        inspect(_zip(tmp_path, files))


@pytest.mark.parametrize("path", [
    "../evil.png", "/root/evil", "assets/other.png",
    "reviewed_masks/../../evil.png",
    r"reviewed_masks\WH-S005_human_reviewed.png",
])
def test_traversal_and_unexpected_zip_paths_refused(tmp_path, path):
    assert not _allowed_member(path)  # Literal unsafe path is always rejected.
    files = _files()
    files[path] = b"x"
    # Windows' zipfile writer normalizes backslashes to '/'. In that case
    # the extra now-valid-looking alpha member must still be rejected.
    reason = ("unexpected_or_missing_review_masks"
              if os.name == "nt" and "\\" in path
              else "unsafe_or_unexpected_archive_member")
    with pytest.raises(ReviewIntakeRefused, match=reason):
        inspect(_zip(tmp_path, files))


def test_corrupt_png_wrong_mode_and_empty_approved_alpha(tmp_path):
    files = _files()
    files["reviewed_masks/WH-S003_human_reviewed.png"] = b"damaged"
    with pytest.raises(ReviewIntakeRefused, match="review_mask_decode_failed"):
        inspect(_zip(tmp_path, files))
    files = _files()
    files["reviewed_masks/WH-S003_human_reviewed.png"] = _mask(grayscale=True)
    with pytest.raises(ReviewIntakeRefused, match="review_mask_must_be_rgba_png"):
        inspect(_zip(tmp_path, files))
    files = _files()
    files["reviewed_masks/WH-S003_human_reviewed.png"] = _mask(empty=True)
    with pytest.raises(ReviewIntakeRefused, match="approved_mask_full_or_empty"):
        inspect(_zip(tmp_path, files))


def test_bad_zip_and_duplicate_archive_member(tmp_path):
    raw = tmp_path / "broken.zip"
    raw.write_bytes(b"not an archive")
    with pytest.raises(ReviewIntakeRefused, match="archive_read_failed"):
        inspect(raw)
    raw = tmp_path / "review.zip"
    members = _files()
    with zipfile.ZipFile(raw, "w") as z:
        for key, content in members.items():
            z.writestr(key, content)
        z.writestr("review_results.json", members["review_results.json"])
    with pytest.raises(ReviewIntakeRefused, match="duplicate_archive_member"):
        inspect(raw)
