"""Export truthful production telemetry without inventing provider billing totals."""
from __future__ import annotations

import csv
import hashlib
import os
import html
import json
import zipfile
from pathlib import Path

from .artifacts import ArtifactIntegrityError, atomic_text, temporary_sibling, verified_image
from .schema import relative_name
from .store import Journal


def export_report(journal: Journal) -> dict:
    rows = journal.tasks()
    results = journal.fact("results", {})
    data = {
        "batch_id": journal.root.name,
        "cost_estimated_or_reserved_usd": round(journal.reserved(), 5),
        "cost_is_actual_invoice": False,
        "tokens_in": sum(r["tokens_in"] for r in rows),
        "tokens_out": sum(r["tokens_out"] for r in rows),
        "operations": len(rows),
        "completed_operations": sum(r["status"] == "completed" for r in rows),
        "asset_results": results,
        "operations_detail": rows,
    }
    atomic_text(journal.root / "report.json",
                json.dumps(data, indent=2, ensure_ascii=False))
    with temporary_sibling(journal.root / "operations.csv") as temp:
        with temp.open("w", newline="", encoding="utf-8") as f:
            fields = ("task_key", "stage", "status", "provider", "model",
                      "reserved_usd", "tokens_in", "tokens_out", "request_id", "path")
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k) for k in fields})
        os.replace(temp, journal.root / "operations.csv")
    table_rows = "".join(
        "<tr><td>" + "</td><td>".join(html.escape(str(row.get(key, ""))) for key in
            ("task_key", "stage", "status", "provider", "reserved_usd", "tokens_in",
             "tokens_out")) + "</td></tr>" for row in rows
    )
    page = (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width'><title>Prehnite report</title>"
        "<style>body{font:15px system-ui;max-width:1150px;margin:40px auto;padding:0 16px}"
        "table{border-collapse:collapse;width:100%}td,th{padding:8px;text-align:left;"
        "border-bottom:1px solid #ccc}tr:nth-child(even){background:#eee}"
        "code{overflow-wrap:anywhere}</style><h1>Prehnite · "
        + html.escape(journal.root.name)
        + "</h1><p>Reserved/estimated spend: $"
        + str(data["cost_estimated_or_reserved_usd"])
        + " (NOT verified provider billing). Tokens in/out: "
        + str(data["tokens_in"]) + "/" + str(data["tokens_out"])
        + "</p><p>Acceptance state and errors: see report.json.</p><table><thead><tr>"
        + "".join(f"<th>{x}</th>" for x in ("Task", "Stage", "Status", "Provider",
                                            "Reserved USD", "Input tokens", "Output tokens"))
        + "</tr></thead><tbody>" + table_rows + "</tbody></table></html>"
    )
    atomic_text(journal.root / "report.html", page)
    return data


def package(journal: Journal) -> Path:
    """Build a verified ZIP off to the side, then atomically publish it."""
    results = journal.fact("results", {})
    selected = (journal.root / "selected").resolve()
    artifacts = {}
    for result in results.values():
        if result.get("status") != "accepted":
            continue
        hashes = result.get("outputs_sha256", {})
        for name in result.get("outputs", []):
            name = relative_name(name)
            if name in artifacts:
                raise ArtifactIntegrityError("Duplicate archive target")
            destination = (selected / name).resolve()
            if not destination.is_relative_to(selected):
                raise ArtifactIntegrityError("Unsafe archive destination")
            verified_image(destination, hashes.get(name))
            artifacts[name] = (destination, hashes[name])

    path = journal.root / f"prehnite-{journal.root.name}.zip"
    with temporary_sibling(path) as staged:
        with zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, (source, expected_sha256) in sorted(artifacts.items()):
                verified_image(source, expected_sha256)
                archive.write(source, name)
            for name in ("report.json", "operations.csv", "report.html"):
                source = journal.root / name
                if source.is_file():
                    archive.write(source, "_prehnite/" + name)
        with zipfile.ZipFile(staged) as archive:
            if archive.testzip() is not None:
                raise ArtifactIntegrityError("ZIP checksum validation failed")
            for name, (_, expected) in artifacts.items():
                if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise ArtifactIntegrityError(f"ZIP entry has unexpected bytes: {name}")
        os.replace(staged, path)
    return path
