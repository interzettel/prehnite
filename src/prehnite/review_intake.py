"""Validate offline Review Studio exports without promoting them to gold mattes.

A review ZIP/folder is untrusted input. Image bytes stay in the original input;
only derived non-image evidence is written to a separate private directory.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import stat
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image, UnidentifiedImageError


class ReviewIntakeRefused(ValueError):
    """Review data cannot be trusted as reproducible evaluation evidence."""


DATASET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{3,127}$")
PRODUCT_PATTERN = re.compile(r"^WH-S[0-9]{3}$")
HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
STATUSES = {"pending", "approved", "needs-work", "skipped"}
FLAGS = {
    "Background retained", "Missing product", "Rough edge / halo",
    "Hanger / prop included", "Light-on-light problem",
    "Strap / handle / hole", "Shadow retained", "Wrong object",
}
MAX_JSON = 2 * 1024 * 1024
MAX_FILES = 210
MAX_SINGLE_FILE = 32 * 1024 * 1024
MAX_TOTAL = 400 * 1024 * 1024
MAX_IMAGES = 200
MAX_PIXELS = 24_000_000
ALLOWED_OTHER_FILES = {"review_results.json", "feedback.txt", "README.txt"}


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require(check: bool, code: str) -> None:
    if not check:
        raise ReviewIntakeRefused(code)


def _plain_string(value: object, limit: int = 600) -> bool:
    return isinstance(value, str) and len(value) <= limit and "\x00" not in value


def _allowed_member(path: str) -> bool:
    if path in ALLOWED_OTHER_FILES:
        return True
    if "\\" in path or path.startswith("/") or "//" in path or any(
        component in ("", ".", "..") for component in path.split("/")
    ):
        return False
    parts = path.split("/")
    return (len(parts) == 2 and parts[0] == "reviewed_masks" and
            re.fullmatch(r"WH-S[0-9]{3}_human_reviewed\.png", parts[1]) is not None)


def _read_archive(path: Path) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            _require(0 < len(entries) <= MAX_FILES, "archive_entry_limit")
            members: dict[str, bytes] = {}
            total = 0
            for item in entries:
                _require(not item.is_dir() and _allowed_member(item.filename), "unsafe_or_unexpected_archive_member")
                mode = (item.external_attr >> 16) & 0xFFFF
                _require(not stat.S_ISLNK(mode), "symlink_member_refused")
                _require(item.flag_bits & 1 == 0, "encrypted_archive_refused")
                _require(item.filename not in members, "duplicate_archive_member")
                _require(0 < item.file_size <= MAX_SINGLE_FILE, "archive_member_size_limit")
                total += item.file_size
                _require(total <= MAX_TOTAL, "archive_expansion_limit")
                _require(item.file_size <= max(1, item.compress_size) * 250, "extreme_compression_ratio")
                members[item.filename] = archive.read(item)
            return members
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
        raise ReviewIntakeRefused("archive_read_failed") from exc


def _read_folder(folder: Path) -> dict[str, bytes]:
    _require(folder.is_dir() and not folder.is_symlink(), "missing_review_folder")
    root = folder.resolve()
    paths = list(folder.iterdir())
    _require(0 < len(paths) <= MAX_FILES, "folder_entry_limit")
    members: dict[str, bytes] = {}
    total = 0
    for path in paths:
        if path.name == "reviewed_masks":
            _require(path.is_dir() and not path.is_symlink(), "unsafe_review_mask_folder")
            children = list(path.iterdir())
            _require(len(children) <= MAX_IMAGES, "folder_mask_count_limit")
        else:
            children = [path]
        for file in children:
            _require(not file.is_symlink() and file.is_file(), "unsafe_review_member")
            _require(file.resolve().is_relative_to(root), "review_member_outside_root")
            rel = file.relative_to(folder).as_posix()
            _require(_allowed_member(rel), "unsafe_or_unexpected_archive_member")
            size = file.stat().st_size
            _require(0 < size <= MAX_SINGLE_FILE, "archive_member_size_limit")
            total += size
            _require(total <= MAX_TOTAL, "archive_expansion_limit")
            members[rel] = file.read_bytes()
    _require(len(members) <= MAX_FILES, "folder_entry_limit")
    return members


def _mask_summary(payload: bytes, dims: tuple[int, int], approved: bool) -> dict:
    try:
        with Image.open(io.BytesIO(payload)) as img:
            _require(img.format == "PNG" and img.mode == "RGBA", "review_mask_must_be_rgba_png")
            _require(img.size == dims, "review_mask_dimensions_mismatch")
            _require(img.width * img.height <= MAX_PIXELS, "review_mask_pixel_limit")
            img.load()
            alpha = img.getchannel("A")
            low, high = alpha.getextrema()
            coverage = sum(v > 127 for v in alpha.tobytes()) / (img.width * img.height)
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ReviewIntakeRefused("review_mask_decode_failed") from exc
    _require(not approved or (low < 255 and high > 0), "approved_mask_full_or_empty")
    return {
        "sha256": _sha(payload),
        "selection_fraction_128": round(coverage, 6),
        "has_soft_alpha": low < high,
        "geometry_warning": "empty_or_full_mask" if low == high else None,
    }


def validate_export(members: dict[str, bytes]) -> dict:
    """Structure, hashes, and annotation consistency; NEVER a gold mask scorer."""
    _require("review_results.json" in members, "missing_review_results_json")
    content = members["review_results.json"]
    _require(len(content) <= MAX_JSON, "review_json_too_large")
    try:
        report = json.loads(content.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ReviewIntakeRefused("invalid_review_json") from exc
    _require(isinstance(report, dict), "invalid_review_structure")
    _require(report.get("schema_version") == 1 and report.get("kind") == "prehnite_human_mask_review", "unsupported_review_schema")
    dataset = report.get("dataset_id")
    _require(isinstance(dataset, str) and DATASET_PATTERN.fullmatch(dataset) is not None, "invalid_dataset_id")
    _require(report.get("independent_ground_truth") is False, "false_independent_ground_truth_claim")
    _require(_plain_string(report.get("exported_at"), 64), "invalid_export_timestamp")
    reviewer = report.get("reviewer")
    _require(reviewer is None or _plain_string(reviewer, 128), "invalid_reviewer")
    objects = report.get("objects")
    _require(isinstance(objects, list) and 0 < len(objects) <= MAX_IMAGES, "invalid_review_object_count")
    _require(type(report.get("expected_images")) is int and report["expected_images"] == len(objects), "expected_image_count_mismatch")
    counts = Counter()
    flags = Counter()
    statuses = []
    seen_ids = set()
    used_masks = set()
    for obj in objects:
        _require(isinstance(obj, dict), "invalid_object")
        id_ = obj.get("id")
        _require(isinstance(id_, str) and PRODUCT_PATTERN.fullmatch(id_) is not None, "invalid_product_id")
        _require(id_ not in seen_ids, "duplicate_product_id")
        seen_ids.add(id_)
        state = obj.get("status")
        _require(state in STATUSES, "invalid_review_status")
        _require(obj.get("reference_is_independent") is False, "false_independent_ground_truth_claim")
        _require(obj.get("human_visually_accepted") is (state == "approved"), "inconsistent_visual_acceptance")
        _require(obj.get("human_reviewed") is (state != "pending"), "inconsistent_reviewed_flag")
        _require(_plain_string(obj.get("title"), 140) and _plain_string(obj.get("category"), 140), "invalid_item_metadata")
        _require(_plain_string(obj.get("target_rule"), 400), "invalid_target_rule")
        _require(_plain_string(obj.get("reviewer_notes"), 6000), "invalid_reviewer_notes")
        _require(isinstance(obj.get("issue_flags"), list) and len(obj["issue_flags"]) <= len(FLAGS), "invalid_issue_flags")
        _require(len(set(obj["issue_flags"])) == len(obj["issue_flags"]) and set(obj["issue_flags"]).issubset(FLAGS), "unknown_or_duplicate_issue_flags")
        dims = obj.get("dimensions")
        _require(isinstance(dims, list) and len(dims) == 2 and all(type(n) is int and 16 <= n <= 10000 for n in dims) and dims[0] * dims[1] <= MAX_PIXELS, "invalid_image_dimensions")
        for key in ("source_sha256", "original_candidate_mask_sha256"):
            hash_ = obj.get(key)
            _require(isinstance(hash_, str) and HASH_PATTERN.fullmatch(hash_) is not None, "invalid_source_or_candidate_hash")
        rating = obj.get("rating_1_to_5")
        _require(rating is None or (type(rating) is int and 1 <= rating <= 5), "invalid_review_rating")
        edited = obj.get("manual_mask_edited")
        strokes = obj.get("brush_strokes")
        _require(type(edited) is bool and type(strokes) is int and 0 <= strokes <= 100000, "invalid_edit_record")
        _require(not edited or strokes > 0, "invalid_edit_record")
        when = obj.get("reviewed_at")
        _require((when is None) if state == "pending" else _plain_string(when, 64), "invalid_review_date")
        mask_path = obj.get("output_mask_path")
        if state == "pending":
            _require(mask_path is None, "pending_review_has_mask_path")
        else:
            required_path = f"reviewed_masks/{id_}_human_reviewed.png"
            _require(mask_path == required_path, "incorrect_review_mask_path")
            _require(required_path in members, "review_mask_missing")
            used_masks.add(required_path)
        mask = _mask_summary(members[mask_path], tuple(dims), state == "approved") if mask_path else None
        counts[state] += 1
        flags.update(obj["issue_flags"])
        statuses.append({
            "id": id_, "status": state, "quality_rating": rating,
            "issues": sorted(obj["issue_flags"]),
            "mask_edited": edited, "brush_strokes": strokes,
            "reviewed_mask": mask,
            "requires_repair": state == "needs-work",
            "independent_gold_reference": False,
        })
    included_masks = {path for path in members if path.startswith("reviewed_masks/")}
    _require(included_masks == used_masks, "unexpected_or_missing_review_masks")
    reviewed = len(objects) - counts["pending"]
    for name, actual in (("reviewed_images", reviewed), ("approved_count", counts["approved"]),
                         ("needs_work_count", counts["needs-work"]), ("skipped_count", counts["skipped"])):
        _require(type(report.get(name)) is int and report[name] == actual, "review_counter_mismatch")
    ratings = [s["quality_rating"] for s in statuses if s["quality_rating"] is not None and s["status"] != "pending"]
    priorities = [s for s in statuses if s["status"] == "needs-work"]
    return {
        "schema_version": 1, "kind": "prehnite_validated_human_review_intake",
        "dataset_id": dataset, "input_report_sha256": _sha(content),
        "private_feedback_only": True,
        "independent_ground_truth_count": 0, "alpha_iou_measured": False,
        "human_approval_is_not_independent_gold": True,
        "count": len(statuses), "reviewed": reviewed,
        "pending": counts["pending"], "visually_approved": counts["approved"],
        "needs_work": counts["needs-work"], "skipped": counts["skipped"],
        "mean_review_rating": round(sum(ratings) / len(ratings), 3) if ratings else None,
        "issue_frequency": dict(sorted(flags.items(), key=lambda v: (-v[1], v[0]))),
        "repair_triage_ids": [s["id"] for s in priorities],
        "objects": statuses,
    }


def _text_report(data: dict) -> str:
    lines = ["PREHNITE / HUMAN REVIEW INTAKE", "=" * 40,
             "Validated export structure and mask PNG dimensions only.",
             "Human approvals are not independent reference masks or IoU results.",
             f"Images: {data['count']} | Reviewed: {data['reviewed']} | Pending: {data['pending']}",
             f"Visually approved: {data['visually_approved']} | Needs work: {data['needs_work']} | Skipped: {data['skipped']}",
             "", "ISSUE COUNTS"]
    lines += [f"  {name}: {count}" for name, count in data["issue_frequency"].items()] or ["  (none)"]
    lines += ["", "REPAIR QUEUE (user flagged needs-work)"]
    lines += [f"  {s['id']}: {', '.join(s['issues']) or 'no specific issue selected'}" for s in data["objects"] if s["requires_repair"]] or ["  (none)"]
    lines += ["", "Next: independent annotations and a second human review are required before gold-matte or segmentation-accuracy claims.", ""]
    return "\n".join(lines)


def inspect(path: Path) -> dict:
    """Read browser-selected autosave folder or exported ZIP; never extract."""
    return validate_export(_read_folder(path) if path.is_dir() else _read_archive(path))


def write_report(path: Path, destination: Path) -> dict:
    """Create-only reports in a separate private empty directory."""
    output = destination.resolve()
    input_path = path.resolve()
    _require(output != input_path and (not path.is_dir() or not output.is_relative_to(input_path)), "output_overlaps_input")
    _require(not output.exists() or (output.is_dir() and not any(output.iterdir())), "destination_not_empty")
    report = inspect(path)
    output.mkdir(parents=True, exist_ok=True)
    (output / "validated_review.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "triage.txt").write_text(_text_report(report), encoding="utf-8")
    return report
