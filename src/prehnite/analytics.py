"""Offline, snapshot-based analytics for a *single* production batch.

An attempt is a local stage invocation, not provider latency. A reservation is
not an invoice. Counts are independent of demo visual quality. This module
never uploads pixels, accesses the network, or loads optional dependencies.
"""
from __future__ import annotations

import csv
import html
import io
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from .artifacts import atomic_text
from .economics import batch_economics

SCHEMA_VERSION = 1
_ALLOWED_FAILURE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ALLOWED_PROVIDER = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_PAID_PROVIDERS = frozenset({"fal", "anthropic"})
_STATES = ("accepted", "failed_cutouts", "rejected", "error", "pending")
_STATUS_LABELS = {
    "accepted": "Accepted",
    "failed_cutouts": "Cutouts failed",
    "rejected": "Rejected",
    "error": "Error",
    "pending": "Pending",
}
_TYPES = ("local_source", "demo_or_model_generated")
_ASPECTS = ("1:1", "3:4", "4:3", "9:16", "16:9")


def _safe_code(value: object, fallback: str) -> str:
    """Only a narrow code vocabulary, never raw exception/URL strings."""
    return value if isinstance(value, str) and _ALLOWED_FAILURE.fullmatch(value) else fallback


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[math.ceil(0.95 * len(ordered)) - 1], 3)


def _count_rows(rows: list[dict], field: str) -> list[dict]:
    result = []
    for item in rows:
        observed = item["statuses"]
        result.append({
            "group": item[field],
            "requested": item["requested"],
            "accepted": observed.get("accepted", 0),
            "failed_cutouts": observed.get("failed_cutouts", 0),
            "rejected": observed.get("rejected", 0),
            "error": observed.get("error", 0),
            "pending": observed.get("pending", 0),
        })
    return result


