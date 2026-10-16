"""Pixel-true visual detail evidence, generated offline from owned images.

Each crop preserves original pixels. The annotated overview is intentionally
downsampled for navigation and MUST NOT be used to judge fine image detail.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from .artifacts import atomic_text, temporary_sibling
from .images import image_info, sha256

SCHEMA_VERSION = 1
STANDARD_CROPS = ("top-left", "top-right", "center", "bottom-left", "bottom-right")


def _position(width: int, height: int, edge: int, x: float, y: float) -> tuple[int, int, int, int]:
    # An anchor is a normalized source-image point, never a bounding-box guess.
    left = min(max(round(x * width - edge / 2), 0), width - edge)
    top = min(max(round(y * height - edge / 2), 0), height - edge)
    return (left, top, left + edge, top + edge)


def _anchor(anchor: tuple[float, float] | None) -> tuple[float, float] | None:
    if anchor is None:
        return None
    if len(anchor) != 2 or any(
        isinstance(v, bool) or not isinstance(v, (int, float))
        or not math.isfinite(v) or v < 0 or v > 1 for v in anchor
    ):
        raise ValueError("Anchor coordinates must be finite normalized numbers from 0 to 1")
    return (float(anchor[0]), float(anchor[1]))


def _write_png(image: Image.Image, path: Path) -> dict:
    with temporary_sibling(path) as temp:
        image.save(temp, format="PNG", optimize=False)
        info = image_info(temp)
        # Do not publish a partial image if encoding/decoding fails.
        os.replace(temp, path)
    return info


def make_detail_crops(
    source: Path,
    destination: Path,
    *,
    edge: int = 768,
    anchor: tuple[float, float] | None = None,
) -> dict:
    """Write native 1:1 crops, navigation overview and versioned evidence JSON.

    The optional anchor is given explicitly by a human/user agent; Prehnite
    does not automatically detect the subject or imply that a visual model
    has verified it. Pixel coordinates use an EXIF-transposed source frame.
    """
    if isinstance(edge, bool) or not isinstance(edge, int) or not 128 <= edge <= 2048:
        raise ValueError("Crop edge must be an integer between 128 and 2048 pixels")
    anchor = _anchor(anchor)
    source = Path(source)
    destination = Path(destination)
    if not source.is_file():
        raise FileNotFoundError(source)
    targets = list(STANDARD_CROPS) + (["anchor"] if anchor else [])
    # No generated output may silently overwrite the original image.
    if source.resolve() in {
        (destination / name).resolve() for name in
        ([f"{label}.png" for label in targets] + ["overview.png", "crops.json"])
    }:
        raise ValueError("Evidence output would replace the source image")

    source_digest = sha256(source)
    with Image.open(source) as original:
        oriented = ImageOps.exif_transpose(original)
        oriented.load()
        width, height = oriented.size
        if width * height > 24_000_000:
            raise ValueError("Image exceeds the 24 MP inspection limit")
        if min(width, height) < edge:
            raise ValueError("Crop edge exceeds source image short side; no upscaling allowed")
        boxes = {
            "top-left": (0, 0, edge, edge),
            "top-right": (width - edge, 0, width, edge),
            "center": _position(width, height, edge, 0.5, 0.5),
            "bottom-left": (0, height - edge, edge, height),
            "bottom-right": (width - edge, height - edge, width, height),
        }
        if anchor:
            boxes["anchor"] = _position(width, height, edge, *anchor)
        # Preserve 16-bit, alpha and source colors if Pillow can encode them
        # as PNG. Never JPEG-compress detailed evidence.
        crops = []
        for label, bounds in boxes.items():
            filename = f"{label}.png"
            info = _write_png(oriented.crop(bounds), destination / filename)
            crops.append({
                "label": label, "file": filename, "box_xyxy": list(bounds),
                "width": info["width"], "height": info["height"],
                "sha256": info["sha256"],
                "bytes": (destination / filename).stat().st_size,
            })

        # Only an overview: explicit resampling is fine here, not for crops.
        overview = oriented.convert("RGB").copy()
        overview.thumbnail((900, 900), Image.Resampling.LANCZOS)
        scale_x = overview.width / width
        scale_y = overview.height / height
        drawing = ImageDraw.Draw(overview)
        palette = ("#0c695e", "#d06d38", "#5b4cb3", "#7d551b", "#006e9b", "#ae314f")
        for i, (label, bounds) in enumerate(boxes.items()):
            x0, y0, x1, y1 = bounds
            rectangle = (round(x0 * scale_x), round(y0 * scale_y),
                         round(x1 * scale_x), round(y1 * scale_y))
            color = palette[i]
            drawing.rectangle(rectangle, outline=color, width=3)
            drawing.text((rectangle[0] + 3, rectangle[1] + 3), label,
                         fill=color, stroke_width=1, stroke_fill="white")
        overview_info = _write_png(overview, destination / "overview.png")

    data = {
        "schema_version": SCHEMA_VERSION,
        "source_sha256": source_digest,
        "source_width": width, "source_height": height,
        "coordinate_frame": "EXIF-transposed source pixels; xyxy, exclusive max",
        "crop_edge": edge,
        "anchor_xy_normalized": list(anchor) if anchor else None,
        "crops": crops,
        "overview": {
            "file": "overview.png", "sha256": overview_info["sha256"],
            "width": overview_info["width"], "height": overview_info["height"],
            "purpose": "navigation only; downsampled; not a native-detail crop",
        },
        "quality_judgment": "none; deterministic crops are evidence, not scores",
    }
    atomic_text(destination / "crops.json", json.dumps(data, indent=2) + "\n")
    return data


def verified_crop_paths(destination: Path, *, source: Path | None = None) -> dict[str, Path]:
    """Load reusable full-resolution PNG paths after checking their integrity.

    A future model judge can receive these paths directly, without mistaking
    downsampled overview.png for pixel-detail evidence. This verifies local
    integrity, not the authenticity of a user-editable manifest.
    """
    destination = Path(destination)
    record = json.loads((destination / "crops.json").read_text(encoding="utf-8"))
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported detail-evidence manifest version")
    if source is not None and sha256(Path(source)) != record.get("source_sha256"):
        raise ValueError("Source image changed since crop evidence was generated")
    entries = record.get("crops", [])
    allowed = set(STANDARD_CROPS) | {"anchor"}
    expected_count = 6 if record.get("anchor_xy_normalized") is not None else 5
    if not isinstance(entries, list) or len(entries) != expected_count:
        raise ValueError("Missing or duplicate crop evidence")
    results = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Malformed crop evidence")
        label = entry.get("label")
        if label not in allowed or label in results or entry.get("file") != f"{label}.png":
            raise ValueError("Unexpected crop evidence name")
        path = destination / f"{label}.png"
        info = image_info(path)
        if (info["sha256"] != entry.get("sha256")
                or info["width"] != record.get("crop_edge")
                or info["height"] != record.get("crop_edge")):
            raise ValueError(f"Corrupt crop evidence: {label}")
        results[label] = path
    return results
