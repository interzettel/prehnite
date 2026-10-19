"""Offline evaluation of a ten-image local generation pilot.

No inference, network, model downloads, GPU calls, payment or filesystem writes.
The result is an operator-reported scorecard, not an independent hardware
attestation or a product acceptance decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

from PIL import Image

from prehnite.manifest import load_manifest

SCHEMA_VERSION = 1
_ALLOWED = {"accept", "reject"}
_HEX = set("0123456789abcdef")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite(value: Any, *, upper: float | None = None, zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("measurement must be an actual numeric value")
    number = float(value)
    if not math.isfinite(number) or number < 0 or (not zero and number == 0):
        raise ValueError("measurement must be finite and nonnegative")
    if upper is not None and number > upper:
        raise ValueError("measurement exceeds permitted physical range")
    return number


def _digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX


def _date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        dt = datetime.fromisoformat(value)
        return dt.tzinfo is not None and dt.utcoffset() is not None
    except ValueError:
        return False


def plan(manifest: Path) -> dict:
    job = load_manifest(manifest)
    if len(job.assets) != 10:
        raise ValueError("The fixed pilot must contain exactly ten assets")
    if any(
        a.source or a.targets or not a.prompt or a.target_size != (768, 1024)
        or a.aspect_ratio != "3:4" or a.seed is None
        for a in job.assets
    ):
        raise ValueError("pilot expects ten generation-only seeded native-1K images")
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": job.id,
        "asset_count": len(job.assets),
        "provider_spend_permitted": False,
        "gpu_execution_authorized": False,
        "evidence_status": "plan_only",
        "review_dimensions": [
            "prompt_adherence", "composition", "material_and_edges", "usable_for_brief"
        ],
        "assets": [
            {"id": a.id, "output": a.output.image, "seed": a.seed,
             "size": list(a.target_size)}
            for a in job.assets
        ],
    }


def evaluate(manifest: Path, root: Path, receipt: Path) -> dict:
    spec = plan(manifest)
    batch = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(batch, dict) or batch.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid pilot receipt schema")
    if batch.get("batch_id") != spec["batch_id"]:
        raise ValueError("batch identity mismatch")
    if batch.get("origin") not in ("real_local_comfyui", "synthetic_demo"):
        raise ValueError("explicit real or synthetic origin required")
    if batch.get("authorization_receipt") is None and batch["origin"] == "real_local_comfyui":
        raise ValueError("real run requires explicit authorization receipt")
    if not isinstance(batch.get("operator"), str) or not batch["operator"].strip():
        raise ValueError("operator name or pseudonym required")
    if not isinstance(batch.get("reviewer"), str) or not batch["reviewer"].strip():
        raise ValueError("human reviewer required")
    if not _date(batch.get("reviewed_at")):
        raise ValueError("review timestamp must be timezone-aware")
    if not all(_digest(batch.get(key)) for key in ("model_sha256", "workflow_sha256")):
        raise ValueError("source model/workflow SHA256 declarations required")
    records = batch.get("assets")
    if not isinstance(records, list) or len(records) != 10:
        raise ValueError("one recorded review for each of ten images required")
    observed = {item["id"]: item for item in spec["assets"]}
    if not all(isinstance(r, dict) and isinstance(r.get("id"), str) for r in records):
        raise ValueError("malformed image review records")
    if set(r["id"] for r in records) != set(observed) or len({r["id"] for r in records}) != 10:
        raise ValueError("missing, duplicate or unexpected image id")
    root = root.resolve(strict=True)
    accepted = 0
    durations = []
    vram = []
    available_ram = []
    causes: dict[str, int] = {}
    seen_hashes: set[str] = set()
    for record in records:
        original = observed[record["id"]]
        if record.get("relative_output") != original["output"]:
            raise ValueError("output does not match manifest")
        result = (root / original["output"]).resolve(strict=True)
        if not result.is_relative_to(root) or not result.is_file():
            raise ValueError("output must remain inside the approved batch output root")
        declared = record.get("sha256")
        if not _digest(declared) or _sha256(result) != declared:
            raise ValueError("file digest missing or mismatched")
        if declared in seen_hashes:
            raise ValueError("two pilot images have identical output bytes")
        seen_hashes.add(declared)
        with Image.open(result) as image:
            image.verify()
        with Image.open(result) as image:
            if image.format != "PNG" or image.size != tuple(original["size"]):
                raise ValueError("image format or native resolution mismatch")
        decision = record.get("decision")
        if decision not in _ALLOWED:
            raise ValueError("each item needs explicit accept/reject human judgment")
        if decision == "accept":
            accepted += 1
        else:
            cause = record.get("failure_reason")
            if not isinstance(cause, str) or not cause.strip():
                raise ValueError("rejected items require a reason")
            causes[cause] = causes.get(cause, 0) + 1
        for dimension in spec["review_dimensions"]:
            value = record.get("rubric", {}).get(dimension)
            if type(value) is not int or not 1 <= value <= 5:
                raise ValueError("four explicit integer human rubric scores (1..5) required")
        durations.append(_finite(record.get("elapsed_seconds"), zero=False))
        vram.append(_finite(record.get("sampled_peak_vram_mib"), zero=False))
        available_ram.append(_finite(record.get("min_available_ram_mib"), zero=False))
    durations.sort()
    p95 = durations[math.ceil(0.95 * len(durations)) - 1]
    total_seconds = sum(durations)
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": spec["batch_id"],
        "origin": batch["origin"],
        "reviewed_images": 10,
        "accepted": accepted,
        "rejected": 10 - accepted,
        "accepted_yield_percent": round(accepted * 10, 1),
        "elapsed_total_seconds": round(total_seconds, 3),
        "median_seconds_per_image": round(median(durations), 3),
        "p95_seconds_per_image": round(p95, 3),
        "seconds_per_accepted_image": (
            round(total_seconds / accepted, 3) if accepted else None
        ),
        "sampled_peak_vram_mib": max(vram),
        "sampled_min_available_ram_mib": min(available_ram),
        "rejection_reasons": causes,
        "synthetic_eligible_for_product_acceptance": False,
        "independently_verified": False,
        "outcome": "operator_report_only; requires independent physical and human review",
        "model_workflow_provenance": "declared; local file hashes not independently attested",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planner = commands.add_parser("plan", help="show a safe, no-hardware pilot plan")
    planner.add_argument("--manifest", type=Path, required=True)
    scorer = commands.add_parser("evaluate", help="score privately reviewed local outputs")
    scorer.add_argument("--manifest", type=Path, required=True)
    scorer.add_argument("--outputs", type=Path, required=True)
    scorer.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = (
            plan(args.manifest) if args.command == "plan" else
            evaluate(args.manifest, args.outputs, args.receipt)
        )
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"pilot validation refused: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
