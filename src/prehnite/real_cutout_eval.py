"""Local-only reference-alpha scoring for owner-authorized real photographs.

All paths are relative to an explicit, user-controlled data root.
No image bytes, absolute paths, author names or URLs appear in output.
A valid rights *attestation* is not a legal determination.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, UnidentifiedImageError

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 24_000_000
VALID_COHORTS = frozenset({
    "opaque-product", "portrait-hair", "animal-fur", "glass",
    "translucent-fabric", "furniture-openings", "occlusions", "other",
})
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_MAX_ITEMS = 200


class EvaluationRefused(ValueError):
    """Refuse invalid provenance, unsupported images, or unsafe paths."""


def _check_rights(record: dict) -> None:
    if not isinstance(record, dict) or record.get("right_to_process_attested") is not True:
        raise EvaluationRefused("processing_rights_not_attested")
    if record.get("source_type") not in {"owner-authorized", "third-party-licensed"}:
        raise EvaluationRefused("source_type_missing_or_unsupported")
    if record.get("source_type") == "third-party-licensed":
        required = ("license_id", "license_url", "source_url", "creator")
        if not all(isinstance(record.get(key), str) and record[key].strip()
                   for key in required):
            raise EvaluationRefused("third_party_license_provenance_incomplete")
        if not all(record[k].startswith("https://") for k in ("license_url", "source_url")):
            raise EvaluationRefused("source_or_license_url_must_be_https")
    # We make no assumption that an MIT-licensed *dataset* confers
    # rights to every underlying photograph. Attestation is necessary
    # for intake but does not establish provenance independently.


def _checked_file(root: Path, value: object, digest: object) -> Path:
    if not isinstance(value, str) or not value or not isinstance(digest, str):
        raise EvaluationRefused("missing_file_path_or_digest")
    if not _SHA256_RE.fullmatch(digest):
        raise EvaluationRefused("invalid_input_sha256")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise EvaluationRefused("unsafe_relative_path")
    file = (root / relative).resolve()
    if not file.is_relative_to(root) or not file.is_file():
        raise EvaluationRefused("input_missing_or_outside_data_root")
    if file.stat().st_size > MAX_FILE_BYTES or file.stat().st_size == 0:
        raise EvaluationRefused("input_oversized_or_empty")
    h = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != digest:
        raise EvaluationRefused("input_sha256_mismatch")
    return file


def _open_image(path: Path, *, role: str) -> Image.Image:
    try:
        with Image.open(path) as image:
            if image.format not in {"PNG", "JPEG"}:
                raise EvaluationRefused("unsupported_image_encoding")
            if image.width * image.height > MAX_PIXELS or min(image.size) < 16:
                raise EvaluationRefused("unsupported_image_dimensions")
            if image.getexif().get(274, 1) != 1:
                raise EvaluationRefused("exif_orientation_requires_pre_normalization")
            if role == "source":
                if image.mode not in {"RGB", "L"}:
                    raise EvaluationRefused("unsupported_source_mode")
            else:
                if image.format != "PNG" or image.mode not in {"L", "RGBA"}:
                    raise EvaluationRefused("matte_must_be_grayscale_or_rgba_png")
            if role != "source" and image.mode == "RGBA":
                return image.getchannel("A").copy()
            return image.copy()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise EvaluationRefused("image_decode_failed") from exc


def _scores(reference: Image.Image, candidate: Image.Image) -> dict:
    if reference.mode != "L" or candidate.mode != "L" or reference.size != candidate.size:
        raise EvaluationRefused("alpha_geometry_mismatch")
    a, b = reference.tobytes(), candidate.tobytes()
    intersection = sum(x >= 128 and y >= 128 for x, y in zip(a, b))
    union = sum(x >= 128 or y >= 128 for x, y in zip(a, b))
    alpha_error = sum(abs(x - y) for x, y in zip(a, b))
    def edge(img: Image.Image) -> bytes:
        return ImageChops.difference(
            img.filter(ImageFilter.MaxFilter(3)),
            img.filter(ImageFilter.MinFilter(3))
        ).tobytes()
    edges_a, edges_b = edge(reference), edge(candidate)
    edge_error = sum(abs(x - y) for x, y in zip(edges_a, edges_b))
    return {
        "binary_iou_128": round(intersection / union if union else 1.0, 6),
        "normalized_alpha_mae": round(alpha_error / (255 * len(a)), 6),
        "alpha_sad_pixels": round(alpha_error / 255, 6),
        "normalized_edge_mae_3x3": round(edge_error / (255 * len(a)), 6),
        "width": reference.width, "height": reference.height,
    }


def evaluate(manifest: dict, data_root: Path) -> dict:
    """No network, inference, writes, external processing or auto-acceptance."""
    data_root = data_root.resolve(strict=True)
    if not data_root.is_dir():
        raise EvaluationRefused("invalid_data_root")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise EvaluationRefused("unsupported_manifest_version")
    items = manifest.get("items")
    if not isinstance(items, list) or not (1 <= len(items) <= _MAX_ITEMS):
        raise EvaluationRefused("invalid_manifest_item_count")
    output = []
    for ordinal, item in enumerate(items, 1):
        if not isinstance(item, dict) or item.get("cohort") not in VALID_COHORTS:
            raise EvaluationRefused("unsupported_cohort")
        _check_rights(item.get("rights"))
        # Reference gold label must have been independently inspected by
        # a human annotator. Mere signed metadata is not a verified matte.
        gold = item.get("reference_review")
        if gold not in {"reviewed", "unreviewed"}:
            raise EvaluationRefused("reference_review_status_required")
        paths, digests = item.get("paths"), item.get("sha256")
        if not isinstance(paths, dict) or not isinstance(digests, dict):
            raise EvaluationRefused("missing_path_or_hash_map")
        selected = {name: _checked_file(data_root, paths.get(name), digests.get(name))
                    for name in ("source", "reference", "candidate")}
        source = _open_image(selected["source"], role="source")
        ref = _open_image(selected["reference"], role="reference")
        cand = _open_image(selected["candidate"], role="candidate")
        if source.size != ref.size or ref.size != cand.size:
            raise EvaluationRefused("source_reference_candidate_dimensions_mismatch")
        output.append({
            "index": ordinal,
            "cohort": item["cohort"],
            "reference_review": gold,
            "rights_status": "user_attested_not_independently_verified",
            "human_visual_acceptance": "not_assessed",
            "metrics": _scores(ref, cand),
            "source_sha256": digests["source"],
            "reference_sha256": digests["reference"],
            "candidate_sha256": digests["candidate"],
        })
    by_cohort = {}
    for row in output:
        by_cohort.setdefault(row["cohort"], []).append(row)
    aggregate = {
        name: {
            "count": len(rows),
            "mean_alpha_mae": round(sum(r["metrics"]["normalized_alpha_mae"]
                                        for r in rows) / len(rows), 6),
            "mean_iou": round(sum(r["metrics"]["binary_iou_128"]
                                  for r in rows) / len(rows), 6),
        } for name, rows in sorted(by_cohort.items())
    }
    return {
        "schema_version": 1,
        "scoring_only": True,
        "source": "locally_supplied_attested_images",
        "rights_independently_verified": False,
        "human_visual_acceptance_established": False,
        "metrics_not_release_gates": True,
        "image_data_exported": False,
        "provider_requests": 0, "paid_usd": 0,
        "count": len(output), "per_cohort": aggregate, "items": output,
    }


def run(manifest_path: Path, data_root: Path, report: Path) -> dict:
    """Read strictly local paths; publish a text-only PRIVATE report."""
    with manifest_path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    result = evaluate(manifest, data_root)
    # Refuse writing report inside data corpus, avoiding accidental
    # source/ground-truth replacement even under a user-chosen filename.
    resolved = report.resolve()
    if resolved.is_relative_to(data_root.resolve()) or resolved in {
        manifest_path.resolve(), data_root.resolve()
    }:
        raise EvaluationRefused("report_output_overlaps_inputs")
    from .artifacts import atomic_text
    atomic_text(report, json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result
