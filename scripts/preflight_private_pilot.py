"""Verify a private local export of an R2 pilot without uploading image content.

Usage:
  python scripts/preflight_private_pilot.py --manifest private-r2.json \
      --data-root /path/to/downloaded-r2 --report /path/to/private-results.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prehnite.private_source_preflight import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.manifest, args.data_root, args.report)
    print(json.dumps({
        "decoded_source_count": result["decoded_source_count"],
        "roles": result["roles"],
        "ground_truth_masks_supplied": result["ground_truth_masks_supplied"],
        "mask_iou_calculated": result["mask_iou_calculated"],
        "local_byte_hashes_verified": result["local_byte_hashes_verified"],
        "private_report": str(args.report),
    }, indent=2))


if __name__ == "__main__":
    main()