def build_analytics(manifest: dict, results: dict, tasks: list[dict],
                    attempts: list[dict], economics: dict | None = None) -> dict:
    """Create a deterministic JSON-ready snapshot with no image/prompt/ID fields."""
    if not isinstance(results, dict):
        raise ValueError("Invalid batch asset results")
    if not isinstance(manifest, dict):
        raise ValueError("Invalid batch manifest")
    assets = manifest.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("Invalid manifest asset list")
    economics = economics if economics is not None else batch_economics(
        tasks, results, attempts
    )
    manifest_ids = set()
    status = Counter()
    by_input = defaultdict(lambda: {"requested": 0, "statuses": Counter()})
    by_ratio = defaultdict(lambda: {"requested": 0, "statuses": Counter()})
    failure = Counter()
    for asset in assets:
        if not isinstance(asset, dict) or not isinstance(asset.get("id"), str):
            raise ValueError("Invalid manifest asset")
        identifier = asset["id"]
        if identifier in manifest_ids:
            raise ValueError("Duplicate manifest asset")
        manifest_ids.add(identifier)
        row = results.get(identifier, {"status": "pending"})
        if not isinstance(row, dict):
            raise ValueError("Invalid asset result")
        state = row.get("status", "pending")
        state = state if state in _STATES else "pending"
        status[state] += 1
        kind = "local_source" if asset.get("source") else "demo_or_model_generated"
        ratio = asset.get("aspect_ratio", "unspecified")
        ratio = ratio if ratio in _ASPECTS else "unspecified"
        for group, key in ((by_input, kind), (by_ratio, ratio)):
            group[key]["requested"] += 1
            group[key]["statuses"][state] += 1
        if state not in ("accepted", "pending"):
            item = row.get("failure")
            code = _safe_code(item.get("code") if isinstance(item, dict) else None,
                              state)
            failure[code] += 1
    unexpected = sum(identifier not in manifest_ids for identifier in results)
    # A legacy journal without a manifest still displays its reported slots.
    if not assets:
        for row in results.values():
            if not isinstance(row, dict):
                raise ValueError("Invalid asset result")
            state = row.get("status", "pending")
            status[state if state in _STATES else "pending"] += 1
        unexpected = 0

    provider = defaultdict(lambda: {
        "operations": 0, "reserved_usd": 0.0,
        "tokens_in": 0, "tokens_out": 0,
        "attempts": 0, "unfinished": 0, "times": [],
    })
    task_keys = set()
    by_key = {}
    incomplete_stage = Counter()
    recovery_actions = Counter()
    for row in tasks:
        name = row["task_key"]
        if name in task_keys:
            raise ValueError("Duplicate operation key")
        task_keys.add(name)
        provider_name = row["provider"]
        provider_name = (provider_name if isinstance(provider_name, str)
                         and _ALLOWED_PROVIDER.fullmatch(provider_name)
                         else "unknown")
        by_key[name] = provider_name
        group = provider[provider_name]
        group["operations"] += 1
        group["reserved_usd"] += float(row["reserved_usd"])
        group["tokens_in"] += int(row["tokens_in"])
        group["tokens_out"] += int(row["tokens_out"])
        if row["status"] != "completed":
            incomplete_stage[_safe_code(row.get("status"), "unknown")] += 1
            # Conservative read-only operator hint, NOT a dispatch permission.
            if provider_name in _PAID_PROVIDERS:
                action = ("inspect_existing_request" if row.get("request_id")
                          else "manual_reconcile_before_retry")
            else:
                action = "inspect_nonpaid_stage"
            recovery_actions[action] += 1
    counts = Counter()
    for a in attempts:
        key = a["task_key"]
        if key not in by_key:
            raise ValueError("Orphan stage attempt")
        counts[key] += 1
        group = provider[by_key[key]]
        group["attempts"] += 1
        if a["outcome"] == "incomplete":
            group["unfinished"] += 1
        elif a["elapsed_ms"] is not None:
            group["times"].append(float(a["elapsed_ms"]))
    providers = []
    for name, values in sorted(provider.items()):
        durations = values["times"]
        providers.append({
            "provider": name,
            "operations": values["operations"],
            "reserved_usd": round(values["reserved_usd"], 6),
            "tokens_in": values["tokens_in"],
            "tokens_out": values["tokens_out"],
            "attempts_started": values["attempts"],
            "attempts_without_finished_timing": values["unfinished"],
            "observed_local_ms_p95": _p95(durations),
            "observed_local_ms_samples": len(durations),
        })
    retry_distribution = {
        "no_invocation_recorded": sum(counts.get(k, 0) == 0 for k in task_keys),
        "one_invocation": sum(counts.get(k, 0) == 1 for k in task_keys),
        "two_invocations": sum(counts.get(k, 0) == 2 for k in task_keys),
        "three_or_more": sum(counts.get(k, 0) >= 3 for k in task_keys),
    }
    required = len(assets) if assets else len(results)
    accepted = status["accepted"]
    return {
        "schema_version": SCHEMA_VERSION,
        "basis": "single_batch_local_journal_snapshot",
        "asset_scope": "manifest_slots_only",
        "required_assets": required,
        "processed_assets": required - status["pending"],
        "accepted_assets": accepted,
        "accepted_percent_of_required": (
            round(100 * accepted / required, 2) if required else None
        ),
        "unmatched_result_records": unexpected,
        "asset_status_counts": {key: status.get(key, 0) for key in _STATES},
        "input_mode": _count_rows(
            [{"input_mode": k, **v} for k, v in sorted(by_input.items())],
            "input_mode"
        ),
        "aspect_ratio": _count_rows(
            [{"aspect_ratio": k, **v} for k, v in sorted(by_ratio.items())],
            "aspect_ratio"
        ),
        "current_asset_failure_codes": dict(sorted(failure.items())),
        "current_unfinished_stage_states": dict(sorted(incomplete_stage.items())),
        "recovery_action_counts": dict(sorted(recovery_actions.items())),
        "retry_distribution": retry_distribution,
        "stages": economics["stages"],
        "providers": providers,
        "reserved_usd": economics["reserved_usd_total"],
        "reserved_usd_per_accepted_asset": economics["reserved_usd_per_accepted_asset"],
        "actual_invoiced_usd": None,
        "verified_invoice": False,
        "provider_reported_usd_partial_total": economics["provider_reported_usd_partial_total"],
        "total_tokens_in": sum(p["tokens_in"] for p in providers),
        "total_tokens_out": sum(p["tokens_out"] for p in providers),
        "warnings": [
            "Technical acceptance is not a human-calibrated visual-quality score.",
            "Reserved USD is an estimate, not a provider invoice.",
            "Observed durations measure local invocations only; missing timing remains unknown.",
            "No semantic content categories exist in manifest v1: grouping uses source type and aspect ratio.",
            "This report is a current snapshot, not historical incident frequency.",
        ],
    }


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _bar(label: str, quantity: int, total: int, *, tone: str = "good") -> str:
    pct = 100 * quantity / total if total else 0
    # Numeric input comes from validated counts, not CSS controlled by prompts.
    return (
        '<div class="metric-bar"><div class="metric-label"><span>'
        + _esc(label) + '</span><strong>' + str(quantity) + ' / ' + str(total)
        + '</strong></div><div class="track" role="img" aria-label="'
        + _esc(f"{label}: {quantity} of {total}")
        + '"><span class="fill fill-' + tone
        + '" style="width:' + f"{pct:.2f}" + '%"></span></div></div>'
    )


