"""Reference-alpha diagnostics for opt-in, offline S03-A04 experiments.

These metrics compare an RGBA candidate to independently supplied reference
RGBA. They do not manufacture ground truth, validate model provenance or
certify transparent material optics. Inputs use straight (unassociated) RGB.
"""
from __future__ import annotations

from PIL import Image, ImageChops, ImageFilter

MAX_MATTE_PIXELS = 12_000_000


class MatteEvidenceRefused(ValueError):
    """Reference geometry or alpha is inadequate for quantitative evaluation."""


def _background(size: tuple[int, int], kind: str) -> Image.Image:
    if kind == "black":
        return Image.new("RGBA", size, (0, 0, 0, 255))
    if kind == "white":
        return Image.new("RGBA", size, (255, 255, 255, 255))
    if kind != "checkerboard":
        raise MatteEvidenceRefused("unknown_background")
    width, height = size
    plate = Image.new("RGBA", size, (224, 224, 224, 255))
    pixels = plate.load()
    for y in range(height):
        for x in range(width):
            if (x // 8 + y // 8) % 2:
                pixels[x, y] = (48, 48, 48, 255)
    return plate


def _mean_channel_error(a: Image.Image, b: Image.Image, region: Image.Image) -> float:
    """Raw 0-255 RGB MAE inside a binary region, without visual-score inflation."""
    count = region.histogram()[255]
    if not count:
        raise MatteEvidenceRefused("empty_measurement_region")
    difference = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    mask = region.tobytes()
    packed = difference.tobytes()
    total = sum(packed[3 * i] + packed[3 * i + 1] + packed[3 * i + 2]
                for i, selected in enumerate(mask) if selected == 255)
    return round(total / (3 * count), 6)


def evaluate_reference_matte(candidate: Image.Image, reference: Image.Image) -> dict:
    """Report alpha error and three-background compositing error against a real reference.

    The reference is required to be independent of the candidate. The caller
    is responsible for declaring whether it is synthetic oracle data or
    independently annotated licensed photography; this function cannot tell.
    A '0' means pixel equality to *that reference*, not photo realism.
    """
    if candidate.mode != "RGBA" or reference.mode != "RGBA":
        raise MatteEvidenceRefused("straight_rgba_inputs_required")
    if candidate.size != reference.size or not 8 <= candidate.width or not 8 <= candidate.height:
        raise MatteEvidenceRefused("reference_geometry_mismatch")
    if candidate.width * candidate.height > MAX_MATTE_PIXELS:
        raise MatteEvidenceRefused("reference_image_too_large")
    reference_alpha = reference.getchannel("A")
    candidate_alpha = candidate.getchannel("A")
    oracle_partial = reference_alpha.point(lambda x: 255 if 0 < x < 255 else 0)
    if not oracle_partial.getbbox():
        raise MatteEvidenceRefused("reference_has_no_fractional_alpha")
    candidate_partial = candidate_alpha.point(lambda x: 255 if 0 < x < 255 else 0)
    # Include newly introduced partial pixels as well as a one-pixel band around
    # each oracle/candidate transition. Detect halos both inside and outside truth.
    union = ImageChops.lighter(oracle_partial, candidate_partial)
    boundary = union.filter(ImageFilter.MaxFilter(size=3))
    a = candidate_alpha.tobytes()
    b = reference_alpha.tobytes()
    partial_bytes = oracle_partial.tobytes()
    alpha_mae = sum(abs(x - y) for x, y in zip(a, b)) / len(a)
    partial_count = sum(1 for x in partial_bytes if x)
    edge_alpha_mae = sum(abs(x - y) for x, y, selected in zip(a, b, partial_bytes)
                         if selected) / partial_count
    errors = {}
    for kind in ("black", "white", "checkerboard"):
        plate = _background(candidate.size, kind)
        observed = Image.alpha_composite(plate, candidate)
        expected = Image.alpha_composite(plate, reference)
        errors[kind] = _mean_channel_error(observed, expected, boundary)
    return {
        "alpha_mae_255": round(alpha_mae, 6),
        "oracle_fractional_alpha_mae_255": round(edge_alpha_mae, 6),
        "oracle_fractional_pixels": partial_count,
        "transition_band_pixels": boundary.histogram()[255],
        "composited_transition_rgb_mae_255": errors,
        "max_composited_transition_rgb_mae_255": max(errors.values()),
        "measurement_type": "reference_raster_technical_only",
        "human_visual_acceptance": "not_recorded",
    }
