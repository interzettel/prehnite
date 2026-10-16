"""Reproducible, zero-network synthetic product/portrait repair demonstration.

Usage: python scripts/repair_demo.py --workspace /tmp/prehnite-repair-demo
The reference mask is used ONLY here for post-repair benchmarking.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from prehnite.artifacts import atomic_text
from prehnite.images import sha256
from prehnite.repair import run_product_repair
from prehnite.store import Journal


def _save_immutable(image: Image.Image, destination: Path) -> None:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    content = buffer.getvalue()
    if destination.exists():
        if destination.read_bytes() != content:
            raise ValueError("Synthetic fixture exists with different bytes; refusing overwrite")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def _fixture(workspace: Path, cohort: str) -> dict:
    size = (240, 240)
    source = Image.new("RGB", size, "#4aaf87")
    reference = Image.new("L", size, 0)
    image_draw = ImageDraw.Draw(source)
    mask_draw = ImageDraw.Draw(reference)
    if cohort == "product":
        shape = (76, 56, 164, 194)
        image_draw.rounded_rectangle(shape, radius=16, fill="#e8b17d")
        mask_draw.rounded_rectangle(shape, radius=16, fill=255)
        image_draw.ellipse((89, 39, 151, 90), fill="#e8b17d")
        mask_draw.ellipse((89, 39, 151, 90), fill=255)
        image_draw.rectangle((108, 65, 132, 190), fill="#b96949")
    else:
        image_draw.ellipse((77, 58, 163, 181), fill="#d5a47e")
        mask_draw.ellipse((77, 58, 163, 181), fill=255)
        for x in (85, 91, 98, 104, 140, 147, 153):
            image_draw.line((x, 80, x - 15, 24), fill="#573e38", width=2)
            mask_draw.line((x, 80, x - 15, 24), fill=255, width=2)
    defective = reference.filter(ImageFilter.MaxFilter(size=7))
    root = workspace / "synthetic" / cohort
    paths = {key: root / (key + ".png") for key in ("source", "reference", "defective")}
    for key, im in (("source", source), ("reference", reference), ("defective", defective)):
        _save_immutable(im, paths[key])
    return {key: str(value) for key, value in paths.items()}


def _iou(reference: Path, mask: Image.Image) -> float:
    with Image.open(reference) as image:
        truth = image.convert("L").tobytes()
    actual = mask.convert("L").tobytes()
    intersection = sum(a > 127 and b > 127 for a, b in zip(truth, actual))
    union = sum(a > 127 or b > 127 for a, b in zip(truth, actual))
    return intersection / union if union else 1.0


def _checkered(image: Path, mask: Path) -> Image.Image:
    with Image.open(image) as original, Image.open(mask) as alpha:
        rgba = original.convert("RGBA")
        rgba.putalpha(alpha.convert("L"))
    return _composite(rgba)


def _composite(rgba: Image.Image) -> Image.Image:
    bg = Image.new("RGB", rgba.size, "white")
    painter = ImageDraw.Draw(bg)
    for y in range(0, rgba.height, 16):
        for x in range(0, rgba.width, 16):
            if ((x // 16) + (y // 16)) % 2 == 0:
                painter.rectangle((x, y, x + 15, y + 15), fill="#dedbd2")
    bg.paste(rgba, (0, 0), rgba.getchannel("A"))
    return bg


def _uri(image: Image.Image) -> str:
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def _report_html(product: dict, portrait: dict, fixtures: dict,
                 reference_metrics: dict) -> str:
    source = Image.open(fixtures["product"]["source"]).convert("RGB")
    before = _checkered(Path(fixtures["product"]["source"]),
                        Path(fixtures["product"]["defective"]))
    repaired_path = product.get("output")
    after = _composite(Image.open(repaired_path).convert("RGBA")) if repaired_path else before
    portrait_before = _checkered(Path(fixtures["portrait"]["source"]),
                                 Path(fixtures["portrait"]["defective"]))
    cards = [
        ("Original product source", _uri(source)),
        ("Defective alpha cutout", _uri(before)),
        ("Verified local correction", _uri(after)),
        ("Portrait control: deliberately not repaired", _uri(portrait_before)),
    ]
    figures = "".join(
        '<figure><img alt="' + escape(title) + '" src="' + uri + '"><figcaption>'
        + escape(title) + '</figcaption></figure>' for title, uri in cards
    )
    details = escape(json.dumps({
        "product": {key: val for key, val in product.items() if key != "output"},
        "portrait": portrait,
        "reference_benchmark": reference_metrics,
    }, indent=2, sort_keys=True))
    return """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prehnite — local self-correction evidence</title>