def render_analytics(stats: dict) -> str:
    """Server-render accessible charts. No JavaScript, CDN, external CSS."""
    states = stats["asset_status_counts"]
    required = stats["required_assets"]
    status_bars = "".join(
        _bar(_STATUS_LABELS[key], states[key], required,
             tone=("good" if key == "accepted" else
                   "neutral" if key == "pending" else "alert"))
        for key in _STATES
    )
    source_bars = "".join(
        _bar("Local source" if row["group"] == "local_source" else "Generated",
             row["accepted"], row["requested"])
        for row in stats["input_mode"]
    )
    aspect_bars = "".join(
        _bar(row["group"], row["accepted"], row["requested"])
        for row in stats["aspect_ratio"]
    )
    retry = stats["retry_distribution"]
    denominator = sum(retry.values())
    retry_bars = "".join(
        _bar(label, retry[key], denominator, tone="neutral")
        for key, label in (
            ("no_invocation_recorded", "0 (includes cache hits)"),
            ("one_invocation", "1 invocation"),
            ("two_invocations", "2 invocations"),
            ("three_or_more", "3+ invocations"),
        )
    )
    stage_rows = []
    for stage, row in sorted(stats["stages"].items()):
        p95 = row["observed_elapsed_ms_p95"]
        stage_rows.append(
            "<tr><th scope='row'>" + _esc(stage) + "</th>"
            + "<td>" + str(row["operations"]) + "</td>"
            + "<td>" + str(row["retry_attempts"]) + "</td>"
            + "<td>" + str(row["attempts_without_finished_timing"]) + "</td>"
            + "<td>" + ("unknown" if p95 is None else f"{p95:.3f}") + "</td>"
            + "<td>$" + f"{row['reserved_usd']:.6f}" + "</td></tr>"
        )
    provider_rows = []
    for row in stats["providers"]:
        p95 = row["observed_local_ms_p95"]
        provider_rows.append(
            "<tr><th scope='row'>" + _esc(row["provider"]) + "</th>"
            + "<td>" + str(row["operations"]) + "</td>"
            + "<td>" + str(row["attempts_started"]) + "</td>"
            + "<td>" + str(row["attempts_without_finished_timing"]) + "</td>"
            + "<td>" + ("unknown" if p95 is None else f"{p95:.3f}") + "</td>"
            + "<td>" + str(row["tokens_in"]) + " / " + str(row["tokens_out"]) + "</td>"
            + "<td>$" + f"{row['reserved_usd']:.6f}" + "</td></tr>"
        )
    failures = stats["current_asset_failure_codes"]
    failures_html = (
        "<ul class='failure-items'>"
        + "".join("<li><code>" + _esc(k) + "</code><strong>"
                  + str(v) + "</strong></li>" for k, v in failures.items())
        + "</ul>"
        if failures else "<p class='quiet'>No current non-accepted asset failures.</p>"
    )
    if stats["current_unfinished_stage_states"]:
        failures_html += (
            "<h3>Unfinished operation states</h3><ul class='failure-items'>"
            + "".join("<li><code>" + _esc(k) + "</code><strong>"
                      + str(v) + "</strong></li>"
                      for k, v in stats["current_unfinished_stage_states"].items())
            + "</ul>"
        )
    actions = stats["recovery_action_counts"]
    actions_html = (
        "<ul class='failure-items'>"
        + "".join("<li><code>" + _esc(k) + "</code><strong>"
                  + str(v) + "</strong></li>" for k, v in actions.items())
        + "</ul>" if actions else "<p class='quiet'>No unfinished operation guidance.</p>"
    )
    per_accepted = stats["reserved_usd_per_accepted_asset"]
    cost_label = ("undefined" if per_accepted is None else f"${per_accepted:.6f}")
    percent = stats["accepted_percent_of_required"]
    return (
        '<section id="analytics" class="analytics" aria-label="Batch analytics">'
        '<div class="analytics-top"><div><p class="eyebrow">BATCH INTELLIGENCE / V1</p>'
        '<h2>Production snapshot</h2><p class="quiet">Offline calculations from '
        'the local journal. No model quality, invoice or hardware claim.</p></div>'
        '<div class="kpis">'
        '<div class="kpi"><strong>' + str(stats["accepted_assets"])
        + ' / ' + str(required) + '</strong><span>Slots accepted</span></div>'
        '<div class="kpi"><strong>' + (
            "n/a" if percent is None else f"{percent:.1f}%")
        + '</strong><span>Required-slot completion</span></div>'
        '<div class="kpi"><strong>$' + f"{stats['reserved_usd']:.4f}"
        + '</strong><span>Reserved estimate, not billed</span></div>'
        '<div class="kpi"><strong>' + cost_label
        + '</strong><span>Reserved / accepted</span></div>'
        '</div></div>'
        '<div class="analytics-grid">'
        '<section class="analytics-panel"><h3>Delivery states</h3>' + status_bars
        + '</section><section class="analytics-panel"><h3>Source type</h3>' + source_bars
        + '<p class="small">No semantic categories in the manifest.</p>'
        + '</section><section class="analytics-panel"><h3>Aspect ratios</h3>' + aspect_bars
        + '</section><section class="analytics-panel"><h3>Operation attempts</h3>'
        + retry_bars + '<p class="small">Counts unique stage operations, not assets.'
          ' Zero invocations can include cache reuse or unstarted work.</p>'
        + '</section></div>'
        '<div class="analytics-grid">'
        '<section class="analytics-panel"><h3>Current failures</h3>' + failures_html
        + '<h3>Recovery guidance</h3>' + actions_html
        + '<p class="small">Read-only hints; never authorize new paid calls. '
          'Current snapshot, not historical failures.</p></section>'
        '<section class="analytics-panel"><h3>Cost provenance</h3>'
        '<p><strong>Verified invoice:</strong> unknown</p>'
        '<p><strong>Provider-reported partial amount:</strong> '
        + ("unknown" if stats["provider_reported_usd_partial_total"] is None
           else f"${stats['provider_reported_usd_partial_total']:.6f}")
        + '</p><p><strong>Input / output tokens:</strong> '
        + str(stats["total_tokens_in"]) + ' / ' + str(stats["total_tokens_out"])
        + '</p><p class="small">Tokens and estimates do not prove a charge. '
          'Actual provider invoices are not available.</p></section></div>'
        '<section class="analytics-panel"><h3>Stage efficiency</h3>'
        '<div class="table-scroll"><table><thead><tr><th>Stage</th><th>Operations</th>'
        '<th>Retries</th><th>Unknown timing</th><th>Observed p95 ms</th>'
        '<th>Reserved USD</th></tr></thead><tbody>'
        + "".join(stage_rows) + '</tbody></table></div>'
        '<p class="small">p95 covers observed local invocation and publication '
          'only; not remote inference time. Unknown durations are never zero.</p>'
        '</section><section class="analytics-panel"><h3>Provider breakdown</h3>'
        '<div class="table-scroll"><table><thead><tr><th>Provider</th>'
        '<th>Operations</th><th>Attempts</th><th>Unknown timing</th>'
        '<th>Observed p95 ms</th><th>Tokens in / out</th>'
        '<th>Reserved USD</th></tr></thead><tbody>'
        + "".join(provider_rows) + '</tbody></table></div></section>'
        '</section>'
    )


