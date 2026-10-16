"""Score locally supplied photographs against a separately reviewed alpha matte.

No automatic downloads, hosted inference, image uploads or publication.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prehnite.real_cutout_eval import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Local JSON manifest with permissions and SHA256 receipts")
    parser.add_argument("--data-root", type=Path, required=True,
                        help="Private directory containing already-permitted images")
    parser.add_argument("--report", type=Path, required=True,
                        help="Path for PRIVATE text-only JSON report, outside data root")
    args = parser.parse_args()
    result = run(args.manifest, args.data_root, args.report)
    print(json.dumps({
        "count": result["count"],
        "per_cohort": result["per_cohort"],
        "rights_independently_verified": result["rights_independently_verified"],
        "human_visual_acceptance_established": result["human_visual_acceptance_established"],
        "private_report": str(args.report.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
