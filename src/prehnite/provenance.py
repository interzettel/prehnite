"""Reproducible, privacy-minimizing provenance for accepted batch artifacts.

Do not export raw prompts, original input paths, cloud URLs, API keys or
provider request IDs. The private SQLite journal retains operational details.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .artifacts import ArtifactIntegrityError, verified_image
from .schema import relative_name
from .store import Journal

PROVENANCE_SCHEMA = 1
_ATTEMPT = re.compile(r":a([1-9][0-9]*):")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_stage(row: dict, asset: dict) -> dict:
    data = row.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError("Invalid journal stage data")
    trace = {
        "task_key_sha256": _digest(row["task_key"]),
        "stage": row["stage"],
        "state": row["status"],
        "provider": row["provider"],
        "model": row["model"],
        "request_id_sha256": _digest(row["request_id"]) if row["request_id"] else None,
        "artifact_sha256": data.get("artifact_sha256"),
        "reserved_usd_estimate": row["reserved_usd"],
    }
    match = _ATTEMPT.search(row["task_key"])
    if match and row["stage"] == "generation":
        base = asset.get("seed")
        if base is None:
            base = int(_digest(asset["id"])[:8], 16)
        trace["requested_seed"] = base + int(match.group(1)) - 1
    # Include only typed and bounded verdict fields, never free-form notes,
    # remote response objects, or embedded image data.
    if row["stage"] == "judge" and row["status"] == "completed":
        scores = data.get("scores")
        if isinstance(scores, dict):
            trace["rubric_scores"] = {
                key: score for key, score in sorted(scores.items())
                if key in ("A", "B") and type(score) in (int, float)
            }
        if data.get("winner") in ("A", "B", "tie", "neither"):
            trace["rubric_winner"] = data["winner"]
    return trace


def build_provenance(journal: Journal) -> dict:
    manifest = journal.fact("manifest", {})
    assets = manifest.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("Missing batch manifest")
    fingerprints = journal.fact("input_file_sha256")
    if fingerprints is None:
        # Old batches may contain input photos without a trusted historical
        # digest. Refuse silently introducing unverifiable provenance.
        if any(a.get("source") for a in assets):
            raise ArtifactIntegrityError(
                "Existing input batch has no historical source fingerprints; "
                "start a new batch after verifying original inputs")
        fingerprints = {}
    results = journal.fact("results", {})
    by_asset = []
    tasks = journal.tasks()
    root = (journal.root / "selected").resolve()
    for asset in assets:
        asset_id = asset["id"]
        result = results.get(asset_id, {})
        entries = []
        for name in sorted(result.get("outputs", [])):
            relative = relative_name(name)
            if result.get("status") not in ("accepted", "failed_cutouts"):
                break
            expected = result.get("outputs_sha256", {}).get(relative)
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ArtifactIntegrityError("Selected output escapes batch root")
            info = verified_image(path, expected)
            entries.append({
                "name": relative,
                "sha256": info["sha256"],
                "width": info["width"], "height": info["height"],
                "mode": info["mode"], "bytes": path.stat().st_size,
            })
        asset_tasks = [
            _safe_stage(row, asset) for row in tasks
            if row["task_key"].startswith(asset_id + ":")
        ]
        # Journal has no explicit task timestamps reliable at sub-second
        # granularity. Sort stable stage identifiers rather than update time.
        asset_tasks.sort(key=lambda row: row["task_key_sha256"])
        by_asset.append({
            "id": asset_id,
            "input_kind": "original" if asset.get("source") else "prompt",
            "input_sha256": fingerprints.get(asset_id) if asset.get("source") else None,
            "source_reference_sha256": _digest(asset["source"]) if asset.get("source") else None,
            "prompt_sha256": _digest(asset["prompt"]) if asset.get("prompt") else None,
            "requested_target_size": asset["target_size"],
            "status": result.get("status", "not_processed"),
            "winning_variant": result.get("winning_variant"),
            "attempt": result.get("attempt"),
            "visual_quality_verified": bool(result.get("visual_quality_verified", False)),
            "quality_score_uncalibrated": result.get("quality_score"),
            "outputs": entries,
            "stages": asset_tasks,
        })
    return {
        "schema_version": PROVENANCE_SCHEMA,
        "batch_id": journal.root.name,
        "configuration_sha256": journal.fact("configuration_sha256"),
        "cost_is_actual_invoice": False,
        "cost_estimated_or_reserved_usd": round(journal.reserved(), 5),
        "inputs_and_outputs": by_asset,
        "privacy": {
            "raw_prompts": "omitted",
            "source_paths": "sha256 only",
            "provider_request_ids": "sha256 only; private journal retains IDs",
            "credentials_and_provider_urls": "omitted",
        },
        "quality_certification": "none; visual judge scores are uncalibrated",
    }


def export_provenance(journal: Journal) -> dict:
    from .artifacts import atomic_text

    document = build_provenance(journal)
    atomic_text(journal.root / "provenance.json",
                json.dumps(document, ensure_ascii=False, sort_keys=True,
                           indent=2, allow_nan=False) + "\n")
    return document
