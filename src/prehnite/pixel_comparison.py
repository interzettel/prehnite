"""Conservative, local pixel-grid diagnostics for already verified image pairs.

Same dimensions do NOT establish registration. The caller explicitly attests a
shared coordinate grid before metrics are computed; no automatic registration,
retouch ranking, remote judging or provider access occurs here.
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from .artifacts import ArtifactIntegrityError, atomic_text, verified_image
from .manifest import resolve_input
from .schema import Asset, relative_name
from .store import Journal

SCHEMA_VERSION = 1
MAX_METRIC_PIXELS = 4_000_000  # Smaller than 24MP inspector, bounds decoded working sets.
MAX_EMBEDDED_BYTES = 64 * 1024 * 1024
_SUPPORTED = {"RGB", "RGBA"}
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".webp": "image/webp"}


def _selected(root: Path, name: str, checksums: dict) -> tuple[Path, str]:
    relative = relative_name(name)
    directory = (root / "selected").resolve()
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory):
        raise ArtifactIntegrityError("Comparison output escapes approved batch root")
    sha = checksums.get(relative)
    if not isinstance(sha, str) or len(sha) != 64:
        raise ArtifactIntegrityError("Missing comparison output digest")
    verified_image(path, sha)
    return path, sha


def _verify_bytes(path: Path, digest: str) -> bytes:
    verified_image(path, digest)
    if path.stat().st_size > MAX_EMBEDDED_BYTES:
        raise ValueError("Comparison input exceeds embedded-byte limit")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ArtifactIntegrityError("Comparison image changed during snapshot")
    return data


def _read_pair(first: bytes, second: bytes) -> tuple[
        Image.Image | None, Image.Image | None, str | None,
        tuple[int, int], tuple[int, int]]:
    """Check headers before decoding; no automatic EXIF/ICC/geometric transform."""
    with Image.open(io.BytesIO(first)) as a, Image.open(io.BytesIO(second)) as b:
        frame_a, frame_b = a.size, b.size
        # Different dimensions cannot share a pixel grid; do not infer resize.
        if frame_a != frame_b:
            return None, None, "geometry_mismatch", frame_a, frame_b
        if a.width * a.height > MAX_METRIC_PIXELS:
            return None, None, "metric_pixel_budget_exceeded", frame_a, frame_b
        if (a.getexif().get(274, 1) not in (None, 1)
                or b.getexif().get(274, 1) not in (None, 1)):
            return None, None, "orientation_unresolved", frame_a, frame_b
        if a.mode not in _SUPPORTED or b.mode not in _SUPPORTED:
            return None, None, "pixel_encoding_unsupported", frame_a, frame_b
        if a.info.get("icc_profile") != b.info.get("icc_profile"):
            return None, None, "color_profile_mismatch", frame_a, frame_b
        # At most 4 MP of decoded pixels per image; no large mismatch decode.
        a.load()
        b.load()
        return a.copy(), b.copy(), None, frame_a, frame_b


def _against_background(image: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (*color, 255))
    return Image.alpha_composite(background, rgba).convert("RGB")


def _numeric_diff(a: Image.Image, b: Image.Image) -> tuple[dict, bytes]:
    black = ImageChops.difference(
        _against_background(a, (0, 0, 0)), _against_background(b, (0, 0, 0)))
    white = ImageChops.difference(
        _against_background(a, (255, 255, 255)), _against_background(b, (255, 255, 255)))
    # Compositing on two contrasting backgrounds avoids letting arbitrary RGB
    # bytes in fully transparent pixels create phantom differences.
    peak = ImageChops.lighter(black, white)
    r, g, blue = peak.split()
    intensity = ImageChops.lighter(ImageChops.lighter(r, g), blue)
    histogram = intensity.histogram()
    changed = sum(histogram[1:])
    total = a.width * a.height
    aa = a.convert("RGBA").getchannel("A").histogram()
    bb = b.convert("RGBA").getchannel("A").histogram()
    # Reports fractions, NOT segmentation accuracy or human visual quality.
    stats = {
        "pixel_count": total,
        "changed_pixel_count": changed,
        "changed_pixel_fraction": round(changed / total, 8),
        "mean_composited_channel_delta_0_1": round(
            sum(ImageStat.Stat(black).mean + ImageStat.Stat(white).mean) / (6 * 255), 8),
        "reference_partial_alpha_fraction": round(sum(aa[1:255]) / total, 8),
        "candidate_partial_alpha_fraction": round(sum(bb[1:255]) / total, 8),
        "reference_transparent_fraction": round(aa[0] / total, 8),
        "candidate_transparent_fraction": round(bb[0] / total, 8),
    }
    zero = Image.new("L", a.size, 0)
    heatmap = Image.merge("RGB", (intensity, zero, zero))
    output = io.BytesIO()
    heatmap.save(output, format="PNG")
    return stats, output.getvalue()


def _comparison_html(reference: bytes, candidate: bytes, heatmap: bytes,
                     reference_mime: str, candidate_mime: str,
                     record: dict) -> str:
    def img(data: bytes, media: str, label: str) -> str:
        uri = "data:" + media + ";base64," + base64.b64encode(data).decode("ascii")
        return ('<section><h2>' + html.escape(label) + '</h2><div class="viewport">'
                '<img alt="' + html.escape(label) + '" src="' + uri
                + '" /></div></section>')
    metrics = record["metrics"]
    detail = (
        '<p class="notice">Operator-asserted pixel grid, not automatic registration. '
        'No human aesthetic score or provider invoice. Differences describe encoded '
        'pixel observations on black and white backgrounds.</p>'
        '<p><strong>Pixels changed:</strong> ' + str(metrics["changed_pixel_count"])
        + ' / ' + str(metrics["pixel_count"]) + '</p>'
        '<p><strong>Changed fraction:</strong> '
        + f'{metrics["changed_pixel_fraction"]:.6f}' + '</p>'
        '<p><strong>Mean composited channel delta (0–1):</strong> '
        + f'{metrics["mean_composited_channel_delta_0_1"]:.6f}' + '</p>'
        '<p><strong>Partially transparent:</strong> reference '
        + f'{metrics["reference_partial_alpha_fraction"]:.6f}'
        + ', candidate ' + f'{metrics["candidate_partial_alpha_fraction"]:.6f}' + '</p>'
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; '
        'base-uri \'none\'; form-action \'none\'; connect-src \'none\'">'
        '<title>Prehnite · Technical pixel comparison</title><style>'
        ':root{color-scheme:light dark;font:15px/1.5 system-ui,sans-serif}'
        'body{margin:0;padding:20px;max-width:1500px;margin-inline:auto}'
        '.panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:16px}'
        '.viewport{max-height:60vh;overflow:auto;border:1px solid gray;background:#ccc}'
        '.viewport img{display:block;max-width:100%;height:auto}'
        'main:has(#actual:checked) .viewport img{max-width:none;width:auto;height:auto}'
        'section{min-width:0}h2{font-size:1.1rem}.notice{max-width:85ch}'
        '</style></head><body><main>'
        '<h1>Private pixel-grid diagnostics</h1>'
        '<p class="notice">Verified local evidence. No scripts, external assets or model calls.</p>'
        '<fieldset><legend>Inspection scale</legend>'
        '<label><input type="radio" id="fit" name="scale" checked> Fit</label>'
        '<label><input type="radio" id="actual" name="scale"> Native 1:1</label></fieldset>'
        + detail + '<div class="panels">'
        + img(reference, reference_mime, "Reference")
        + img(candidate, candidate_mime, "Candidate")
        + img(heatmap, "image/png", "Encoded delta heatmap")
        + '</div></main></body></html>'
    )


def compare_slot(
    journal: Journal, asset_id: str, *,
    inputs: Path | None = None, cutout: str | None = None,
    same_grid_asserted: bool = False,
) -> dict:
    """Private, explicit one-slot comparison; no inferred image registration.

    Choose exactly one reference: historical source via --inputs, or named
    selected cutout via --cutout. Refuse missing hash / unapproved paths before
    creating any HTML, PNG or JSON evidence.
    """
    Asset.check_id(asset_id)
    if (inputs is None) == (cutout is None):
        raise ValueError("Choose exactly one reference: --inputs or --cutout")
    if not same_grid_asserted:
        raise ValueError("Pixel comparison requires --assume-same-grid attestation")
    results = journal.fact("results", {})
    result = results.get(asset_id)
    if not isinstance(result, dict) or result.get("status") not in ("accepted", "failed_cutouts"):
        raise ValueError("Pixel comparison requires an accepted base output")
    outputs = result.get("outputs", [])
    checksums = result.get("outputs_sha256", {})
    if not isinstance(outputs, list) or not outputs or not isinstance(checksums, dict):
        raise ArtifactIntegrityError("Missing recorded outputs and digests")
    assets = journal.fact("manifest", {}).get("assets", [])
    asset = next((a for a in assets if isinstance(a, dict) and a.get("id") == asset_id), None)
    if asset is None:
        raise ValueError("Cannot compare a slot missing from the recorded manifest")
    selected = asset.get("output", {})
    if not isinstance(selected, dict) or selected.get("image") != outputs[0]:
        raise ArtifactIntegrityError("Selected base is inconsistent with manifest")
    root = journal.root
    base_path, base_sha = _selected(root, outputs[0], checksums)
    base_bytes = _verify_bytes(base_path, base_sha)
    if inputs is not None:
        if not isinstance(asset.get("source"), str) or not asset["source"]:
            raise ValueError("Prompt-generated slot has no original to compare")
        saved = journal.fact("input_file_sha256")
        source_sha = saved.get(asset_id) if isinstance(saved, dict) else None
        if not isinstance(source_sha, str) or len(source_sha) != 64:
            raise ArtifactIntegrityError("No historical original source SHA256")
        source_path = resolve_input(Path(inputs), relative_name(asset["source"]))
        ref_path, ref_sha = source_path, source_sha
        ref_kind = "historical_original"
        cand_path, cand_sha = base_path, base_sha
        cand_bytes = base_bytes
    else:
        if not isinstance(cutout, str) or not cutout or not cutout.isidentifier():
            raise ValueError("Invalid named cutout target")
        named = selected.get("cutouts", {})
        if not isinstance(named, dict) or cutout not in named or named[cutout] not in outputs[1:]:
            raise ValueError("Cutout is not a recorded selected output")
        ref_path, ref_sha = base_path, base_sha
        ref_kind = "accepted_base"
        cand_path, cand_sha = _selected(root, named[cutout], checksums)
        cand_bytes = _verify_bytes(cand_path, cand_sha)
    ref_bytes = _verify_bytes(ref_path, ref_sha)
    if len(ref_bytes) + len(cand_bytes) > MAX_EMBEDDED_BYTES:
        raise ValueError("Comparison exceeds 64 MiB encoded-byte budget")

    first, second, reason, ref_size, cand_size = _read_pair(ref_bytes, cand_bytes)
    record = {
            "schema_version": SCHEMA_VERSION,
            "purpose": "technical_pixel_observation_only",
            "comparison": ("original_vs_base" if inputs is not None else "base_vs_cutout"),
            "reference_kind": ref_kind,
            "registration": "operator_asserted_same_pixel_grid_no_computed_transform",
            "geometric_transform": None,
            "status": ("not_comparable" if reason else "comparable"),
            "reason_code": reason,
            "reference_sha256": ref_sha,
            "candidate_sha256": cand_sha,
            "reference_dimensions": list(ref_size),
            "candidate_dimensions": list(cand_size),
            "icc_contract": "both_untagged_or_identical_profile_bytes",
            "comparison_color_space": "encoded_channels_not_perceptual_or_linear",
            "human_quality_judgment": None,
            "actual_provider_invoice_usd": None,
            "metrics": None,
        }
    if reason:
        # Explain refusal without generating an enticing but invalid overlay.
        return record
    assert first is not None and second is not None
    with first, second:
        metrics, heatmap = _numeric_diff(first, second)
    record["metrics"] = metrics
    if len(ref_bytes) + len(cand_bytes) + len(heatmap) > MAX_EMBEDDED_BYTES:
        raise ValueError("Comparison exceeds 64 MiB full evidence budget")
    ref_media = _MIME.get(ref_path.suffix.lower())
    cand_media = _MIME.get(cand_path.suffix.lower())
    if not ref_media or not cand_media:
        raise ValueError("Unsupported image container for private HTML")
    page = _comparison_html(ref_bytes, cand_bytes, heatmap, ref_media, cand_media, record)
    destination = root / "reviews"
    if not destination.resolve().is_relative_to(root.resolve()):
        raise ArtifactIntegrityError("Review destination escapes batch root")
    suffix = "original" if inputs is not None else "cutout"
    stem = asset_id + "-difference-" + suffix
    # Atomic file writes; the JSON manifest is the publication marker and last.
    from .artifacts import temporary_sibling
    import os
    diff_file = destination / (stem + ".png")
    with temporary_sibling(diff_file) as temp:
        temp.write_bytes(heatmap)
        os.replace(temp, diff_file)
    atomic_text(destination / (stem + ".html"), page)
    record["heatmap_sha256"] = hashlib.sha256(heatmap).hexdigest()
    atomic_text(destination / (stem + ".json"),
                json.dumps(record, sort_keys=True, indent=2, allow_nan=False) + "\n")
    return record
