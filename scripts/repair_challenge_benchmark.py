"""Synthetic cutout stress matrix, never a substitute for human-rated images.

Run: python scripts/repair_challenge_benchmark.py --workspace /tmp/prehnite-challenges
References stay in this benchmark only; prehnite.repair cannot access them.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from prehnite.artifacts import atomic_text
from prehnite.images import sha256
from prehnite.repair import run_product_repair
from prehnite.store import Journal

SIZE = (192, 192)
BG = (74, 175, 135)
FG = (233, 176, 124)


@dataclass(frozen=True)
class Challenge:
    slug: str
    category: str
    expectation: str
    cohort: str = "product"
    material: str = "opaque"


CASES = (
    Challenge("opaque-flat", "Opaque product / uniform background", "technically_accepted"),
    Challenge("opaque-dark", "Opaque product / alternate dark background", "technically_accepted"),
    Challenge("small-lighting-jitter", "Opaque product / bounded exposure variation", "technically_accepted"),
    Challenge("thin-fringe", "Opaque product / thinner segmentation leakage", "technically_accepted"),
    Challenge("smooth-gradient", "Product / directional lighting gradient", "human_review"),
    Challenge("checkerboard", "Product / textured backdrop", "human_review"),
    Challenge("random-texture", "Product / nonuniform noise", "human_review"),
    Challenge("cast-shadow", "Product / frame-reaching shadow", "human_review"),
    Challenge("two-products", "Ambiguous product instances", "human_review"),
    Challenge("frame-crop", "Partially cropped product", "human_review"),
    Challenge("color-collision", "Foreground material matches backdrop", "human_review"),
    Challenge("interior-mask-hole", "Opaque product / missing interior part", "human_review"),
    Challenge("furniture-hole", "Object with a legitimate through-hole", "human_review"),
    Challenge("thick-halo", "Alpha leakage wider than bounded band", "human_review"),
    Challenge("clean-mask", "Valid matte / nothing to repair", "human_review"),
    Challenge("portrait-hair", "Portrait fine strands / uncertain boundaries", "human_review", "portrait"),
    Challenge("portrait-fur", "Animal fur / disconnected strands", "human_review", "portrait"),
    Challenge("glass", "Translucent glass / alpha not opaque", "human_review", "product", "glass"),
    Challenge("sheer-fabric", "Sheer fabric / semi-transparent fringe", "human_review", "product", "translucent"),
    Challenge("unknown-material", "Material not independently classified", "human_review", "product", "unknown"),
)


def _save(image: Image.Image, path: Path) -> None:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError("Existing fixture differs; refusing to overwrite: " + path.name)
    if not path.exists():
        path.write_bytes(data)


def create_fixture(workspace: Path, case: Challenge) -> dict[str, Path]:
    """Create a deterministic source, independent true alpha, and bad mask."""
    source = Image.new("RGB", SIZE, BG)
    ref = Image.new("L", SIZE, 0)
    if case.slug == "opaque-dark":
        source.paste((24, 57, 70), (0, 0, *SIZE))
    elif case.slug == "smooth-gradient":
        for x in range(SIZE[0]):
            for y in range(SIZE[1]):
                source.putpixel((x, y), (40 + x // 2, 125 + x // 4, 116))
    elif case.slug == "checkerboard":
        painter = ImageDraw.Draw(source)
        for y in range(0, SIZE[1], 12):
            for x in range(0, SIZE[0], 12):
                if (x // 12 + y // 12) % 2:
                    painter.rectangle((x, y, x + 11, y + 11), fill=(138, 115, 98))
    elif case.slug == "random-texture":
        for y in range(SIZE[1]):
            for x in range(SIZE[0]):
                variance = ((x * 37 + y * 17 + x * y * 7) % 39) - 19
                source.putpixel((x, y), tuple(max(0, min(255, channel + variance)) for channel in BG))
    elif case.slug == "cast-shadow":
        ImageDraw.Draw(source).rectangle((0, 0, 23, SIZE[1] - 1), fill=(35, 87, 71))

    painter = ImageDraw.Draw(source)
    matte = ImageDraw.Draw(ref)
    if case.cohort == "portrait":
        painter.ellipse((58, 38, 138, 154), fill=(199, 143, 107))
        matte.ellipse((58, 38, 138, 154), fill=255)
        for index in range(16):
            x = 63 + index * 5
            painter.line((x, 69, x - 20 + (index % 4) * 2, 9), fill=(63, 39, 37), width=2)
            matte.line((x, 69, x - 20 + (index % 4) * 2, 9), fill=255, width=2)
    else:
        painter.rounded_rectangle((51, 38, 143, 154), radius=15, fill=FG)
        matte.rounded_rectangle((51, 38, 143, 154), radius=15, fill=255)
        painter.rectangle((78, 58, 114, 148), fill=(182, 102, 79))
        if case.slug == "two-products":
            painter.rectangle((153, 66, 177, 122), fill=(221, 179, 143))
            matte.rectangle((153, 66, 177, 122), fill=255)
        elif case.slug == "frame-crop":
            painter.rectangle((0, 81, 52, 117), fill=FG)
            matte.rectangle((0, 81, 52, 117), fill=255)
        elif case.slug == "color-collision":
            # This remains part of the ground-truth opaque foreground;
            # matching background RGB is not proof of transparency.
            painter.rectangle((79, 86, 106, 116), fill=BG)
        elif case.slug == "furniture-hole":
            painter.rectangle((82, 78, 111, 120), fill=source.getpixel((0, 0)))
            matte.rectangle((82, 78, 111, 120), fill=0)
        elif case.slug == "glass":
            painter.rectangle((72, 56, 122, 140), fill=(114, 191, 167))
            matte.rectangle((72, 56, 122, 140), fill=92)
        elif case.slug == "sheer-fabric":
            for y in range(64, 142):
                painter.line((76, y, 125, y), fill=(182, 188, 167), width=1)
                matte.line((76, y, 125, y), fill=120)

    # Bounded, deliberately wrong segmentation. The benchmark's exact
    # reference is NEVER supplied to the repairer. Only source + bad mask.
    radius = 3 if case.slug == "thin-fringe" else (19 if case.slug == "thick-halo" else 7)
    defective = ref.filter(ImageFilter.MaxFilter(radius))
    if case.slug == "clean-mask":
        defective = ref.copy()
    if case.slug == "interior-mask-hole":
        ImageDraw.Draw(defective).rectangle((84, 93, 102, 111), fill=0)
    if case.slug == "small-lighting-jitter":
        # Alter only background RGB, not the independent reference mask.
        for y in range(SIZE[1]):
            for x in range(SIZE[0]):
                if ref.getpixel((x, y)) == 0:
                    v = ((x * 5 + y * 7) % 5) - 2
                    source.putpixel((x, y), tuple(channel + v for channel in BG))

    root = workspace / "fixtures" / case.slug
    output = {n: root / (n + ".png") for n in ("source", "reference", "defective")}
    _save(source, output["source"])
    _save(ref, output["reference"])
    _save(defective, output["defective"])
    return output


def metrics(reference: Path, image: Image.Image) -> dict:
    """Binary IoU and normalized alpha/edge absolute error, fixed dimensions."""
    with Image.open(reference) as truth:
        a = truth.convert("L")
        b = image.convert("L")
        if b.size != a.size:
            raise ValueError("Reference geometry mismatch")
        a_bytes, b_bytes = a.tobytes(), b.tobytes()
        intersection = sum(p > 127 and q > 127 for p, q in zip(a_bytes, b_bytes))
        union = sum(p > 127 or q > 127 for p, q in zip(a_bytes, b_bytes))
        iou = intersection / union if union else 1.0
        alpha_mae = sum(abs(p - q) for p, q in zip(a_bytes, b_bytes)) / (255 * len(a_bytes))
        # Pixel-accurate 3x3 morphological edge, no perception or VLM.
        def edge(img: Image.Image) -> Image.Image:
            return ImageChops.difference(
                img.filter(ImageFilter.MaxFilter(3)),
                img.filter(ImageFilter.MinFilter(3)))
        ea, eb = edge(a).tobytes(), edge(b).tobytes()
        edge_mae = sum(abs(p - q) for p, q in zip(ea, eb)) / (255 * len(ea))
        return {"iou": round(iou, 6), "alpha_mae": round(alpha_mae, 6),
                "edge_mae": round(edge_mae, 6)}


def _preview(source: Path, alpha: Image.Image) -> str:
    with Image.open(source) as opened:
        rgba = opened.convert("RGBA")
        rgba.putalpha(alpha.convert("L"))
    bg = Image.new("RGB", rgba.size, (251, 249, 236))
    brush = ImageDraw.Draw(bg)
    for y in range(0, bg.height, 12):
        for x in range(0, bg.width, 12):
            if (x // 12 + y // 12) % 2:
                brush.rectangle((x, y, x + 11, y + 11), fill=(203, 212, 194))
    bg.paste(rgba, mask=rgba.getchannel("A"))
    buf = io.BytesIO()
    bg.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _html(results: list[dict], panels: list[tuple[str, str]]) -> str:
    entries = []
    for result, pair in zip(results, panels):
        before, after = pair
        slug = escape(result["case"])
        expected = escape(result["expected"])
        observed = escape(result["actual"])
        reason = escape(result["reason"])
        before_metric = result["before"]
        after_metric = result["after"]
        delta = "Not evaluated" if after_metric is None else (
            f'{before_metric["iou"]:.6f} → {after_metric["iou"]:.6f}')
        entries.append(
            "<article><h2>" + slug + "</h2><p>" + escape(result["category"])
            + "</p><div class='photos'><figure><img alt='Defective "
            + slug + "' src='" + before + "'><figcaption>Before</figcaption></figure>"
            + "<figure><img alt='Post-decision " + slug + "' src='" + after
            + "'><figcaption>After / original if refused</figcaption></figure></div>"
            + "<p><strong>" + observed + "</strong> / expected " + expected
            + "</p><p>Reference IoU: " + escape(delta)
            + "</p><p class='reason'>" + reason + "</p></article>")
    total = len(results)
    improved = sum(r["actual"] == "technically_accepted" for r in results)
    reviewed = sum(r["actual"] == "human_review" for r in results)
    return """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Prehnite / controlled challenging-mask matrix</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:light dark;--paper:#F6EFE2;--surface:#FFF9EC;--green:#075231;--muted:#53675A;--coral:#A63D35}