def write_analytics(root: Path, data: dict) -> None:
    """Versioned stable aggregate exports, free of prompt and request identifiers."""
    import json
    root = Path(root)
    atomic_text(root / "analytics.json",
                json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(("schema_version", "section", "group", "measure", "value", "unit"))
    version = data["schema_version"]
    for name in ("required_assets", "accepted_assets", "processed_assets",
                 "reserved_usd", "reserved_usd_per_accepted_asset"):
        writer.writerow((version, "summary", "batch", name,
                         "" if data[name] is None else data[name],
                         "USD" if name.startswith("reserved") else "assets"))
    for key, number in sorted(data["asset_status_counts"].items()):
        writer.writerow((version, "asset_status", key, "count", number, "assets"))
    for dimension in ("input_mode", "aspect_ratio"):
        for item in data[dimension]:
            for measure in ("requested", "accepted", "failed_cutouts", "rejected",
                            "error", "pending"):
                writer.writerow((version, dimension, item["group"],
                                 measure, item[measure], "assets"))
    for key, number in sorted(data["retry_distribution"].items()):
        writer.writerow((version, "retry_distribution", key, "operations", number,
                         "operations"))
    for key, number in sorted(data["current_asset_failure_codes"].items()):
        writer.writerow((version, "asset_failure_codes", key, "count", number, "assets"))
    for key, number in sorted(data["current_unfinished_stage_states"].items()):
        writer.writerow((version, "unfinished_stage_states", key, "count", number,
                         "operations"))
    for key, number in sorted(data["recovery_action_counts"].items()):
        writer.writerow((version, "recovery_action_counts", key, "count", number,
                         "operations"))
    for row in data["providers"]:
        for name in ("operations", "reserved_usd", "attempts_started",
                     "attempts_without_finished_timing", "observed_local_ms_p95",
                     "tokens_in", "tokens_out"):
            unit = "ms" if name.endswith("_ms_p95") else (
                "USD" if name == "reserved_usd" else
                "tokens" if name.startswith("tokens") else "operations")
            writer.writerow((version, "provider", row["provider"], name,
                             "" if row[name] is None else row[name], unit))
    for group, row in sorted(data["stages"].items()):
        for name in ("operations", "reserved_usd", "retry_attempts",
                     "attempts_without_finished_timing", "observed_elapsed_ms_p95"):
            unit = "ms" if name.endswith("_ms_p95") else (
                "USD" if name == "reserved_usd" else "operations")
            writer.writerow((version, "stage", group, name,
                             "" if row[name] is None else row[name], unit))
    atomic_text(root / "analytics.csv", buf.getvalue())
