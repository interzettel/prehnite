"""SHA-bound operator-attested integer translations and tiled 4K+ diagnostics.

This first alignment contract supports exact integer translations only.
It does NOT detect alignment, estimate a transform, interpolate, rescale,
crop to fit, or produce a human-calibrated visual-quality score.

Tile buffers stay bounded; Pillow's codec may still materialize image frames
internally. The 24 MP cap bounds that decoder exposure.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from .artifacts import ArtifactIntegrityError, atomic_text, temporary_sibling, verified_image
from .images import sha256
from .manifest import resolve_input
from .pixel_comparison import _selected
from .schema import Asset, relative_name
from .store import Journal

SCHEMA_VERSION = 1
MAX_FRAME_PIXELS = 24_000_000
TILE_WIDTH = 512
TILE_HEIGHT = 128
MIN_OVERLAP_FRACTION = 0.10
_VALID_SHA = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_KEYS = frozenset({
    "schema_version", "kind", "dx_pixels", "dy_pixels",
    "reference_sha256", "candidate_sha256",
    "coordinate_frame", "interpolation", "attestation",
})
_FRAME = "raw_unrotated_encoded_pixels_exif_orientation_1"


def read_translation(path: Path, ref_sha: str, cand_sha: str) -> tuple[int, int, str]:
    """Parse an operator-authored fixed contract; never accept freeform instructions."""
    raw = Path(path).read_bytes()
    if len(raw) > 4096:
        raise ValueError("Alignment record exceeds 4 KiB")
    try:
        record = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid JSON alignment record") from exc
    if not isinstance(record, dict) or set(record) != _ALLOWED_KEYS:
        raise ValueError("Alignment record contains missing or unsupported fields")
    if (type(record["schema_version"]) is not int or record["schema_version"] != SCHEMA_VERSION
            or record["kind"] != "integer_translation"
            or record["coordinate_frame"] != _FRAME
            or record["interpolation"] != "none"
            or record["attestation"] != "operator_asserted_not_inferred"):
        raise ValueError("Unsupported alignment contract; no inferred registration")
    dx, dy = record["dx_pixels"], record["dy_pixels"]
    if (type(dx) is not int or type(dy) is not int
            or abs(dx) > 8192 or abs(dy) > 8192):
        raise ValueError("Translation must contain bounded integer pixel offsets")
    if (record["reference_sha256"] != ref_sha
            or record["candidate_sha256"] != cand_sha
            or not all(isinstance(s, str) and _VALID_SHA.fullmatch(s)
                       for s in (ref_sha, cand_sha))):
        raise ArtifactIntegrityError("Alignment record image hashes do not match")
    return dx, dy, hashlib.sha256(raw).hexdigest()


def _png_chunk(file, tag: bytes, body: bytes) -> None:
    file.write(struct.pack(">I", len(body)))
    file.write(tag)
    file.write(body)
    file.write(struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))


def _compose(tile: Image.Image, shade: int) -> Image.Image:
    rgba = tile.convert("RGBA")
    ground = Image.new("RGBA", tile.size, (shade, shade, shade, 255))
    return Image.alpha_composite(ground, rgba).convert("RGB")


def _inspect_pair(a: Image.Image, b: Image.Image) -> tuple[int, int]:
    for img in (a, b):
        if img.width * img.height > MAX_FRAME_PIXELS:
            raise ValueError("Image exceeds 24 MP comparison cap")
        if img.getexif().get(274, 1) not in (None, 1):
            raise ValueError("orientation_unresolved")
        if img.mode not in ("RGB", "RGBA"):
            raise ValueError("pixel_encoding_unsupported")
    if a.info.get("icc_profile") != b.info.get("icc_profile"):
        raise ValueError("color_profile_mismatch")
    return a.width * a.height, b.width * b.height


def _verified_pair(journal: Journal, asset_id: str, inputs: Path | None,
                   cutout: str | None) -> tuple[Path, str, Path, str, str]:
    Asset.check_id(asset_id)
    if (inputs is None) == (cutout is None):
        raise ValueError("Exactly one of --inputs and --cutout is required")
    results = journal.fact("results", {})
    result = results.get(asset_id) if isinstance(results, dict) else None
    if not isinstance(result, dict) or result.get("status") not in ("accepted", "failed_cutouts"):
        raise ValueError("Comparison requires an accepted base image")
    outputs = result.get("outputs")
    checksums = result.get("outputs_sha256")
    if not isinstance(outputs, list) or not outputs or not isinstance(checksums, dict):
        raise ArtifactIntegrityError("Missing selected output integrity evidence")
    manifest = journal.fact("manifest", {})
    assets = manifest.get("assets", []) if isinstance(manifest, dict) else []
    asset = next((row for row in assets
                  if isinstance(row, dict) and row.get("id") == asset_id), None)
    if asset is None or not isinstance(asset.get("output"), dict):
        raise ValueError("Asset is absent from the recorded manifest")
    if asset["output"].get("image") != outputs[0]:
        raise ArtifactIntegrityError("Selected base does not match the manifest")
    base, base_sha = _selected(journal.root, outputs[0], checksums)
    if inputs is not None:
        source = asset.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError("Prompt-generated asset has no historical source")
        hashes = journal.fact("input_file_sha256")
        previous = hashes.get(asset_id) if isinstance(hashes, dict) else None
        if not isinstance(previous, str) or not _VALID_SHA.fullmatch(previous):
            raise ArtifactIntegrityError("No saved historical original SHA256")
        ref = resolve_input(Path(inputs), relative_name(source))
        verified_image(ref, previous)
        return ref, previous, base, base_sha, "original_vs_base"
    named = asset["output"].get("cutouts", {})
    if (not isinstance(cutout, str) or not cutout.isidentifier()
            or not isinstance(named, dict) or cutout not in named
            or named[cutout] not in outputs[1:]):
        raise ValueError("Requested cutout was not accepted for this slot")
    candidate, candidate_sha = _selected(journal.root, named[cutout], checksums)
    return base, base_sha, candidate, candidate_sha, "base_vs_cutout"


def compare_registered_tiles(
    journal: Journal, asset_id: str, *,
    alignment: Path,
    inputs: Path | None = None, cutout: str | None = None,
) -> dict:
    """Compute an overlap-only delta without constructing full RGBA diff arrays.

    Reference-to-candidate mapping: candidate(x + dx, y + dy) = reference(x, y).
    Pixels outside overlap are *not compared*; PNG alpha is 0 there. This is
    entirely different from counting invalid margins as visual failures.
    """
    ref, ref_sha, candidate, cand_sha, kind = _verified_pair(
        journal, asset_id, inputs, cutout)
    dx, dy, record_sha = read_translation(alignment, ref_sha, cand_sha)
    with Image.open(ref) as first, Image.open(candidate) as second:
        ref_total, candidate_total = _inspect_pair(first, second)
        width, height = first.size
        cand_w, cand_h = second.size
        left, top = max(0, -dx), max(0, -dy)
        right, bottom = min(width, cand_w - dx), min(height, cand_h - dy)
        valid_count = max(0, right - left) * max(0, bottom - top)
        if not valid_count or valid_count / ref_total < MIN_OVERLAP_FRACTION:
            raise ValueError("Insufficient registered overlap for a truthful comparison")
        # Pixel buffers: one 512x128 work tile and one reference-width 128-row
        # scanline strip. No full-image alpha/diff/heatmap raster in Python.
        changed = partial_ref = partial_cand = transparent_ref = transparent_cand = 0
        delta_sum = 0.0
        root = journal.root / "reviews"
        if not root.resolve().is_relative_to(journal.root.resolve()):
            raise ArtifactIntegrityError("Review destination escapes batch root")
        suffix = "original" if inputs is not None else "cutout"
        name = f"{asset_id}-registered-{suffix}"
        target = root / (name + ".png")
        with temporary_sibling(target) as staged:
            with staged.open("wb") as writer:
                writer.write(b"\x89PNG\r\n\x1a\n")
                _png_chunk(writer, b"IHDR", struct.pack(
                    ">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                compressor = zlib.compressobj(level=6)
                for strip_y in range(0, height, TILE_HEIGHT):
                    strip_bottom = min(height, strip_y + TILE_HEIGHT)
                    raster = Image.new("RGBA", (width, strip_bottom - strip_y),
                                       (0, 0, 0, 0))
                    y0, y1 = max(strip_y, top), min(strip_bottom, bottom)
                    if y0 < y1:
                        for x0 in range(left, right, TILE_WIDTH):
                            x1 = min(right, x0 + TILE_WIDTH)
                            a = first.crop((x0, y0, x1, y1)).convert("RGBA")
                            b = second.crop((x0 + dx, y0 + dy,
                                             x1 + dx, y1 + dy)).convert("RGBA")
                            black = ImageChops.difference(_compose(a, 0),
                                                          _compose(b, 0))
                            white = ImageChops.difference(_compose(a, 255),
                                                          _compose(b, 255))
                            delta_sum += sum(ImageStat.Stat(black).sum)
                            delta_sum += sum(ImageStat.Stat(white).sum)
                            maximum = ImageChops.lighter(black, white)
                            rr, gg, bb = maximum.split()
                            intensity = ImageChops.lighter(ImageChops.lighter(rr, gg), bb)
                            changed += sum(intensity.histogram()[1:])
                            aa, ab = a.getchannel("A").histogram(), b.getchannel("A").histogram()
                            partial_ref += sum(aa[1:255])
                            partial_cand += sum(ab[1:255])
                            transparent_ref += aa[0]
                            transparent_cand += ab[0]
                            blank = Image.new("L", intensity.size, 0)
                            alpha = Image.new("L", intensity.size, 255)
                            raster.paste(Image.merge("RGBA", (intensity, blank, blank, alpha)),
                                         (x0, y0 - strip_y))
                    for row in range(raster.height):
                        scan = b"\x00" + raster.crop(
                            (0, row, width, row + 1)).tobytes()
                        encoded = compressor.compress(scan)
                        if encoded:
                            _png_chunk(writer, b"IDAT", encoded)
                tail = compressor.flush()
                if tail:
                    _png_chunk(writer, b"IDAT", tail)
                _png_chunk(writer, b"IEND", b"")
            # Enforce integrity of the stream *before* publication.
            with Image.open(staged) as png:
                png.verify()
            png_digest = sha256(staged)
            if sha256(ref) != ref_sha or sha256(candidate) != cand_sha:
                raise ArtifactIntegrityError("Comparison images changed during evaluation")
            os.replace(staged, target)
        result = {
            "schema_version": SCHEMA_VERSION,
            "purpose": "operator_attested_translation_overlap_diagnostics_only",
            "comparison": kind,
            "alignment_kind": "integer_translation",
            "alignment_record_sha256": record_sha,
            "reference_sha256": ref_sha,
            "candidate_sha256": cand_sha,
            "reference_dimensions": [width, height],
            "candidate_dimensions": [cand_w, cand_h],
            "reference_to_candidate_translation_xy": [dx, dy],
            "registration": "operator_attested_not_computed",
            "interpolation": "none",
            "coordinate_frame": _FRAME,
            "overlap_pixels": valid_count,
            "overlap_fraction_of_reference": round(valid_count / ref_total, 8),
            "overlap_fraction_of_candidate": round(valid_count / candidate_total, 8),
            "metrics": {
                "changed_pixel_count": changed,
                "changed_pixel_fraction_of_overlap": round(changed / valid_count, 8),
                "mean_composited_channel_delta_0_1": round(
                    delta_sum / (valid_count * 6 * 255), 8),
                "reference_partial_alpha_fraction_of_overlap": round(
                    partial_ref / valid_count, 8),
                "candidate_partial_alpha_fraction_of_overlap": round(
                    partial_cand / valid_count, 8),
                "reference_transparent_fraction_of_overlap": round(
                    transparent_ref / valid_count, 8),
                "candidate_transparent_fraction_of_overlap": round(
                    transparent_cand / valid_count, 8),
            },
            "heatmap_sha256": png_digest,
            "heatmap_format": "RGBA PNG, red delta within overlap, transparent outside",
            "human_visual_quality_score": None,
            "inference_cost_usd": 0,
            "decoder_memory_note": "Pillow may decode whole input frames internally",
        }
        atomic_text(root / (name + ".json"),
                    json.dumps(result, sort_keys=True, indent=2) + "\n")
        return result
