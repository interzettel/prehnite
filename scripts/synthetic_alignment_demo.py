"""Create an inspectable, entirely synthetic 4K translated-image test artifact.

ONLY fake Pillow geometry and owner-approved brand colors. Never use this
CI artifact path for production images, prompts, or user source files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from prehnite.brand import LIGHT
from prehnite.images import image_info
from prehnite.store import Journal
from prehnite.tiled_alignment import compare_registered_tiles


def generate(destination: Path) -> dict:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="prehnite-synthetic-4k-") as temp:
        root = Path(temp)
        workspace = root / "workspace"
        original_root = root / "inputs"
        original_root.mkdir()
        journal = Journal(workspace, "synthetic-alignment")
        try:
            width, height, dx, dy = 3840, 2160, 11, -7
            source = original_root / "fake-riso.png"
            reference = Image.new("RGB", (width, height), LIGHT["bg"])
            drawing = ImageDraw.Draw(reference)
            drawing.polygon([(450, 310), (1350, 380), (1100, 1660),
                             (320, 1480)], fill=LIGHT["ink"])
            drawing.ellipse((1650, 410, 3020, 1770), fill=LIGHT["coral"])
            drawing.rectangle((2190, 800, 2760, 1290), fill=LIGHT["ink"])
            reference.save(source, optimize=True)
            candidate = Image.new("RGB", (width, height), LIGHT["bg"])
            # Candidate(x + dx, y + dy) = reference(x,y), without resampling.
            candidate.paste(reference.crop((0, -dy, width - dx, height)),
                            (dx, 0))
            candidate.putpixel((2200, 1000), (255, 255, 255))
            selected = journal.root / "selected/images/demo.png"
            selected.parent.mkdir(parents=True, exist_ok=True)
            candidate.save(selected, optimize=True)
            ref_sha = image_info(source)["sha256"]
            cand_sha = image_info(selected)["sha256"]
            journal.set_fact("manifest", {"assets": [{
                "id": "demo", "source": "fake-riso.png",
                "output": {"image": "images/demo.png", "cutouts": {}},
            }]})
            journal.set_fact("input_file_sha256", {"demo": ref_sha})
            journal.set_fact("results", {"demo": {
                "status": "accepted", "outputs": ["images/demo.png"],
                "outputs_sha256": {"images/demo.png": cand_sha},
            }})
            alignment = root / "transform.json"
            alignment.write_text(json.dumps({
                "schema_version": 1, "kind": "integer_translation",
                "dx_pixels": dx, "dy_pixels": dy,
                "reference_sha256": ref_sha,
                "candidate_sha256": cand_sha,
                "coordinate_frame": "raw_unrotated_encoded_pixels_exif_orientation_1",
                "interpolation": "none",
                "attestation": "operator_asserted_not_inferred",
            }, indent=2) + "\n", encoding="utf-8")
            data = compare_registered_tiles(
                journal, "demo", inputs=original_root, alignment=alignment)
            assert data["metrics"]["changed_pixel_count"] == 1
            for original, filename in [
                (source, "synthetic-reference.png"),
                (selected, "synthetic-candidate.png"),
                (alignment, "alignment.json"),
                (journal.root / "reviews/demo-registered-original.png",
                 "registered-delta.png"),
                (journal.root / "reviews/demo-registered-original.json",
                 "registered-delta.json"),
            ]:
                shutil.copyfile(original, destination / filename)
            (destination / "README.txt").write_text(
                "SYNTHETIC 3840x2160 ONLY — no user pixels.\n"
                "Open reference and candidate images and the RGBA delta PNG.\n"
                "Transparent margins are excluded from the pixel difference.\n"
                "The white pixel at (2200,1000) is the only registered change.\n"
                "No automated image alignment or quality score.\n",
                encoding="utf-8")
            (destination / "digests.json").write_text(
                json.dumps({
                    f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                    for f in sorted(destination.iterdir()) if f.is_file()
                    and f.name != "digests.json"
                }, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            return {"dimensions": [width, height], "translation": [dx, dy],
                    "overlap_pixels": data["overlap_pixels"],
                    "changed_pixel_count": data["metrics"]["changed_pixel_count"]}
        finally:
            journal.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("alignment-4k-synthetic"))
    args = parser.parse_args()
    print(json.dumps(generate(args.output), indent=2, sort_keys=True))
