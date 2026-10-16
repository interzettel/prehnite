"""On-demand native-pixel, offline inspection of one already verified slot.

Unlike gallery.html, this page embeds original, *unresampled* bytes for one
asset only, after digest and decodability checks. It is not included in default
archives and never makes browser network requests or model-provider calls.
"""
from __future__ import annotations

import base64
import hashlib
import html
import re
from collections import Counter
from pathlib import Path

from .artifacts import ArtifactIntegrityError, atomic_text, verified_image
from .brand import embedded_theme_css
from .manifest import resolve_input
from .schema import Asset, relative_name
from .store import Journal

MAX_EMBEDDED_BYTES = 64 * 1024 * 1024
MAX_PANELS = 12
MAX_RENDER_PIXELS = 24_000_000
_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def export_native_inspection(
        journal: Journal, asset_id: str, *,
        inputs: Path | None = None) -> Path:
    """Generate one self-contained, full-resolution inspection page.

    The caller must control this private workspace. Fail closed on stale
    hashes, symlinks escaping selected/, invalid/missing outputs or oversized
    assets; an existing inspection HTML remains intact on failure.
    """
    Asset.check_id(asset_id)
    results = journal.fact("results", {})
    result = results.get(asset_id)
    if not isinstance(result, dict) or result.get("status") not in (
            "accepted", "failed_cutouts"):
        raise ValueError("Native inspection requires an accepted base delivery")
    outputs = result.get("outputs", [])
    if not isinstance(outputs, list) or not 1 <= len(outputs):
        raise ValueError("Expected at least one selected output for single-slot inspection")
    # The explicit original occupies a panel too; never exceed the combined cap.
    if len(outputs) + (1 if inputs is not None else 0) > MAX_PANELS:
        raise ValueError("Native inspection exceeds the 12-panel limit")
    checksums = result.get("outputs_sha256", {})
    if not isinstance(checksums, dict):
        raise ArtifactIntegrityError("Missing selected output hashes")
    manifest = journal.fact("manifest", {})
    entries = manifest.get("assets", []) if isinstance(manifest, dict) else []
    asset = next((a for a in entries
                  if isinstance(a, dict) and a.get("id") == asset_id), {})
    declared = asset.get("output", {}) if isinstance(asset.get("output"), dict) else {}
    if declared.get("image") and outputs[0] != declared["image"]:
        raise ArtifactIntegrityError("Base output differs from recorded manifest")
    cutouts = declared.get("cutouts", {})
    if isinstance(cutouts, dict) and cutouts:
        unexpected = set(outputs[1:]) - set(cutouts.values())
        if unexpected:
            raise ArtifactIntegrityError("Cutout output differs from recorded manifest")
    root = (journal.root / "selected").resolve()
    total_bytes = 0
    blocks = []
    if inputs is not None:
        # CLI batches may have been created with an arbitrary --inputs root.
        # Never guess the original folder from journal location or file name.
        source = asset.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError("This slot has no original source image to inspect")
        source = relative_name(source)
        previous = journal.fact("input_file_sha256")
        expected = previous.get(asset_id) if isinstance(previous, dict) else None
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ArtifactIntegrityError("No verified historical original-input hash")
        original = resolve_input(Path(inputs), source)
        # Only an original still matching the original batch fingerprint
        # may be presented as the real original. Never update the fingerprint.
        original_info = verified_image(original, expected)
        if original_info["width"] * original_info["height"] > MAX_RENDER_PIXELS:
            raise ValueError("Original exceeds the native pixel safety limit")
        media = _MIME.get(original.suffix.lower())
        if media is None:
            raise ValueError("Unsupported original image format")
        source_bytes = original.read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != expected:
            raise ArtifactIntegrityError("Original input changed while reading")
        total_bytes += len(source_bytes)
        if total_bytes > MAX_EMBEDDED_BYTES:
            raise ValueError("Native detail exceeds 64 MiB embedded-image limit")
        uri = "data:" + media + ";base64," + base64.b64encode(source_bytes).decode("ascii")
        blocks.append(
            '<section class="panel"><h2>Original input (SHA256 verified)</h2>'
            '<p class="info">Owner-provided source · '
            + str(original_info["width"]) + ' × ' + str(original_info["height"])
            + ' px</p><div class="viewport"><img src="' + uri
            + '" width="' + str(original_info["width"]) + '" height="'
            + str(original_info["height"]) + '" alt="Verified original for '
            + html.escape(asset_id, quote=True) + '" /></div></section>'
        )
    seen = set()
    for position, raw in enumerate(outputs):
        name = relative_name(raw)
        if name in seen:
            raise ArtifactIntegrityError("Repeated selected output path")
        seen.add(name)
        target = (root / name).resolve()
        if not target.is_relative_to(root):
            raise ArtifactIntegrityError("Selected file escapes batch root")
        info = verified_image(target, checksums.get(name))
        if info["width"] * info["height"] > MAX_RENDER_PIXELS:
            raise ValueError("Selected image exceeds the native pixel safety limit")
        media = _MIME.get(target.suffix.lower())
        if not media:
            raise ValueError("Unsupported native inspector image format")
        if total_bytes + target.stat().st_size > MAX_EMBEDDED_BYTES:
            raise ValueError("Native detail exceeds 64 MiB embedded-image limit")
        image_bytes = target.read_bytes()
        total_bytes += len(image_bytes)
        if total_bytes > MAX_EMBEDDED_BYTES:
            raise ValueError("Native detail exceeds 64 MiB embedded-image limit")
        # The digest is rechecked against the *read bytes* to catch changes
        # after preflight but before embedding.
        if hashlib.sha256(image_bytes).hexdigest() != checksums[name]:
            raise ArtifactIntegrityError("Selected image changed during native review")
        cutout_labels = declared.get("cutouts", {})
        kind = "Selected base" if position == 0 else "Named cutout"
        if isinstance(cutout_labels, dict):
            label = next((key for key, path in cutout_labels.items()
                          if path == name), None)
            if label is not None:
                kind = "Cutout: " + str(label)
        dimension = f"{info['width']} × {info['height']}"
        uri = "data:" + media + ";base64," + base64.b64encode(image_bytes).decode("ascii")
        blocks.append(
            '<section class="panel"><h2>' + html.escape(kind, quote=True)
            + '</h2><p class="info">' + html.escape(name, quote=True)
            + ' · ' + dimension + ' px · SHA256 verified</p>'
            + '<div class="viewport' + (' checker' if position else '') + '">'
            + '<img src="' + uri + '" width="' + str(info["width"])
            + '" height="' + str(info["height"]) + '" alt="'
            + html.escape(kind + " for " + asset_id, quote=True)
            + '" /></div></section>'
        )
    # Agent-readable operator evidence without raw operation keys, remote IDs,
    # model strings, paths, prompts, exceptions or untrusted freeform notes.
    def safe_label(value: object) -> str:
        return (value if isinstance(value, str)
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", value)
                else "unknown")

    attempts = Counter(
        a["task_key"] for a in journal.attempts()
        if isinstance(a, dict) and isinstance(a.get("task_key"), str))
    stages = []
    for row in journal.tasks():
        task_key = row.get("task_key")
        if not isinstance(task_key, str) or not task_key.startswith(asset_id + ":"):
            continue
        reserve = row.get("reserved_usd", 0)
        reserve = float(reserve) if type(reserve) in (int, float) and 0 <= reserve < 1e9 else 0.0
        stages.append((
            safe_label(row.get("stage")),
            safe_label(row.get("provider")),
            safe_label(row.get("status")),
            attempts.get(task_key, 0),
            reserve,
        ))
    stage_rows = "".join(
        "<tr><td>" + html.escape(name) + "</td><td>" + html.escape(provider)
        + "</td><td>" + html.escape(state) + "</td><td>" + str(count)
        + "</td><td>$" + f"{reserved:.6f}" + "</td></tr>"
        for name, provider, state, count, reserved in sorted(stages)
    )
    stage_table = (
        '<section class="evidence"><h2>Local stage observations</h2>'
        '<p class="hint">Local attempts and reserved estimates only; no actual '
        'provider invoice or validated visual-quality claim.</p><div class="table-scroll">'
        '<table><thead><tr><th>Stage</th><th>Provider</th><th>Status</th>'
        '<th>Local attempts</th><th>Reserved USD</th></tr></thead><tbody>'
        + stage_rows + '</tbody></table></div></section>'
        if stages else '<p class="hint">No recorded stages for this asset.</p>'
    )
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; img-src data:; '
        'style-src \'unsafe-inline\'; base-uri \'none\'; '
        'form-action \'none\'; connect-src \'none\'">'
        '<title>Prehnite · Native inspection</title>'
        '<style>'
        ':root{color-scheme:light dark;font:15px/1.5 system-ui,sans-serif;'
        '--bg:#f2f5f1;--panel:#fff;--fg:#213630;--sub:#52665d;--line:#cddbd1}'
        '@media(prefers-color-scheme:dark){:root{--bg:#17221e;--panel:#22342c;'
        '--fg:#e7eee9;--sub:#b9c9be;--line:#52665a}}'
        '*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg)}'
        'main{padding:22px;max-width:1600px;margin:auto}h1{margin:0 0 5px}'
        '.hint,.info{color:var(--sub);font-size:.82rem}fieldset{display:flex;'
        'gap:18px;flex-wrap:wrap;border:0;padding:14px 0;margin:0 0 16px}'
        'label{cursor:pointer}input{accent-color:#287d6f}'
        '.panels{display:grid;grid-template-columns:repeat(auto-fit,'
        'minmax(min(100%,490px),1fr));gap:14px}'
        '.panel{min-width:0;background:var(--panel);padding:17px;'
        'border:1px solid var(--line);border-radius:9px}'
        '.panel h2{font-size:1rem;margin:0}.panel .info{overflow-wrap:anywhere}'
        '.viewport{overflow:auto;max-height:68vh;border:1px solid var(--line);'
        'background:var(--panel)}'
        '.checker{background-color:#eee;background-image:linear-gradient(45deg,'
        '#bbb 25%,transparent 25%),linear-gradient(-45deg,#bbb 25%,transparent 25%),'
        'linear-gradient(45deg,transparent 75%,#bbb 75%),'
        'linear-gradient(-45deg,transparent 75%,#bbb 75%);'
        'background-size:24px 24px;background-position:0 0,0 12px,12px -12px,-12px 0}'
        '.viewport img{display:block;max-width:100%;height:auto}'
        'main:has(#actual:checked) .viewport img{max-width:none;width:auto;height:auto}'
        'main:has(#checker:not(:checked)) .checker{background:var(--panel);background-image:none}'
        '.evidence{margin-top:23px;padding:17px;background:var(--panel);border:1px solid var(--line)}'
        '.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.83rem}'
        'th,td{text-align:left;padding:8px 14px 8px 0;border-bottom:1px solid var(--line)}'
        '</style></head><body><main><h1>Prehnite / Native inspection</h1>'
        '<p class="hint">Private local evidence · no quality certification · '
        'no network, script, or resampling. Actual pixels means one image pixel '
        'per CSS pixel at 100% browser zoom; display scaling may vary.</p>'
        '<fieldset><legend>Image size</legend>'
        '<label><input type="radio" name="scale" id="fit" checked> Fit to panel</label>'
        '<label><input type="radio" name="scale" id="actual"> Actual pixels (1:1)</label>'
        '<label><input type="checkbox" id="checker" checked> Alpha checkerboard</label>'
        '</fieldset><div class="panels">' + "".join(blocks)
        + '</div>' + stage_table + '</main></body></html>'
    )
    output = journal.root / "reviews" / (asset_id + ".html")
    # The reviews directory itself must never be a symlink outside the batch.
    if not output.parent.resolve().is_relative_to(journal.root.resolve()):
        raise ArtifactIntegrityError("Review destination escapes batch root")
    page = page.replace('</style>', embedded_theme_css() + '</style>', 1)
    atomic_text(output, page)
    return output
