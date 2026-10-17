"""Validate the standalone offline Review Studio ZIP or autosave folder.

python scripts/inspect_human_review.py --input /private/review.zip --output /private/validated
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prehnite.review_intake import write_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True,
                        help="Untrusted browser review ZIP or its autosave folder")
    parser.add_argument("--output", type=Path, required=True,
                        help="New, empty private results directory")
    args = parser.parse_args()
    report = write_report(args.input, args.output)
    print(json.dumps({
        "reviewed": report["reviewed"], "pending": report["pending"],
        "visually_approved": report["visually_approved"],
        "needs_work": report["needs_work"],
        "independent_ground_truth_count": report["independent_ground_truth_count"],
        "output": str(args.output.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
