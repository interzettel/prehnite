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
    from .gallery import export_gallery
    from .provenance import export_provenance
    export_gallery(journal)
    export_provenance(journal)
    return data


_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def _zip_add(archive: zipfile.ZipFile, name: str, body: bytes) -> None:
    """Use identical ZIP metadata across operating systems and source mtimes."""
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_DATE)
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, body, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def package(journal: Journal) -> Path:
    """Publish a deterministic archive with a digest manifest after verification."""
    results = journal.fact("results", {})
    selected = (journal.root / "selected").resolve()
    artifacts: dict[str, tuple[Path, str]] = {}
    for result in results.values():
        if result.get("status") != "accepted":
            continue
        hashes = result.get("outputs_sha256", {})
        for name in result.get("outputs", []):
            name = relative_name(name)
            if name in artifacts or name.startswith("_prehnite/"):
                raise ArtifactIntegrityError("Duplicate or reserved archive target")
            destination = (selected / name).resolve()
            if not destination.is_relative_to(selected):
                raise ArtifactIntegrityError("Unsafe archive destination")
            verified_image(destination, hashes.get(name))
            artifacts[name] = (destination, hashes[name])

    entries = {}
    for name, (source, expected) in sorted(artifacts.items()):
        verified_image(source, expected)
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ArtifactIntegrityError("Output changed during ZIP preflight: " + name)
        entries[name] = data
    for name in ("report.json", "operations.csv", "report.html", "gallery.html",
                 "provenance.json"):
        source = journal.root / name
        if source.is_file():
            entries["_prehnite/" + name] = source.read_bytes()

    # A portable digest list also covers the included reports; the top-level
    # manifest does not hash itself.
    manifest = {
        "schema_version": 1,
        "sha256": {
            name: hashlib.sha256(body).hexdigest()
            for name, body in sorted(entries.items())
        },
    }
    entries["_prehnite/archive-manifest.json"] = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")

    path = journal.root / f"prehnite-{journal.root.name}.zip"
    with temporary_sibling(path) as staged:
        with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, body in sorted(entries.items()):
                _zip_add(archive, name, body)
        with zipfile.ZipFile(staged) as archive:
            if archive.testzip() is not None:
                raise ArtifactIntegrityError("ZIP CRC validation failed")
            if archive.namelist() != sorted(entries):
                raise ArtifactIntegrityError("ZIP entry order changed")
            for name, expected in manifest["sha256"].items():
                if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise ArtifactIntegrityError("ZIP entry digest mismatch: " + name)
        os.replace(staged, path)
    return path
