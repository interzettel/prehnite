"""Explicit, opt-in and local-only Parquet datasets.

The core engine never imports PyArrow. A user must request export and install
prehnite[parquet]. No raw asset IDs, prompts, image bytes, paths, or provider
request IDs enter either dataset. Numbers have nullable, typed columns.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
from contextlib import ExitStack
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .analytics import _ASPECTS, _STATES, _safe_code, write_analytics
from .artifacts import ArtifactIntegrityError, atomic_text, temporary_sibling

PARQUET_SCHEMA_VERSION = 1
DATASETS = ("analytics.parquet", "asset-observations.parquet")
MANIFEST_FILE = "parquet-manifest.json"
_CSV_FIELDS = ["schema_version", "section", "group", "measure", "value", "unit"]
_TOKEN = re.compile(r"^[A-Za-z0-9_.:/-]{1,96}$")
_DECIMAL_SCALE = Decimal("0.000001")


def _arrow():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError(
            "Optional Parquet export requires PyArrow: "
            'install with pip install "prehnite[parquet]"'
        ) from exc
    return pa, pq


def _metadata(dataset: str) -> dict[bytes, bytes]:
    return {
        b"prehnite.dataset": dataset.encode("ascii"),
        b"prehnite.schema_version": b"1",
        b"prehnite.privacy": b"local_aggregate_no_raw_identifiers",
        b"prehnite.invoice": b"unknown_not_verified",
    }


def _metric_rows(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != _CSV_FIELDS:
        raise ValueError("Analytics CSV schema changed; refuse Parquet export")
    rows = []
    for item in reader:
        if item["schema_version"] != "1":
            raise ValueError("Unsupported analytics CSV version")
        for key in ("section", "group", "measure"):
            if not _TOKEN.fullmatch(item[key] or ""):
                raise ValueError("Unsafe analytics dimension in Parquet export")
        unit = item["unit"]
        raw = item["value"]
        count = amount = milliseconds = None
        if unit in ("assets", "operations", "tokens"):
            if raw:
                if not re.fullmatch(r"[0-9]+", raw):
                    raise ValueError("Invalid count value")
                count = int(raw)
                if count > 2**63 - 1:
                    raise ValueError("Count exceeds int64")
        elif unit == "USD":
            if raw:
                try:
                    amount = Decimal(raw)
                except InvalidOperation as exc:
                    raise ValueError("Invalid USD value") from exc
                if not amount.is_finite() or amount < 0:
                    raise ValueError("Invalid USD value")
                amount = amount.quantize(_DECIMAL_SCALE)
                if amount >= Decimal("100000000000000"):
                    raise ValueError("USD value exceeds decimal128 precision")
        elif unit == "ms":
            if raw:
                milliseconds = float(raw)
                if not math.isfinite(milliseconds) or milliseconds < 0:
                    raise ValueError("Invalid observed duration")
        else:
            raise ValueError("Unknown analytics unit in Parquet export")
        rows.append({
            "schema_version": 1,
            "section": item["section"],
            "group": item["group"],
            "measure": item["measure"],
            "unit": unit,
            "value_integer": count,
            "value_usd": amount,
            "value_ms": milliseconds,
        })
    return sorted(rows, key=lambda row: (
        row["section"], row["group"], row["measure"]
    ))


def _slot_rows(manifest: dict, results: dict) -> list[dict]:
    assets = manifest.get("assets", [])
    if not isinstance(assets, list) or not isinstance(results, dict):
        raise ValueError("Invalid manifest/results for Parquet snapshot")
    seen = set()
    rows = []
    for position, asset in enumerate(assets, 1):
        if not isinstance(asset, dict) or not isinstance(asset.get("id"), str):
            raise ValueError("Invalid manifest asset for Parquet snapshot")
        identifier = asset["id"]
        if identifier in seen:
            raise ValueError("Duplicate asset ID in Parquet snapshot")
        seen.add(identifier)
        result = results.get(identifier, {})
        if not isinstance(result, dict):
            raise ValueError("Invalid asset result in Parquet snapshot")
        status = result.get("status", "pending")
        if status not in _STATES:
            status = "pending"
        failure = result.get("failure")
        failure_code = None
        if status not in ("accepted", "pending"):
            failure_code = _safe_code(
                failure.get("code") if isinstance(failure, dict) else None,
                status)
        aspect = asset.get("aspect_ratio", "unspecified")
        if aspect not in _ASPECTS:
            aspect = "unspecified"
        outputs = result.get("outputs", [])
        if not isinstance(outputs, list):
            raise ValueError("Invalid selected outputs in Parquet snapshot")
        targets = asset.get("targets", [])
        if not isinstance(targets, list):
            raise ValueError("Invalid cutout targets in Parquet snapshot")
        rows.append({
            "schema_version": 1,
            "slot_ordinal": position,  # position only; never the raw asset ID
            "source_mode": ("local_source" if asset.get("source")
                            else "demo_or_model_generated"),
            "aspect_ratio": aspect,
            "status": status,
            "failure_code": failure_code,
            "requested_cutouts": len(targets),
            "selected_outputs": (len(outputs) if status in
                                 ("accepted", "failed_cutouts") else 0),
        })
    return rows


def write_parquet_exports(root: Path, analytics: dict,
                          manifest: dict, results: dict) -> dict:
    """Create a verified pair and digest sidecar; publish marker last.

    If writing either dataset fails, the old publication marker remains;
    package(include_parquet=True) rejects mismatched data instead of exposing
    a half-published pair. Do not call while a worker is writing the journal.
    """
    pa, pq = _arrow()
    if analytics.get("schema_version") != 1:
        raise ValueError("Unsupported analytics schema for Parquet export")
    root = Path(root)
    # Regenerate from the caller's validated analytics, never trust old CSV.
    write_analytics(root, analytics)
    csv_bytes = (root / "analytics.csv").read_text(encoding="utf-8")
    metric_rows = _metric_rows(csv_bytes)
    slot_rows = _slot_rows(manifest, results)
    metric_schema = pa.schema([
        pa.field("schema_version", pa.int16(), nullable=False),
        pa.field("section", pa.string(), nullable=False),
        pa.field("group", pa.string(), nullable=False),
        pa.field("measure", pa.string(), nullable=False),
        pa.field("unit", pa.string(), nullable=False),
        pa.field("value_integer", pa.int64()),
        pa.field("value_usd", pa.decimal128(20, 6)),
        pa.field("value_ms", pa.float64()),
    ], metadata=_metadata("metric_facts"))
    slot_schema = pa.schema([
        pa.field("schema_version", pa.int16(), nullable=False),
        pa.field("slot_ordinal", pa.int32(), nullable=False),
        pa.field("source_mode", pa.string(), nullable=False),
        pa.field("aspect_ratio", pa.string(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("failure_code", pa.string()),
        pa.field("requested_cutouts", pa.int16(), nullable=False),
        pa.field("selected_outputs", pa.int16(), nullable=False),
    ], metadata=_metadata("slot_observations"))
    tables = {
        DATASETS[0]: pa.Table.from_pylist(metric_rows, schema=metric_schema),
        DATASETS[1]: pa.Table.from_pylist(slot_rows, schema=slot_schema),
    }
    publication = {
        "schema_version": PARQUET_SCHEMA_VERSION,
        "basis": "local_opt_in_aggregate_no_raw_identifiers",
        "analytics_json_sha256": hashlib.sha256(
            (root / "analytics.json").read_bytes()).hexdigest(),
        "datasets": {},
    }
    with ExitStack() as stack:
        staged = {}
        for name, table in tables.items():
            target = root / name
            temp = stack.enter_context(temporary_sibling(target))
            pq.write_table(table, temp, compression="zstd", version="1.0",
                           write_statistics=True)
            metadata = pq.read_metadata(temp)
            if metadata.num_rows != table.num_rows:
                raise ArtifactIntegrityError("Parquet row count verification failed")
            if pq.read_table(temp).schema != table.schema:
                raise ArtifactIntegrityError("Parquet schema round-trip failed")
            publication["datasets"][name] = {
                "sha256": hashlib.sha256(temp.read_bytes()).hexdigest(),
                "rows": table.num_rows,
            }
            staged[name] = temp
        for name, temp in staged.items():
            os.replace(temp, root / name)
    # Commit marker LAST. A crash before this is rejected during packaging.
    atomic_text(root / MANIFEST_FILE,
                json.dumps(publication, sort_keys=True, indent=2) + "\n")
    return publication


def verified_parquet_entries(root: Path) -> dict[str, bytes]:
    """Verify the opt-in publication marker before archive inclusion.

    This only checks the SHA256 digest, row counts were verified at write time.
    It does not import PyArrow or attempt a remote lookup.
    """
    root = Path(root)
    manifest_path = root / MANIFEST_FILE
    if (not manifest_path.is_file() or
            not manifest_path.resolve().is_relative_to(root.resolve())):
        raise ArtifactIntegrityError("Parquet marker missing or outside batch root")
    try:
        publication = json.loads(manifest_path.read_text(encoding="utf-8"))
        if publication["schema_version"] != PARQUET_SCHEMA_VERSION:
            raise ValueError("Unexpected Parquet export schema")
        aggregate = root / "analytics.json"
        if not aggregate.resolve().is_relative_to(root.resolve()):
            raise ValueError("Analytics snapshot escapes batch root")
        actual = hashlib.sha256(aggregate.read_bytes()).hexdigest()
        if actual != publication["analytics_json_sha256"]:
            raise ValueError("Parquet metrics are stale relative to analytics.json")
        entries = {}
        for name in DATASETS:
            source = root / name
            item = publication["datasets"][name]
            body = source.read_bytes()
            if (len(body) < 8 or body[:4] != b"PAR1" or body[-4:] != b"PAR1"
                    or hashlib.sha256(body).hexdigest() != item["sha256"]
                    or not isinstance(item["rows"], int) or item["rows"] < 0):
                raise ValueError("Parquet dataset missing or digest invalid")
            entries["_prehnite/" + name] = body
        entries["_prehnite/" + MANIFEST_FILE] = manifest_path.read_bytes()
        return entries
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise ArtifactIntegrityError("Parquet opt-in snapshot integrity check failed") from exc
