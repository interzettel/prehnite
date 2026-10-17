"""Private, offline evidence receipt for a real image and cutout candidate.

No claim of human visual acceptance, model rights, timing accuracy or GPU tier
is inferred from technically valid pixels. No file bytes are uploaded.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .artifacts import atomic_text
from .hardware import hardware_report
from .schema import relative_name


MAX_PIXELS = 24_000_000
MAX_BYTES = 100_000_000


def _verified_file(root: Path, name: str) -> Path:
    if relative_name(name) != name:
        raise ValueError("Trial output path must be canonical and relative")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Output root must be a real directory")
    path = root
    for part in name.split("/"):
        path = path / part
        if path.is_symlink():
            raise ValueError("Trial output must not be a symlink")
    base = root.resolve(strict=True)
    target = path.resolve(strict=True)
    if not target.is_relative_to(base) or not target.is_file():
        raise ValueError("Trial output is outside approved root")
    size = target.stat().st_size
    if not (0 < size <= MAX_BYTES):
        raise ValueError("Trial output is empty or exceeds allowed size")
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _image(path: Path, *, cutout: bool) -> dict:
    try:
        with Image.open(path) as img:
            if img.format not in ("PNG", "JPEG", "WEBP"):
                raise ValueError("Unsupported generated image encoding")
            width, height = img.size
            if min(width, height) < 64 or width * height > MAX_PIXELS:
                raise ValueError("Invalid or oversized image dimensions")
            if img.getexif().get(274, 1) != 1:
                raise ValueError("EXIF-rotated images require normalization first")
            if cutout and (img.format != "PNG" or img.mode != "RGBA"):
                raise ValueError("Cutout must be RGBA PNG, not an opaque/mask-only image")
            img.load()
            result = {"format": img.format, "mode": img.mode,
                      "width": width, "height": height}
            if cutout:
                alpha = img.getchannel("A")
                low, high = alpha.getextrema()
                if low != 0 or high <= 0:
                    raise ValueError("Cutout needs both transparent and nontransparent pixels")
                result["alpha_min"] = low
                result["alpha_max"] = high
                result["alpha_geometry_verified"] = True
            return result
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValueError("Could not decode trial image") from exc


def evidence_receipt(
    *,
    root: Path,
    generated: str,
    cutout: str,
    output: Path,
    elapsed_seconds: float | None = None,
    peak_vram_mib: float | None = None,
    measurement_method: str | None = None,
    human_review: str = "unreviewed",
) -> dict:
    """Create-only receipt stored OUTSIDE the image root, without output mutation."""
    if human_review not in ("unreviewed", "accepted", "rejected"):
        raise ValueError("Human review must be unreviewed, accepted or rejected")
    if (elapsed_seconds is not None or peak_vram_mib is not None):
        if (not isinstance(measurement_method, str) or
                not measurement_method.strip() or len(measurement_method) > 200):
            raise ValueError("Measured values require a named method and observation window")
    if measurement_method and not (elapsed_seconds is not None or peak_vram_mib is not None):
        raise ValueError("Measurement method supplied without any measurements")
    for value in (elapsed_seconds, peak_vram_mib):
        if value is not None and (not math.isfinite(value) or value <= 0):
            raise ValueError("Timing and VRAM values must be finite positive observations")
    if generated == cutout:
        raise ValueError("Generated and cutout outputs must be distinct files")
    original = _verified_file(root, generated)
    transparent = _verified_file(root, cutout)
    input_image, cutout_image = _image(original, cutout=False), _image(transparent, cutout=True)
    if (input_image["width"], input_image["height"]) != (
            cutout_image["width"], cutout_image["height"]):
        raise ValueError("Cutout and generated image geometries differ")
    # Avoid changing either image; root is part of the private user workspace.
    target = output.resolve(strict=False)
    directory = root.resolve(strict=True)
    if target.is_relative_to(directory) or target in (original, transparent):
        raise ValueError("Evidence report must be outside approved source image root")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Evidence receipt already exists; will not overwrite")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError("Receipt parent must be a real existing directory")
    receipt = {
        "schema_version": 1, "status": "technical_evidence_not_quality_certification",
        "assets": {
            "generated": {"filename": generated, "sha256": _sha256(original),
                          "bytes": original.stat().st_size, "image": input_image},
            "cutout": {"filename": cutout, "sha256": _sha256(transparent),
                       "bytes": transparent.stat().st_size, "image": cutout_image},
        },
        "geometry_match": True,
        "alpha_has_transparency_and_content": True,
        "human_review": human_review,
        "human_review_independently_verified": False,
        "model_rights_verified": False,
        "provider_billing_verified": False,
        "quality_scores": "not_measured_without_reviewed_alpha_reference",
        "hardware_observation": hardware_report(),
        "operator_measurements": {
            "elapsed_seconds": elapsed_seconds, "peak_vram_mib": peak_vram_mib,
            "measurement_method": measurement_method,
            "status": "owner_supplied_unverified" if measurement_method else "not_provided",
        },
        "network_or_model_calls": 0, "amount_spent_usd": 0,
        "note": "Receipt only. Run a separately human-reviewed alpha quality benchmark.",
    }
    # Exclusive creation, never silently overwrite a prior acceptance record.
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return receipt
