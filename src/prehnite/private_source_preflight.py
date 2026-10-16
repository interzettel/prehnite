"""Private, offline source-only pilot preflight; never a segmentation quality score.

Accepts a user-controlled local export plus exact R2 object metadata supplied
separately. No network access, source publication, model calls or image writes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image, UnidentifiedImageError

_MAX_ITEMS = 200
_MAX_FILE_BYTES = 64 * 1024 * 1024
_MAX_PIXELS = 24_000_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROLES = frozenset(("front", "care_label"))


class SourcePreflightRefused(ValueError):
    """Fail closed without revealing the private source filename."""


def _private_file(root: Path, record: dict) -> Path:
    name = record.get("path")
    expected_hash = record.get("sha256")
    expected_size = record.get("size")
    if (not isinstance(name, str) or not name
            or not isinstance(expected_hash, str) or not _SHA256.fullmatch(expected_hash)
            or type(expected_size) is not int or not 0 < expected_size <= _MAX_FILE_BYTES):
        raise SourcePreflightRefused("invalid_manifest_metadata")
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise SourcePreflightRefused("unsafe_source_path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise SourcePreflightRefused("source_missing_or_outside_private_root")
    if path.stat().st_size != expected_size:
        raise SourcePreflightRefused("source_byte_size_mismatch")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_hash:
        raise SourcePreflightRefused("source_sha256_mismatch")
    return path


def check_private_sources(manifest: dict, root: Path) -> dict:
    """Decode/hash each real input, with no mask-quality inference.

    The source hash from R2 custom metadata is a *claimed* source digest.
    This routine independently compares that claim against local raw bytes.
    """
    private_root = root.resolve(strict=True)
    if not private_root.is_dir():
        raise SourcePreflightRefused("private_root_not_directory")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise SourcePreflightRefused("unsupported_source_manifest")
    records = manifest.get("objects")
    if not isinstance(records, list) or not 1 <= len(records) <= _MAX_ITEMS:
        raise SourcePreflightRefused("invalid_object_count")

    seen: set[str] = set()
    decoded = []
    for index, item in enumerate(records, 1):
        if not isinstance(item, dict) or item.get("role") not in _ROLES:
            raise SourcePreflightRefused("invalid_source_role")
        name = item.get("path")
        if not isinstance(name, str) or name in seen:
            raise SourcePreflightRefused("duplicate_source_path")
        seen.add(name)
        file = _private_file(private_root, item)
        try:
            with Image.open(file) as image:
                if image.format != "WEBP":
                    raise SourcePreflightRefused("not_webp_source")
                if image.width * image.height > _MAX_PIXELS or min(image.size) < 16:
                    raise SourcePreflightRefused("unsupported_dimensions")
                if image.getexif().get(274, 1) != 1:
                    raise SourcePreflightRefused("orientation_normalization_required")
                if image.mode not in {"L", "RGB", "RGBA"}:
                    raise SourcePreflightRefused("unsupported_color_mode")
                # Force full decode; WEBP headers alone are insufficient evidence.
                image.load()
                decoded.append({
                    "ordinal": index,
                    "role": item["role"],
                    "sha256": item["sha256"],
                    "byte_size": item["size"],
                    "width": image.width,
                    "height": image.height,
                    "mode": image.mode,
                    "embedded_alpha": "A" in image.getbands(),
                    "reference_alpha_present": False,
                    "segmentation_quality_assessed": False,
                })
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise SourcePreflightRefused("source_image_decode_failed") from exc

    roles = {role: sum(x["role"] == role for x in decoded) for role in sorted(_ROLES)}
    return {
        "schema_version": 1,
        "kind": "private_source_preflight",
        "source_only": True,
        "rights_basis": "owner_authorized_for_testing_not_redistribution",
        "local_byte_hashes_verified": True,
        "decoded_source_count": len(decoded),
        "roles": roles,
        "ground_truth_masks_supplied": 0,
        "mask_iou_calculated": False,
        "image_bytes_exported": False,
        "provider_requests": 0,
        "paid_usd": 0,
        "items": decoded,
    }


def run(manifest: Path, root: Path, output: Path) -> dict:
    """Read a local manifest and publish text-only report outside the data root."""
    with manifest.open("r", encoding="utf-8") as stream:
        spec = json.load(stream)
    result = check_private_sources(spec, root)
    target = output.resolve()
    if (target.is_relative_to(root.resolve())
            or target == manifest.resolve()):
        raise SourcePreflightRefused("report_overlaps_private_inputs")
    from .artifacts import atomic_text
    atomic_text(output, json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result
