"""On-demand native-pixel, offline inspection of one already verified slot.

Unlike gallery.html, this page embeds original, *unresampled* bytes for one
asset only, after digest and decodability checks. It is not included in default
archives and never makes browser network requests or model-provider calls.
"""
from __future__ import annotations

import base64
import html
from pathlib import Path

from .artifacts import ArtifactIntegrityError, atomic_text, verified_image
from .schema import Asset, relative_name
from .store import Journal

MAX_EMBEDDED_BYTES = 64 * 1024 * 1024
MAX_PANELS = 12
_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def export_native_inspection(journal: Journal, asset_id: str) -> Path:
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
    if not isinstance(outputs, list) or not 1 <= len(outputs) <= MAX_PANELS:
        raise ValueError("Expected 1-12 selected outputs for single-slot inspection")
    checksums = result.get("outputs_sha256", {})
    if not isinstance(checksums, dict):
        raise ArtifactIntegrityError("Missing selected output hashes")
    manifest = journal.fact("manifest", {})
    entries = manifest.get("assets", []) if isinstance(manifest, dict) else []
    asset = next((a for a in entries
                  if isinstance(a, dict) and a.get("id") == asset_id), {})
    declared = asset.get("output", {}) if isinstance(asset.get("output"), dict) else {}
    root = (journal.root / "selected").resolve()
    total_bytes = 0
    blocks = []
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
        media = _MIME.get(target.suffix.lower())
        if not media:
            raise ValueError("Unsupported native inspector image format")
        image_bytes = target.read_bytes()
        total_bytes += len(image_bytes)
        if total_bytes > MAX_EMBEDDED_BYTES:
            raise ValueError("Native detail exceeds 64 MiB embedded-image limit")
        # The digest is rechecked against the *read bytes* to catch changes
        # after preflight but before embedding.
        import hashlib
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
        '</style></head><body><main><h1>Prehnite / Native inspection</h1>'
        '<p class="hint">Private local evidence · no quality certification · '
        'no network, script, or resampling. Actual pixels means one image pixel '
        'per CSS pixel at 100% browser zoom; display scaling may vary.</p>'
        '<fieldset><legend>Image size</legend>'
        '<label><input type="radio" name="scale" id="fit" checked> Fit to panel</label>'
        '<label><input type="radio" name="scale" id="actual"> Actual pixels (1:1)</label>'
        '</fieldset><div class="panels">' + "".join(blocks) + '</div></main></body></html>'
    )
    output = journal.root / "reviews" / (asset_id + ".html")
    atomic_text(output, page)
    return output
