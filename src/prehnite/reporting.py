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
from .economics import batch_economics
from .failures import classify_task, summarize_failures
from .analytics import build_analytics, write_analytics


def export_report(journal: Journal) -> dict:
    rows = journal.tasks()
    results = journal.fact("results", {})
    attempts = journal.attempts()
    economics = batch_economics(rows, results, attempts)
    failure_summary = summarize_failures(rows, results)
    analytics = build_analytics(journal.fact("manifest", {}), results,
                               rows, attempts, economics)
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
        "economics": economics,
        "analytics": analytics,
        "failure_summary": failure_summary,
        "batch_failure": journal.fact("batch_failure"),
    }
    atomic_text(journal.root / "report.json",
                json.dumps(data, indent=2, ensure_ascii=False))
    with temporary_sibling(journal.root / "operations.csv") as temp:
        with temp.open("w", newline="", encoding="utf-8") as f:
            fields = ("task_key", "stage", "status", "provider", "model",
                      "reserved_usd", "tokens_in", "tokens_out", "request_id",
                      "path", "failure_code", "next_action")
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                failure = classify_task(row)
                values = {k: row.get(k) for k in fields}
                values["failure_code"] = failure["code"] if failure else ""
                values["next_action"] = failure["next_action"] if failure else ""
                writer.writerow(values)
        os.replace(temp, journal.root / "operations.csv")
    table_rows = "".join(
        "<tr><td>" + "</td><td>".join(html.escape(str(row.get(key, ""))) for key in
            ("task_key", "stage", "status", "provider", "reserved_usd", "tokens_in",
             "tokens_out")) + "</td></tr>" for row in rows
    )
    stage_rows = "".join(
        "<tr><td>" + html.escape(name) + "</td><td>"
        + "</td><td>".join(html.escape(str(values[field])) for field in (
            "reserved_usd", "attempts_started", "retry_attempts",
            "attempts_without_finished_timing", "observed_elapsed_ms_p95"))
        + "</td></tr>"
        for name, values in economics["stages"].items()
    )
    failure_rows = "".join(
        "<tr><td>" + html.escape(code) + "</td><td>"
        + str(count) + "</td></tr>"
        for code, count in failure_summary["asset_failure_counts"].items()
    )
    failure_stage_rows = "".join(
        "<tr><td>" + html.escape(code) + "</td><td>"
        + str(count) + "</td></tr>"
        for code, count in failure_summary["stage_failure_counts"].items()
    )
    cost_per_accepted = economics["reserved_usd_per_accepted_asset"]
    accepted_cost_label = ("undefined (no accepted assets)" if cost_per_accepted is None
                           else "$" + str(cost_per_accepted))
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
        + "</p><p>Accepted assets: " + str(economics["accepted_assets"])
        + "; reserved estimate per accepted asset: " + accepted_cost_label
        + ". These are <strong>reservations, not actual invoices</strong>. "
        + "Provider-billed amount: unknown. Observed local stage invocations: "
        + str(economics["attempts_with_observed_duration"])
        + "; unfinished/unknown timing: "
        + str(economics["attempts_without_finished_timing"])
        + ".</p><h2>Stage economics and local timing</h2>"
        + "<table><thead><tr><th>Stage</th><th>Reserved USD</th>"
        + "<th>Started attempts</th><th>Retries</th><th>Unknown timing</th>"
        + "<th>Observed p95 ms</th></tr></thead><tbody>"
        + stage_rows + "</tbody></table>"
        + "<p>Local measured invocation/publish time is not provider inference "
        + "latency or time spent waiting after a crash.</p>"
        + "<h2>Machine-readable failures and safe next actions</h2>"
        + "<p>Snapshot of unresolved stages; pending remote requests never imply "
          "permission to resubmit or that charges were reversed. See report.json "
          "for versioned codes and action counts.</p>"
        + "<h3>Assets</h3><table><tr><th>Code</th><th>Count</th></tr>"
        + failure_rows + "</table><h3>Stages</h3>"
        + "<table><tr><th>Code</th><th>Count</th></tr>"
        + failure_stage_rows + "</table>"
        + "<p>Acceptance state and errors: see report.json. "
          "Open gallery.html for the self-contained analytics and image dashboard. "
          "Exported analytics.json / analytics.csv use schema version 1.</p>"
          "<table><thead><tr>"
        + "".join(f"<th>{x}</th>" for x in ("Task", "Stage", "Status", "Provider",
                                            "Reserved USD", "Input tokens", "Output tokens"))
        + "</tr></thead><tbody>" + table_rows + "</tbody></table></html>"
    )
    atomic_text(journal.root / "report.html", page)
    from .gallery import export_gallery
    from .provenance import export_provenance
    write_analytics(journal.root, analytics)
    export_gallery(journal, analytics=analytics)
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


def package(journal: Journal, *, include_parquet: bool = False) -> Path:
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
                 "analytics.json", "analytics.csv", "provenance.json"):
        source = journal.root / name
        if source.is_file():
            entries["_prehnite/" + name] = source.read_bytes()

    if include_parquet:
        from .parquet_export import verified_parquet_entries
        entries.update(verified_parquet_entries(journal.root))

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
