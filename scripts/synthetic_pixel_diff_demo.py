"""Write inspectable, synthetic-only pixel-comparison evidence for CI review.

Never use this script to publish real batch data. The entire workspace is built
from fresh, locally drawn Pillow shapes and disposed of after export.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from prehnite.images import image_info
from prehnite.pixel_comparison import compare_slot
from prehnite.store import Journal


def generate(destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="prehnite-fake-diff-") as work:
        home = Path(work)
        inputs = home / "inputs"
        inputs.mkdir()
        j = Journal(home / "workspace", "synthetic-demo")
        try:
            original = inputs / "synthetic-original.png"
            reference = Image.new("RGB", (320, 240), "#eee7dc")
            draw = ImageDraw.Draw(reference)
            draw.ellipse((45, 35, 205, 200), fill="#387d74")
            draw.rectangle((195, 70, 287, 165), fill="#df8454")
            reference.save(original)

            base = j.root / "selected/photos/demo.png"
            base.parent.mkdir(parents=True, exist_ok=True)
            adjusted = reference.copy()
            d = ImageDraw.Draw(adjusted)
            d.rectangle((100, 95, 155, 148), fill="#c74d49")
            adjusted.save(base)

            cutout = j.root / "selected/cutouts/subject.png"
            cutout.parent.mkdir(parents=True, exist_ok=True)
            rgba = adjusted.convert("RGBA")
            mask = Image.new("L", rgba.size, 0)
            ImageDraw.Draw(mask).ellipse((45, 35, 205, 200), fill=255)
            rgba.putalpha(mask.filter(ImageFilter.GaussianBlur(radius=2)))
            rgba.save(cutout)
            j.set_fact("manifest", {"assets": [{
                "id": "demo", "source": "synthetic-original.png",
                "output": {"image": "photos/demo.png",
                           "cutouts": {"subject": "cutouts/subject.png"}},
            }]})
            j.set_fact("input_file_sha256", {
                "demo": image_info(original)["sha256"],
            })
            j.set_fact("results", {"demo": {
                "status": "accepted",
                "outputs": ["photos/demo.png", "cutouts/subject.png"],
                "outputs_sha256": {
                    "photos/demo.png": image_info(base)["sha256"],
                    "cutouts/subject.png": image_info(cutout)["sha256"],
                },
            }})
            summary = {}
            for label, options in [
                ("original", {"inputs": inputs}),
                ("cutout", {"cutout": "subject"}),
            ]:
                record = compare_slot(j, "demo", same_grid_asserted=True, **options)
                assert record["status"] == "comparable"
                stem = f"demo-difference-{label}"
                for extension in ("html", "png", "json"):
                    source = j.root / "reviews" / f"{stem}.{extension}"
                    target = destination / f"synthetic-{label}.{extension}"
                    shutil.copyfile(source, target)
                    if extension == "html":
                        text = target.read_text(encoding="utf-8").replace(
                            "Private pixel-grid diagnostics</h1>",
                            "Private pixel-grid diagnostics · SYNTHETIC DEMO</h1>")
                        target.write_text(text, encoding="utf-8")
                summary[label] = {
                    "schema_version": record["schema_version"],
                    "status": record["status"],
                    "changed_pixel_count": record["metrics"]["changed_pixel_count"],
                    "heatmap_sha256": hashlib.sha256(
                        (destination / f"synthetic-{label}.png").read_bytes()).hexdigest(),
                }
            (destination / "README.txt").write_text(
                "SYNTHETIC FIXTURE ONLY. Open synthetic-original.html and "
                "synthetic-cutout.html locally. No user data, providers or GPU.\n",
                encoding="utf-8")
            (destination / "summary.json").write_text(
                json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            return summary
        finally:
            j.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("pixel-diff-synthetic"))
    args = parser.parse_args()
    print(json.dumps(generate(args.output), sort_keys=True, indent=2))
