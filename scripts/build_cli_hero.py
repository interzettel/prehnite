"""Build a looping CLI GIF from the owner-selected README hero image.

Offline, deterministic animation: retains the supplied surroundings while
redrawing the central terminal pane. No model, GPU, web, or paid API activity.

Usage:
    python scripts/build_cli_hero.py --source /path/to/selected-image.png \
        --output assets/prehnite-cli-hero.gif
"""
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

COLORS = {"ink": "#041B17", "coral": "#F7655B", "paper": "#F6EFE2", "sage": "#79AB92"}
CHARACTERS = {
    "P": ("11110", "10001", "11110", "10000", "10000"),
    "R": ("11110", "10001", "11110", "10100", "10010"),
    "E": ("11111", "10000", "11110", "10000", "11111"),
    "H": ("10001", "10001", "11111", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001"),
    "I": ("11111", "00100", "00100", "00100", "11111"),
    "T": ("11111", "00100", "00100", "00100", "00100"),
}


def render(source: Path, output: Path, width: int = 720) -> None:
    if width < 320 or width > 1600:
        raise ValueError("width must be between 320 and 1600")
    image = Image.open(source).convert("RGB")
    if image.width / image.height < 1.6 or image.width / image.height > 2.1:
        raise ValueError("expected owner's wide Prehnite laptop illustration")
    scale = width / image.width
    image = image.resize((width, round(image.height * scale)), Image.Resampling.LANCZOS)
    base = image.quantize(colors=80, method=Image.Quantize.MEDIANCUT,
                          dither=Image.Dither.NONE)
    palette = base.getpalette()

    def color(hexval: str) -> int:
        rgb = tuple(int(hexval[1 + i:3 + i], 16) for i in (0, 2, 4))
        return min(range(80),
                   key=lambda j: sum((palette[3*j+k]-rgb[k])**2 for k in range(3)))

    def point(x: float, y: float) -> tuple[int, int]:
        return round(x * scale), round(y * scale)

    def frame(stage: int) -> Image.Image:
        img = base.copy()
        draw = ImageDraw.Draw(img)
        left, top = point(420, 344)
        cell = max(2, round(13 * scale))
        x1, y1 = point(406, 328)
        x2, y2 = point(1258, 690)
        draw.rounded_rectangle((x1, y1, x2, y2), radius=max(2, round(9*scale)),
                               fill=color(COLORS["ink"]))
        for i, ch in enumerate("PREHNITE"[:min(stage, 8)]):
            for j, row in enumerate(CHARACTERS[ch]):
                for k, v in enumerate(row):
                    if v == "1":
                        x = left + (i*6+k)*cell
                        y = top + j*cell
                        draw.rectangle((x, y, x+cell-2, y+cell-2),
                                       fill=color(COLORS["coral"]))
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", max(9, round(23*scale)))
        except OSError:
            font = ImageFont.load_default()
        if stage >= 8:
            draw.text(point(420, 492), "make the images. keep the experiments.",
                      font=font, fill=color(COLORS["paper"]))
        if stage >= 9:
            draw.text(point(420, 548), "$ prehnite doctor", font=font,
                      fill=color(COLORS["sage"]))
        if stage >= 10:
            draw.text(point(420, 578),
                      "$ prehnite run batch.yaml --profile local.yaml", font=font,
                      fill=color(COLORS["paper"]))
        cy = top if stage == 0 else (
            top+6*cell if stage < 9 else point(420, 638)[1])
        draw.rectangle((left, cy, left+max(2, round(11*scale)),
                        cy+max(4, round(18*scale))), fill=color(COLORS["paper"]))
        return img

    stages = [0, 2, 5, 8, 9, 10, 10]
    durations = [300, 200, 200, 500, 750, 1600, 850]
    frames = [frame(stage) for stage in stages]
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=True, disposal=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=720)
    args = parser.parse_args()
    render(args.source, args.output, args.width)
