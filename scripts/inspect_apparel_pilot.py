"""Local-only, read-only QA of an owner-supplied apparel photo ZIP.

JPEG inventory needs Pillow only. Optional OpenCV GrabCut is exploratory, never
an independently validated matte, and needs explicit --unreviewed-grabcut.
Nothing is uploaded, accepted for production, or saved in the source archive.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

_MAX_FILES = 200
_MAX_BYTES = 400 * 1024 * 1024
_MAX_IMAGE = 25 * 1024 * 1024
_MAX_PIXELS = 24_000_000
_PATTERN = re.compile(r"^(?:[^/]+/)?(WH-S[0-9]{3})/(front|care_label)\.jpg$")


class PilotRefused(ValueError):
    """An untrusted ZIP or output contract is unsafe or ambiguous."""


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def inventory(source: Path) -> tuple[dict, list[tuple[str, str, bytes]]]:
    """Fully decode without extracting untrusted members to the filesystem."""
    with zipfile.ZipFile(source) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if not 1 <= len(members) <= _MAX_FILES:
            raise PilotRefused("unsupported_archive_count")
        if sum(item.file_size for item in members) > _MAX_BYTES:
            raise PilotRefused("archive_expansion_limit")
        seen: set[tuple[str, str]] = set()
        inspected = []
        rows = []
        for entry in members:
            # Validate the literal ZIP member path, not merely the shape
            # of its final components. A prefix of ".." previously matched
            # the optional top-level folder even though no extraction occurs.
            parts = entry.filename.split("/")
            if (entry.filename.startswith("/") or chr(92) in entry.filename
                    or any(part in ("", ".", "..") for part in parts)):
                raise PilotRefused("unexpected_or_encrypted_member")
            match = _PATTERN.fullmatch(entry.filename)
            if (not match or entry.flag_bits & 1 or entry.file_size < 1
                    or entry.file_size > _MAX_IMAGE):
                raise PilotRefused("unexpected_or_encrypted_member")
            key = (match.group(1), match.group(2))
            if key in seen:
                raise PilotRefused("duplicate_product_role")
            seen.add(key)
            content = archive.read(entry)
            if len(content) != entry.file_size:
                raise PilotRefused("archive_byte_length_mismatch")
            try:
                with Image.open(io.BytesIO(content)) as image:
                    if image.format != "JPEG" or image.mode != "RGB":
                        raise PilotRefused("unsupported_image_format")
                    if (image.width * image.height > _MAX_PIXELS
                            or min(image.size) < 16):
                        raise PilotRefused("unsupported_dimensions")
                    if image.getexif().get(274, 1) != 1:
                        raise PilotRefused("exif_normalization_required")
                    image.load()
                    size = image.size
            except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
                raise PilotRefused("image_decode_failed") from exc
            rows.append({
                "product_id": key[0], "role": key[1],
                "sha256": _digest(content), "byte_size": len(content),
                "dimensions": list(size), "reference_alpha_present": False,
            })
            inspected.append((key[0], key[1], content))
    rows.sort(key=lambda row: (row["product_id"], row["role"]))
    inspected.sort(key=lambda item: (item[0], item[1]))
    counts = {
        role: sum(row["role"] == role for row in rows)
        for role in ("front", "care_label")
    }
    report = {
        "schema_version": 1,
        "kind": "private_owner_photo_archive",
        "original_zip_sha256": _digest(source.read_bytes()),
        "file_count": len(rows),
        "roles": counts,
        "reference_alpha_count": 0,
        "mask_iou_available": False,
        "image_bytes_published": False,
        "paid_provider_calls": 0,
        "sources": rows,
    }
    return report, inspected


def _grabcut(content: bytes) -> tuple[Image.Image, Image.Image]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise PilotRefused("optional_opencv_numpy_not_installed") from exc
    with Image.open(io.BytesIO(content)) as opened:
        image = opened.convert("RGB")
    image.thumbnail((360, 480))
    pixels = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    mask = np.zeros(pixels.shape[:2], np.uint8)
    bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    rect = (round(image.width * .045), round(image.height * .035),
            round(image.width * .91), round(image.height * .93))
    try:
        cv2.grabCut(pixels, mask, rect, bg, fg, 4, cv2.GC_INIT_WITH_RECT)
    except cv2.error as exc:
        raise PilotRefused("baseline_segmentation_failed") from exc
    alpha = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype("uint8") * 255
    return image, Image.fromarray(alpha, mode="L")


def _preview(image: Image.Image, alpha: Image.Image) -> Image.Image:
    backdrop = Image.new("RGB", image.size, "#f4f0e8")
    draw = ImageDraw.Draw(backdrop)
    for y in range(0, backdrop.height, 16):
        for x in range(0, backdrop.width, 16):
            if x // 16 % 2 != y // 16 % 2:
                draw.rectangle((x, y, x + 15, y + 15), fill="#d2d9d2")
    backdrop.paste(image, (0, 0), mask=alpha)
    panel = Image.new("RGB", (image.width * 2, image.height))
    panel.paste(image, (0, 0))
    panel.paste(backdrop, (image.width, 0))
    return panel


def run(zip_path: Path, output_dir: Path, *, unreviewed_grabcut: bool = False) -> dict:
    """Never writes over the input ZIP or existing outputs; output is private."""
    if not zip_path.is_file():
        raise PilotRefused("missing_zip")
    destination = output_dir.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise PilotRefused("destination_must_be_empty")
    if destination == zip_path.resolve() or destination == zip_path.resolve().parent:
        raise PilotRefused("unsafe_destination")
    report, inputs = inventory(zip_path)
    report["candidates_generated"] = 0
    report["human_accepted"] = 0
    report["actual_segmentation_iou"] = None
    report["baseline"] = "none"
    candidates: list[tuple[str, Image.Image, Image.Image]] = []
    if unreviewed_grabcut:
        report["baseline"] = "opencv_grabcut_rectangle_4_iterations_downsampled"
        for product, role, content in inputs:
            if role != "front":
                continue
            im, alpha = _grabcut(content)
            candidates.append((product, alpha, _preview(im, alpha)))
        report["candidates_generated"] = len(candidates)
    destination.mkdir(parents=True, exist_ok=True)
    if candidates:
        masks = destination / "unreviewed_masks"
        previews = destination / "unreviewed_previews"
        masks.mkdir()
        previews.mkdir()
        for product, alpha, comparison in candidates:
            alpha.save(masks / f"{product}.png")
            comparison.save(previews / f"{product}.jpg", quality=85)
    (destination / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unreviewed-grabcut", action="store_true",
                        help="Explicitly generate non-production masks (requires optional OpenCV)")
    args = parser.parse_args()
    result = run(args.zip_path, args.output, unreviewed_grabcut=args.unreviewed_grabcut)
    print(json.dumps({
        "file_count": result["file_count"], "roles": result["roles"],
        "candidates_generated": result["candidates_generated"],
        "mask_iou_available": result["mask_iou_available"],
        "human_accepted": result["human_accepted"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
