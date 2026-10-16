"""Verified, *non-executing* affine transform contract for image comparisons.

Version 2 records an operator-authored invertible mapping, SHA256-bound image
provenance and conservative continuous sampling-region intersection. This module
DOES NOT resample, warp, register, compare pixels or publish quality scores.
A downstream v2 executor must validate every sampled pixel again.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image

from .artifacts import ArtifactIntegrityError
from .tiled_alignment import MAX_FRAME_PIXELS, MIN_OVERLAP_FRACTION, _verified_pair

SCHEMA_VERSION = 2
MAX_CONTRACT_BYTES = 4096
MAX_OFFSET = 8192.0
MAX_COEFFICIENT = 8.0
MIN_DETERMINANT = 1.0 / 64
MAX_CONDITION = 128.0
FRAME = "raw_unrotated_pixel_centers_origin_zero_exif_orientation_1"
INTERPOLATION = "bilinear_premultiplied_rgba"
BOUNDARY = "only_full_source_sampling_footprint"
PROFILE = "identical_icc_bytes_or_both_untagged_encoded_channels"
ALPHA = "premultiplied_rgba"
ATTESTATION = "operator_asserted_not_inferred"
_KEYS = frozenset({
    "schema_version", "kind", "reference_sha256", "candidate_sha256",
    "reference_to_candidate", "candidate_to_reference",
    "coordinate_frame", "interpolation", "boundary", "color_profile_policy",
    "alpha_policy", "attestation",
})


def _finite_float(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Affine matrix contains non-finite or non-numeric value")
    return float(value)


def _matrix(value: object) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    if (not isinstance(value, list) or len(value) != 2
            or any(not isinstance(row, list) or len(row) != 3 for row in value)):
        raise ValueError("Affine matrix must be a 2 by 3 numeric array")
    result = tuple(tuple(_finite_float(v) for v in row) for row in value)
    for row in result:
        if any(abs(v) > MAX_COEFFICIENT for v in row[:2]) or abs(row[2]) > MAX_OFFSET:
            raise ValueError("Affine coefficients exceed bounded range")
    return result  # type: ignore[return-value]


def _inverse(m: tuple[tuple[float, float, float],
                      tuple[float, float, float]]) -> tuple[
                          tuple[float, float, float],
                          tuple[float, float, float]]:
    (a, b, tx), (c, d, ty) = m
    det = a * d - b * c
    if abs(det) < MIN_DETERMINANT:
        raise ValueError("Singular or near-singular affine matrix")
    inv = ((d / det, -b / det, (b * ty - d * tx) / det),
           (-c / det, a / det, (c * tx - a * ty) / det))
    # Matrix 2-norm bound via Frobenius norm; conservative but deterministic.
    norm = math.hypot(a, b, c, d)
    inv_norm = math.hypot(inv[0][0], inv[0][1], inv[1][0], inv[1][1])
    if norm * inv_norm > MAX_CONDITION:
        raise ValueError("Affine transform is numerically ill-conditioned")
    return inv


def _apply(m: tuple, x: float, y: float) -> tuple[float, float]:
    return (m[0][0] * x + m[0][1] * y + m[0][2],
            m[1][0] * x + m[1][1] * y + m[1][2])


def _clip(polygon: list[tuple[float, float]], axis: int, edge: float,
          keep_above: bool) -> list[tuple[float, float]]:
    if not polygon:
        return []
    def inside(p: tuple[float, float]) -> bool:
        return p[axis] >= edge if keep_above else p[axis] <= edge

    output: list[tuple[float, float]] = []
    previous = polygon[-1]
    was_inside = inside(previous)
    for point in polygon:
        is_inside = inside(point)
        if is_inside != was_inside:
            denom = point[axis] - previous[axis]
            t = (edge - previous[axis]) / denom
            output.append((previous[0] + t * (point[0] - previous[0]),
                           previous[1] + t * (point[1] - previous[1])))
        if is_inside:
            output.append(point)
        previous, was_inside = point, is_inside
    return output


def _overlap_polygon(width: int, height: int, candidate_width: int,
                     candidate_height: int, inverse: tuple) -> tuple[
                         list[tuple[float, float]], float]:
    """Continuous center-coordinate overlap, NOT count of sampled pixels."""
    if min(width, height, candidate_width, candidate_height) < 2:
        raise ValueError("Affine sampling requires both image axes >= 2 pixels")
    # Full bilinear footprint requires candidate center coordinates in
    # [0, width-1] x [0, height-1]. Ref sampling centers use same convention.
    corners = [(0.0, 0.0), (candidate_width - 1.0, 0.0),
               (candidate_width - 1.0, candidate_height - 1.0),
               (0.0, candidate_height - 1.0)]
    polygon = [_apply(inverse, *p) for p in corners]
    for axis, edge, above in (
        (0, 0.0, True), (0, width - 1.0, False),
        (1, 0.0, True), (1, height - 1.0, False),
    ):
        polygon = _clip(polygon, axis, edge, above)
        if not polygon:
            return [], 0.0
    twice = abs(sum(
        polygon[i][0] * polygon[(i + 1) % len(polygon)][1]
        - polygon[(i + 1) % len(polygon)][0] * polygon[i][1]
        for i in range(len(polygon))
    ))
    area = twice / 2.0
    fraction = min(1.0, area / ((width - 1.0) * (height - 1.0)))
    return polygon, fraction


def validate_affine_record(raw: bytes, reference_sha: str, candidate_sha: str,
                           reference_size: tuple[int, int],
                           candidate_size: tuple[int, int]) -> dict:
    """Pure validation; never decode or resample pixels and never write files."""
    if not isinstance(raw, bytes) or len(raw) > MAX_CONTRACT_BYTES:
        raise ValueError("Alignment record exceeds 4 KiB or is not bytes")
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid JSON affine contract") from exc
    if not isinstance(record, dict) or set(record) != _KEYS:
        raise ValueError("Missing or unsupported affine contract fields")
    required = {
        "schema_version": SCHEMA_VERSION, "kind": "affine_2d",
        "coordinate_frame": FRAME, "interpolation": INTERPOLATION,
        "boundary": BOUNDARY, "color_profile_policy": PROFILE,
        "alpha_policy": ALPHA, "attestation": ATTESTATION,
    }
    for key, expectation in required.items():
        if type(record[key]) is not type(expectation) or record[key] != expectation:
            raise ValueError("Unsupported affine schema or operator contract")
    if (record["reference_sha256"] != reference_sha
            or record["candidate_sha256"] != candidate_sha
            or any(not isinstance(s, str) or len(s) != 64
                   or any(c not in "0123456789abcdef" for c in s)
                   for s in (reference_sha, candidate_sha))):
        raise ArtifactIntegrityError("Affine image digests do not match")
    forward = _matrix(record["reference_to_candidate"])
    declared_inverse = _matrix(record["candidate_to_reference"])
    calculated_inverse = _inverse(forward)
    # Affine translation values may be large: inverse check uses a scale-aware
    # tolerance, while rejecting incompatible inverses and NaN/singular data.
    for row in range(2):
        for col in range(3):
            if not math.isclose(calculated_inverse[row][col],
                                declared_inverse[row][col], rel_tol=1e-8,
                                abs_tol=1e-7):
                raise ValueError("Declared affine inverse is inconsistent")
    if (type(reference_size) is not tuple or type(candidate_size) is not tuple
            or any(type(v) is not int or v < 2 or v > 24_000
                   for v in (*reference_size, *candidate_size))
            or reference_size[0] * reference_size[1] > MAX_FRAME_PIXELS
            or candidate_size[0] * candidate_size[1] > MAX_FRAME_PIXELS):
        raise ValueError("Invalid or oversized source geometry")
    polygon, fraction = _overlap_polygon(
        *reference_size, *candidate_size, declared_inverse)
    if fraction < MIN_OVERLAP_FRACTION:
        raise ValueError("Insufficient continuous affine overlap")
    return {
        "schema_version": SCHEMA_VERSION,
        "validation": "operator_affine_contract_only_not_pixel_comparison",
        "record_sha256": hashlib.sha256(raw).hexdigest(),
        "reference_sha256": reference_sha,
        "candidate_sha256": candidate_sha,
        "reference_dimensions": list(reference_size),
        "candidate_dimensions": list(candidate_size),
        "reference_to_candidate": [list(row) for row in forward],
        "candidate_to_reference": [list(row) for row in declared_inverse],
        "continuous_center_domain_overlap_fraction": round(fraction, 8),
        "continuous_center_domain_overlap_polygon": [
            [round(x, 6), round(y, 6)] for x, y in polygon
        ],
        "valid_discrete_sample_count": None,
        "interpolation_executed": False,
        "pixel_difference_metrics": None,
        "operator_attestation_not_verified": True,
        "human_visual_quality_score": None,
    }


def validate_affine_for_slot(journal, asset_id: str, *,
                             alignment: Path,
                             inputs: Path | None = None,
                             cutout: str | None = None) -> dict:
    """Bind affine contract to verified recorded inputs without doing any warp."""
    from .images import sha256
    ref, reference_sha, cand, candidate_sha, kind = _verified_pair(
        journal, asset_id, inputs, cutout)
    path = Path(alignment)
    if path.stat().st_size > MAX_CONTRACT_BYTES:
        raise ValueError("Alignment record exceeds 4 KiB")
    payload = path.read_bytes()
    with Image.open(ref) as a, Image.open(cand) as b:
        for image in (a, b):
            if image.width * image.height > MAX_FRAME_PIXELS:
                raise ValueError("Image exceeds 24 MP")
            if image.getexif().get(274, 1) not in (None, 1):
                raise ValueError("orientation_unresolved")
            if image.mode not in ("RGB", "RGBA"):
                raise ValueError("pixel_encoding_unsupported")
        if a.info.get("icc_profile") != b.info.get("icc_profile"):
            raise ValueError("color_profile_mismatch")
        reference_size, candidate_size = a.size, b.size
    result = validate_affine_record(
        payload, reference_sha, candidate_sha, reference_size, candidate_size)
    if sha256(ref) != reference_sha or sha256(cand) != candidate_sha:
        raise ArtifactIntegrityError("Image changed during affine verification")
    result["comparison"] = kind
    return result
