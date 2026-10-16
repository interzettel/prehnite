"""Self-contained, offline visual review of local batch outputs.

This exports a STATIC HTML document. It never creates client network requests,
executes JavaScript, or claims that thumbnail inspection proves image quality.
"""
from __future__ import annotations

import base64
import html
import io
import re
from pathlib import Path

from PIL import Image, ImageOps

from .artifacts import atomic_text, verified_image
from .images import image_info
from .schema import relative_name
from .store import Journal
from .brand import embedded_theme_css
from .analytics import build_analytics, render_analytics
from .economics import batch_economics


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _thumbnail(source: Path, *, edge: int = 370) -> tuple[str, bool]:
    """Produce an embedded downsampled preview; never a quality-grade 4K crop."""
    with Image.open(source) as original:
        picture = ImageOps.exif_transpose(original)
        picture.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        if picture.mode in ("RGBA", "LA") or "transparency" in picture.info:
            rgba = picture.convert("RGBA")
            buffer = io.BytesIO()
            rgba.save(buffer, "PNG")
            mimetype = "image/png"
            transparent = True
        else:
            buffer = io.BytesIO()
            picture.convert("RGB").save(buffer, "JPEG", quality=82, optimize=True)
            mimetype = "image/jpeg"
            transparent = False
    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:{mimetype};base64,{data}", transparent


def _figure(path: Path, label: str, *, verified: bool = False) -> str:
    uri, transparent = _thumbnail(path)
    classes = "thumb checker" if transparent else "thumb"
    caption = _escape(label)
    qualifier = " · SHA256 verified" if verified else " · preview only"
    return (f'<figure><div class="{classes}">'
            f'<img loading="lazy" src="{uri}" alt="{caption}" /></div>'
            f'<figcaption>{caption}{_escape(qualifier)}</figcaption></figure>')


def _safe_in_batch(root: Path, path: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve()) and path.is_file()