<style>
:root{color-scheme:light dark;--paper:#F6EFE2;--surface:#FFF9EC;--green:#075231;
--coral:#A63D35;--line:#b8bdae}
@media(prefers-color-scheme:dark){:root{--paper:#132820;--surface:#203A2E;
--green:#F6EFE2;--coral:#FD8276;--line:#627668}}
*{box-sizing:border-box}body{margin:auto;max-width:1150px;padding:36px 22px;
background:var(--paper);color:var(--green);font:16px/1.5 system-ui,sans-serif}
h1{font-size:clamp(27px,5vw,56px);line-height:1.08;margin:12px 0}
.eyebrow{letter-spacing:.15em;font-size:12px;text-transform:uppercase}
.note{border-left:4px solid var(--coral);padding-left:16px;max-width:790px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(225px,1fr));gap:16px;margin:24px 0}
figure{margin:0;background:var(--surface);padding:12px;border:1px solid var(--line)}
img{width:100%;height:auto;image-rendering:pixelated}
figcaption{margin-top:10px;font-size:14px}
pre{background:var(--surface);padding:20px;overflow:auto;border:1px solid var(--line);
white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}
.metric{color:var(--coral);font-weight:700}
</style><body>
<p class="eyebrow">PREHNITE / EXPERIMENT 001 / OFFLINE SYNTHETIC</p>
<h1>One repair. No regeneration.</h1>
<p class="note">Deterministic product fringe correction only. Accepted means
<strong>technical demo acceptance</strong>, not visual-quality certification.
The portrait fixture intentionally abstains. No provider calls, credentials,
external uploads, model inference or human calibration.</p>
<section class="grid">""" + figures + """</section>
<h2>Withheld-reference benchmark</h2><p>Product reference-mask intersection-over-union:
<span class="metric">""" + escape(str(reference_metrics)) + """</span></p>
<h2>Journal and policy receipt</h2><pre>""" + details + """</pre>
<p>Inputs and repaired outputs remain separate. Re-running verifies hashes
and reuses the same logical operation ID. This demonstration is not yet
connected to the production Engine cutout acceptance path.</p></body></html>"""


def run(workspace: Path) -> dict:
    workspace = workspace.resolve()
    fixtures = {cohort: _fixture(workspace, cohort) for cohort in ("product", "portrait")}
    journal = Journal(workspace, "repair-demo-001")
    try:
        product = run_product_repair(
            journal, Path(fixtures["product"]["source"]),
            Path(fixtures["product"]["defective"]),
            asset_id="ceramic-product", target_id="one-object")
        portrait = run_product_repair(
            journal, Path(fixtures["portrait"]["source"]),
            Path(fixtures["portrait"]["defective"]),
            asset_id="hair-portrait", target_id="one-person", cohort="portrait")
        if product["status"] != "technically_accepted" or portrait["status"] != "human_review":
            raise RuntimeError("Expected bounded demonstration outcome not achieved")
        with Image.open(fixtures["product"]["defective"]) as defective:
            before_iou = _iou(Path(fixtures["product"]["reference"]), defective)
        with Image.open(product["output"]) as repaired:
            after_iou = _iou(Path(fixtures["product"]["reference"]),
                             repaired.getchannel("A"))
        metrics = {"product_iou_before": round(before_iou, 6),
                   "product_iou_after": round(after_iou, 6)}
        if not after_iou > before_iou:
            raise RuntimeError("Reference evaluation did not improve")
        count = journal.db.execute(
            "SELECT COUNT(*) FROM local_repairs WHERE operation_id=?",
            (product["operation_id"],)).fetchone()[0]
        if count != 1:
            raise RuntimeError("Duplicate logical repair operation")
        root = workspace / "evidence" / "experiment-001"
        result = {
            "schema_version": 1, "scope": "synthetic_product_and_portrait",
            "technical_only": True, "provider_requests": 0, "actual_paid_usd": 0,
            "fixture_paths": fixtures,
            "fixture_sha256": {cohort: {key: sha256(Path(path))
                               for key, path in paths.items()}
                               for cohort, paths in fixtures.items()},
            "product": product, "portrait": portrait,
            "reference_benchmark": metrics, "logical_attempt_count": count,
        }
        atomic_text(root / "report.json", json.dumps(result, sort_keys=True, indent=2) + "\n")
        atomic_text(root / "report.html", _report_html(product, portrait, fixtures, metrics))
        return {"html": str(root / "report.html"),
                "json": str(root / "report.json"), **metrics}
    finally:
        journal.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("prehnite-repair-demo"))
    args = parser.parse_args()
    print(json.dumps(run(args.workspace), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
