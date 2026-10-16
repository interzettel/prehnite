"""Demonstrate the zero-cost A/B positional audit on synthetic PNGs.

Run from an editable install:
    python examples/position_bias_demo.py --output position-audit.json

This never instantiates a remote judge or uses any API key.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from prehnite.position_audit import Comparison, audit_pairs, write_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("position-audit.json"))
    args = parser.parse_args()
    with TemporaryDirectory() as workspace:
        root = Path(workspace)
        first, second = root/"red.png", root/"blue.png"
        Image.new("RGB", (64, 64), "red").save(first)
        Image.new("RGB", (64, 64), "blue").save(second)
        comparison = Comparison("synthetic-swap", "red", first, "blue", second,
                                "A product photo of a red object",
                                "Image quality and prompt fidelity, 0..1")

        def favor_first(images, prompt, rubric):
            return {"winner": "A", "scores": {"A": 0.9, "B": 0.2},
                    "reason": "SYNTHETIC first-position bias; no real judging"}

        result = audit_pairs([comparison], favor_first)
        write_report(args.output, result)
        print(f"Synthetic positional audit written to {args.output}")
        print("Swapped identity winner:", result["pairs"][0]["winner_flip"])
        print("First position wins:", result["summary"]["first_position_wins"])


if __name__ == "__main__":
    main()
