"""Truthful offline economics: spending *reservations* are not invoices.

Attempt measurements cover *observed local invocation+publish elapsed time*
only. Crashed/still-open attempts have unknown duration, not zero duration.
"""
from __future__ import annotations

import math
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from statistics import median


def _money(value):
    if isinstance(value, bool):
        raise ValueError("USD value must be numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("USD value must be numeric") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("USD value must be nonnegative and finite")
    return number


def _rounded(amount: Decimal | None) -> float | None:
    if amount is None:
        return None
    return float(amount.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def batch_economics(tasks: list[dict], results: dict, attempts: list[dict]) -> dict:
    """Summarize a snapshot without mixing cost, time, approval or invoice facts.

    One task row is a unique operation/reservation, even when multiple local
    attempts were needed. A failed acceptance still contributes to the cost
    per *accepted* asset. Unknown invoices/time measurements stay null.
    """
    if not isinstance(results, dict):
        raise ValueError("Batch results must be a JSON object")
    known_keys = set()
    by_stage = defaultdict(lambda: {
        "operations": 0, "reserved_usd": Decimal(0),
        "attempts_started": 0, "attempts_completed": 0,
        "attempts_failed": 0, "attempts_without_finished_timing": 0,
        "observed_elapsed_ms": [],
    })
    reserved = Decimal(0)
    reported = Decimal(0)
    reported_count = 0
    for task in tasks:
        key = task["task_key"]
        if key in known_keys:
            raise ValueError("Duplicate task key in economics snapshot")
        known_keys.add(key)
        stage = task["stage"]
        amount = _money(task["reserved_usd"])
        reserved += amount
        by_stage[stage]["reserved_usd"] += amount
        by_stage[stage]["operations"] += 1
        raw = task.get("data") or {}
        if "provider_reported_usd" in raw:
            reported += _money(raw["provider_reported_usd"])
            reported_count += 1

    per_key = defaultdict(int)
    unknown_count = 0
    measured = 0
    for item in attempts:
        key = item["task_key"]
        if key not in known_keys:
            raise ValueError("Attempt refers to unknown operation")
        stage = item["stage"]
        if stage != next(task["stage"] for task in tasks if task["task_key"] == key):
            raise ValueError("Attempt stage does not match task stage")
        count = by_stage[stage]
        count["attempts_started"] += 1
        per_key[key] += 1
        outcome = item["outcome"]
        elapsed = item.get("elapsed_ms")
        if outcome == "incomplete":
            if elapsed is not None:
                raise ValueError("Incomplete attempt cannot have a measured duration")
            unknown_count += 1
            count["attempts_without_finished_timing"] += 1
            continue
        if outcome not in ("completed", "failed") or elapsed is None:
            raise ValueError("Finished attempt requires outcome and duration")
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)):
            raise ValueError("Attempt duration must be numeric")
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("Invalid attempt duration")
        count["observed_elapsed_ms"].append(float(elapsed))
        count["attempts_" + outcome] += 1
        measured += 1

    total_accepted = sum(
        isinstance(asset, dict) and asset.get("status") == "accepted"
        for asset in results.values()
    )
    final_states = defaultdict(int)
    for asset in results.values():
        if not isinstance(asset, dict):
            raise ValueError("Asset result must be an object")
        final_states[asset.get("status", "unknown")] += 1

    stages = {}
    for name in sorted(by_stage):
        stage = by_stage[name]
        times = stage["observed_elapsed_ms"]
        stages[name] = {
            "operations": stage["operations"],
            "reserved_usd": _rounded(stage["reserved_usd"]),
            "attempts_started": stage["attempts_started"],
            "retry_attempts": sum(
                max(0, count - 1) for key, count in per_key.items()
                if next(t["stage"] for t in tasks if t["task_key"] == key) == name
            ),
            "attempts_completed": stage["attempts_completed"],
            "attempts_failed": stage["attempts_failed"],
            "attempts_without_finished_timing": stage["attempts_without_finished_timing"],
            "observed_elapsed_ms_total": round(sum(times), 3),
            "observed_elapsed_ms_median": round(median(times), 3) if times else None,
            "observed_elapsed_ms_p95": round(_p95(times), 3) if times else None,
        }

    return {
        "schema_version": 1,
        "cost_basis": "reserved estimates; may over- or understate invoice",
        "currency": "USD",
        "reserved_usd_total": _rounded(reserved),
        "provider_reported_usd_partial_total": (
            _rounded(reported) if reported_count else None
        ),
        "provider_reported_operation_count": reported_count,
        "actual_invoiced_usd_total": None,
        "actual_invoice_verified": False,
        "accepted_assets": total_accepted,
        "asset_status_counts": dict(sorted(final_states.items())),
        "reserved_usd_per_accepted_asset": _rounded(
            reserved / total_accepted if total_accepted else None
        ),
        "actual_invoiced_usd_per_accepted_asset": None,
        "attempts_started": len(attempts),
        "attempts_with_observed_duration": measured,
        "attempts_without_finished_timing": unknown_count,
        "retry_attempts": sum(max(0, count - 1) for count in per_key.values()),
        "timing_basis": "observed local stage invocation and publication; "
                        "not provider-internal latency, queue wait after a crash, "
                        "nor end-to-end batch wall time",
        "stages": stages,
    }
