"""Offline P08-A03 planning, simulation and evidence validation.

This CLI is hardware-free. It never imports ComfyUI, Torch or CUDA and has no
run/execute command. A real hardware experiment requires separate owner
authorization and a private runner.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prehnite.benchmark_evidence import (
    experiment_plan,
    simulated_fallback_scenarios,
    validate_evidence,
)


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan", help="print the proposed bounded experiment")
    subparsers.add_parser(
        "simulate-fallbacks", help="print deterministic offline fallback scenarios"
    )
    validate = subparsers.add_parser(
        "validate", help="validate a completed evidence JSON bundle"
    )
    validate.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)

    if args.command == "plan":
        _print(experiment_plan())
        return 0
    if args.command == "simulate-fallbacks":
        _print(simulated_fallback_scenarios())
        return 0
    payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    report = validate_evidence(payload)
    _print(report)
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