@media(prefers-color-scheme:dark){:root{--paper:#132820;--surface:#203A2E;--green:#F6EFE2;--muted:#CED4C2;--coral:#FD8276}}
body{font:15px/1.5 system-ui,sans-serif;margin:auto;padding:32px;max-width:1200px;background:var(--paper);color:var(--green)}
header{max-width:800px}h1{font-size:clamp(28px,5vw,54px);line-height:1.1;margin:12px 0}
.summary{border-left:4px solid var(--coral);padding-left:16px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px;margin-top:28px}
article{background:var(--surface);padding:16px;border:1px solid var(--muted)}article h2{margin:0;font-size:20px}
.photos{display:grid;grid-template-columns:1fr 1fr;gap:8px}figure{margin:0}figure img{width:100%;image-rendering:pixelated}
figcaption{font-size:12px} .reason{color:var(--coral);overflow-wrap:anywhere}
</style><body><header><p>PREHNITE / EXPERIMENT 002 / SYNTHETIC ONLY</p>
<h1>Harder cases. Stricter refusals.</h1>
<p class="summary">""" + str(total) + " deterministic scenarios · " + str(improved) \
        + " controlled repairs · " + str(reviewed) + """ human-review outcomes.
Synthetic references are never passed to the repair engine. Automatic
technical decisions are not evidence of real-world mask quality; human-rated
portraits, fur, glass and product images remain unverified.</p></header>
<main>""" + "".join(entries) + "</main></body></html>"


def run(workspace: Path) -> dict:
    workspace = workspace.resolve()
    rows, panels = [], []
    for case in CASES:
        paths = create_fixture(workspace, case)
        original_sha = {key: sha256(path) for key, path in paths.items()}
        journal = Journal(workspace, "challenge-" + case.slug)
        try:
            actual = run_product_repair(
                journal, paths["source"], paths["defective"],
                asset_id="challenging-asset", target_id="selected",
                cohort=case.cohort, material=case.material)
            records = journal.db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='local_repairs'").fetchone()[0]
            count = (journal.db.execute("SELECT COUNT(*) FROM local_repairs").fetchone()[0]
                     if records else 0)
        finally:
            journal.close()
        if any(sha256(path) != original_sha[key] for key, path in paths.items()):
            raise AssertionError("A source, defective mask or reference changed")
        observed = actual["status"]
        if observed != case.expectation:
            raise AssertionError(f"{case.slug}: expected {case.expectation}, got {observed}: {actual}")
        with Image.open(paths["defective"]) as mask:
            bad = mask.copy()
        before = metrics(paths["reference"], bad)
        after = None
        final_mask = bad
        output_sha = None
        if observed == "technically_accepted":
            output_path = Path(actual["output"])
            if sha256(output_path) != actual["output_sha256"]:
                raise AssertionError("Published candidate checksum mismatch")
            with Image.open(output_path) as opened:
                final_mask = opened.getchannel("A").copy()
            after = metrics(paths["reference"], final_mask)
            if not (after["iou"] > before["iou"]
                    and after["alpha_mae"] < before["alpha_mae"]
                    and after["edge_mae"] < before["edge_mae"]):
                raise AssertionError(f"{case.slug}: correction did not improve all metrics")
            if count != 1 or actual["would_spend_usd"] != 0:
                raise AssertionError("Invalid journal or price evidence")
            output_sha = actual["output_sha256"]
        elif count > 1:
            raise AssertionError("Duplicate operation created on review")
        panels.append((_preview(paths["source"], bad), _preview(paths["source"], final_mask)))
        rows.append({
            "case": case.slug, "category": case.category,
            "cohort": case.cohort, "material": case.material,
            "expected": case.expectation, "actual": observed,
            "reason": actual["reason"], "before": before, "after": after,
            "source_sha256": original_sha["source"],
            "defective_sha256": original_sha["defective"],
            "reference_sha256": original_sha["reference"],
            "output_sha256": output_sha,
            "logical_attempt_count": count,
            "provider_requests": 0, "additional_paid_usd": 0,
        })
    summary = {
        "schema_version": 1, "fixtures": "deterministic_synthetic_only",
        "benchmark_reference_used_by_repair": False,
        "production_quality_established": False, "provider_requests": 0,
        "additional_paid_usd": 0, "case_count": len(rows),
        "technically_accepted": sum(r["actual"] == "technically_accepted" for r in rows),
        "human_review": sum(r["actual"] == "human_review" for r in rows),
        "cases": rows,
    }
    root = workspace / "evidence" / "experiment-002"
    atomic_text(root / "report.json", json.dumps(summary, sort_keys=True, indent=2) + "\n")
    atomic_text(root / "report.html", _html(rows, panels))
    return {"report_html": str(root / "report.html"),
            "report_json": str(root / "report.json"),
            "cases": len(rows), "accepted": summary["technically_accepted"],
            "review": summary["human_review"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("prehnite-challenge-demo"))
    args = parser.parse_args()
    print(json.dumps(run(args.workspace), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