def _candidate_paths(root: Path, asset_id: str, max_items: int = 4):
    """Local intermediates only; never follow user-controlled absolute paths."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", asset_id):
        return []
    directory = root / "intermediates" / asset_id
    if not directory.is_dir() or not directory.resolve().is_relative_to(root.resolve()):
        return []
    items = []
    for attempt in sorted(directory.glob("attempt-*")):
        if not attempt.is_dir() or not attempt.resolve().is_relative_to(root.resolve()):
            continue
        for variant in sorted(attempt.iterdir()):
            if not variant.is_dir() or not variant.resolve().is_relative_to(root.resolve()):
                continue
            path = variant / "final.png"
            if _safe_in_batch(root, path):
                items.append((path, f"{attempt.name} / {variant.name}"))
    return items[:max_items]


def _tile_card(root: Path, asset_id: str, result: dict) -> str:
    status = str(result.get("status", "unknown"))
    reason = str(result.get("reason", ""))[:500]
    images = []
    candidates = _candidate_paths(root, asset_id)
    for path, label in candidates:
        try:
            image_info(path)
            images.append(_figure(path, f"Candidate {label}"))
        except (OSError, ValueError):
            # A damaged intermediate is not an accepted deliverable.
            images.append(f'<p class="notice">{_escape(label)} could not be decoded.</p>')
    accepted = []
    if status == "accepted" and not result.get("outputs"):
        raise ValueError("Accepted asset lacks named deliverables")
    if status in ("accepted", "failed_cutouts"):
        digests = result.get("outputs_sha256", {})
        for path_str in result.get("outputs", []):
            path_str = relative_name(path_str)
            target = (root / "selected" / path_str).resolve()
            if not target.is_relative_to((root / "selected").resolve()):
                raise ValueError("Selected image escapes batch directory")
            verified_image(target, digests.get(path_str))
            label = "Cutout" if path_str.lower().endswith(".png") and (
                path_str != result.get("outputs", [""])[0]) else "Selected"
            accepted.append(_figure(target, f"{label}: {path_str}", verified=True))
    selected = "".join(accepted)
    previews = "".join(images)
    score = result.get("quality_score")
    scored = (f'<span class="meta">Judge score: {_escape(score)}</span>'
              if isinstance(score, (float, int)) and not isinstance(score, bool)
              else '<span class="meta">No calibrated quality score</span>')
    return (f'<article class="asset"><header><h2>{_escape(asset_id)}</h2>'
            f'<span class="state state-{_escape(status)}">{_escape(status)}</span></header>'
            f'<div class="meta-row">{scored}'
            f'<span class="meta">Winning variant: '
            f'{_escape(result.get("winning_variant", "—"))}</span></div>'
            + (f'<p class="reason">{_escape(reason)}</p>' if reason else "")
            + (f'<h3>Accepted delivery</h3><div class="figures">{selected}</div>'
               if selected else '<p class="notice">No accepted deliverables in this record.</p>')
            + (f'<details><summary>Inspect {len(candidates)} intermediate candidates'
               '</summary><div class="figures">' + previews + '</div></details>'
               if candidates else "")
            + '</article>')


def export_gallery(journal: Journal, analytics: dict | None = None) -> Path:
    """Regenerate an offline analytics dashboard with verified visual previews."""
    root = journal.root
    results = journal.fact("results", {})
    if not isinstance(results, dict):
        raise ValueError("Invalid result dictionary")
    manifest = journal.fact("manifest", {})
    asset_ids = [
        a.get("id") for a in manifest.get("assets", [])
        if isinstance(a, dict) and isinstance(a.get("id"), str)
    ] if isinstance(manifest, dict) else []
    # Also surface failures with missing manifest entries; never drop an error.
    ids = list(dict.fromkeys(asset_ids + list(results)))
    if analytics is None:
        tasks, attempts = journal.tasks(), journal.attempts()
        analytics = build_analytics(manifest, results, tasks, attempts,
                                   batch_economics(tasks, results, attempts))
    rows = []
    for asset_id in ids:
        if not isinstance(asset_id, str):
            raise ValueError("Invalid asset identifier")
        result = results.get(asset_id, {"status": "pending", "outputs": []})
        if not isinstance(result, dict):
            raise ValueError("Invalid asset result")
        rows.append(_tile_card(root, asset_id, result))
    accepted = sum(r.get("status") == "accepted" for r in results.values()
                   if isinstance(r, dict))
    rejected = sum(r.get("status") in ("rejected", "error", "failed_cutouts")
                   for r in results.values() if isinstance(r, dict))
    page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<meta http-equiv="Content-Security-Policy"
content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; connect-src 'none'" />
<title>Prehnite · Offline analytics and review</title>
<style>
:root{color-scheme:light dark;font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
--bg:#f4f6f2;--paper:#fff;--ink:#19312c;--sub:#53635d;--line:#d5ddd6}
@media(prefers-color-scheme:dark){:root{--bg:#17211e;--paper:#20312b;--ink:#e6eee8;
--sub:#b6c7be;--line:#42534a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink)}
main{max-width:1240px;margin:auto;padding:22px}
h1{font-size:clamp(1.6rem,4vw,2.5rem);margin:0}h2{font-size:1.16rem;margin:0}
h3{font-size:.9rem;color:var(--sub);margin:16px 0 9px}
.intro{margin:12px 0 28px;color:var(--sub);max-width:75ch}
.analytics{margin:0 0 35px}
.analytics-top{display:grid;gap:18px;margin:18px 0 22px}
.analytics-top h2{font-size:1.65rem;letter-spacing:-.025em}
.eyebrow{color:var(--sub);font-size:.69rem;letter-spacing:.13em;font-weight:700}
.quiet,.small{color:var(--sub)}
.small{font-size:.79rem;line-height:1.45;max-width:72ch}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px}
.kpi,.analytics-panel{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:17px}
.kpi strong{display:block;font-size:clamp(1.18rem,2.8vw,1.8rem);letter-spacing:-.04em;
font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.kpi span{font-size:.76rem;color:var(--sub)}
.analytics-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr));
gap:13px;margin:14px 0}
.analytics-panel{min-width:0}
.analytics-panel h3{font-size:.92rem;margin:0 0 17px;color:var(--ink)}
.metric-bar{margin:12px 0}
.metric-label{display:flex;justify-content:space-between;gap:12px;
font-size:.82rem;margin-bottom:6px;font-variant-numeric:tabular-nums}
.metric-label strong{white-space:nowrap}
.track{height:9px;border-radius:9px;background:var(--line);overflow:hidden}
.fill{display:block;height:100%;background:#28796b;border-radius:9px}
.fill-neutral{background:#9eada5}.fill-alert{background:#bd7552}
.table-scroll{overflow-x:auto}
.analytics-panel table{border-collapse:collapse;width:100%;font-size:.81rem;font-variant-numeric:tabular-nums}
.analytics-panel th,.analytics-panel td{text-align:left;padding:9px 10px 9px 0;
border-bottom:1px solid var(--line);white-space:nowrap}
.analytics-panel thead th{font-size:.73rem;color:var(--sub);font-weight:600}
.failure-items{list-style:none;margin:0;padding:0}
.failure-items li{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--line)}
.failure-items code{font-size:.76rem;overflow-wrap:anywhere}
@media(min-width:860px){.analytics-top{grid-template-columns:1fr 2fr;align-items:center}}
@media(max-width:500px){main{padding:16px}.asset{padding:15px}.kpi{padding:12px}}
.dashboard{display:flex;gap:14px;flex-wrap:wrap;margin:17px 0 26px}
.dashboard span{border:1px solid var(--line);border-radius:9px;padding:8px 12px}
.asset{background:var(--paper);border:1px solid var(--line);border-radius:14px;
padding:20px;margin-bottom:18px}
.asset header{display:flex;justify-content:space-between;gap:12px;align-items:center}
.state{border:1px solid var(--line);border-radius:30px;padding:3px 10px;font-size:.75rem}
.meta-row{display:flex;flex-wrap:wrap;gap:8px;margin:9px 0}
.meta{color:var(--sub);font-size:.85rem}
.figures{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,220px),1fr));gap:14px}
figure{margin:0;min-width:0}
.thumb{display:grid;place-items:center;min-height:180px;border-radius:8px;overflow:hidden;
background:#e3e8e2}
.checker{background-color:#eee;background-image:conic-gradient(#dedede 25%,#fff 0 50%,#dedede 0 75%,#fff 0);background-size:20px 20px}
.thumb img{display:block;max-width:100%;max-height:370px;object-fit:contain}
figcaption{margin:6px 1px;color:var(--sub);font-size:.78rem;overflow-wrap:anywhere}
.reason{background:var(--bg);padding:9px 12px;border-radius:7px;overflow-wrap:anywhere}
.notice{color:var(--sub);font-style:italic}
details{margin-top:17px;border-top:1px solid var(--line);padding-top:12px}
summary{cursor:pointer;color:var(--sub);margin-bottom:12px}
footer{color:var(--sub);margin:28px 0;font-size:.85rem}
</style></head><body><main>""" + (
        "<header><h1>Prehnite / offline production dashboard</h1>"
        "<p class='intro'>Local thumbnails only. Previews are deliberately downsampled; "
        "inspect native 1:1 crops for fine detail. Reported judge scores are uncalibrated. "
        "This standalone page has no scripts, external fonts, analytics or image requests. "
        "Sharing this HTML file shares the embedded thumbnail pixels.</p>"
        f"<div class='dashboard'><span>{len(ids)} assets</span>"
        f"<span>{accepted} accepted</span><span>{rejected} need attention</span></div></header>"
        + render_analytics(analytics)
        + "".join(rows)
        + "<footer>Offline local report · source images and full-resolution exports are "
          "not embedded · no remote content loaded.</footer></main></body></html>"
    )
    location = root / "gallery.html"
    page = page.replace('</style>', embedded_theme_css() + '</style>', 1)
    atomic_text(location, page)
    return location
