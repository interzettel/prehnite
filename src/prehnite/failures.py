"""Versioned, non-secret failure/recovery facts for offline reports and agents.

A journal state is an observation, *not* evidence that a provider refunded,
finished or cancelled a billable request. Never infer retry authorization from
network exception text. This module does not dispatch or reconcile operations.
"""
from __future__ import annotations

import hashlib
from collections import Counter

TAXONOMY_VERSION = 1
PAID = frozenset({"fal", "anthropic"})


class RecoveryBlocked(RuntimeError):
    """A previous billable operation may have run and needs reconciliation."""


class BudgetExceeded(RuntimeError):
    """A further billable operation would exceed the owner's approved limit."""


def _record(code: str, category: str, action: str, *,
            stage: str, provider: str, request_id_present: bool = False) -> dict:
    if not isinstance(stage, str) or not isinstance(provider, str):
        raise ValueError("Failure stage/provider must be strings")
    return {
        "code": code,
        "category": category,
        "stage": stage,
        "provider": provider,
        "next_action": action,
        "paid_or_billable": provider in PAID,
        "request_id_present": bool(request_id_present),
        "automatic_resubmit_allowed": False,
    }


def classify_exception(exc: Exception, *, stage: str, provider: str,
                       request_id_present: bool = False) -> dict:
    """Classify typed exceptions; no secrets, raw paths or exception strings."""
    if isinstance(exc, BudgetExceeded):
        return _record("budget_limit", "policy", "request_budget_review",
                       stage=stage, provider=provider)
    if isinstance(exc, PermissionError):
        return _record("authorization_required", "policy", "obtain_explicit_consent",
                       stage=stage, provider=provider)
    if isinstance(exc, RecoveryBlocked):
        return _record("remote_reconciliation_required", "remote_recovery",
                       "inspect_existing_request" if request_id_present
                       else "manual_reconcile_before_retry",
                       stage=stage, provider=provider,
                       request_id_present=request_id_present)
    # ArtifactIntegrityError extends ValueError; recognize it first.
    from .artifacts import ArtifactIntegrityError
    if isinstance(exc, ArtifactIntegrityError):
        return _record("artifact_integrity", "integrity", "inspect_and_restore_artifact",
                       stage=stage, provider=provider)
    if isinstance(exc, (TimeoutError, ConnectionError)):
        if provider in PAID:
            return _record("remote_transport_uncertain", "remote_recovery",
                           "inspect_existing_request" if request_id_present
                           else "manual_reconcile_before_retry",
                           stage=stage, provider=provider,
                           request_id_present=request_id_present)
        return _record("local_transport_failure", "execution", "inspect_and_retry_nonpaid",
                       stage=stage, provider=provider)
    if isinstance(exc, ValueError):
        return _record("technical_validation", "validation", "inspect_invalid_artifact",
                       stage=stage, provider=provider)
    return _record("stage_execution_error", "execution",
                   "inspect_existing_request" if provider in PAID and request_id_present
                   else "manual_reconcile_before_retry" if provider in PAID
                   else "inspect_and_retry_nonpaid",
                   stage=stage, provider=provider,
                   request_id_present=request_id_present)


def classify_task(task: dict) -> dict | None:
    """Infer unresolved state from the persisted journal, including hard kills.

    A stage can be in 'submitting' after a crash *before* or *after* dispatch.
    Both are ambiguous: no automatic paid retry is permitted.
    """
    status = task.get("status")
    if status == "completed":
        return None
    stage = task.get("stage", "unknown")
    provider = task.get("provider", "unknown")
    rid = bool(task.get("request_id"))
    paid = provider in PAID
    if status in ("submitting", "uncertain") and paid:
        return _record(
            "remote_request_pending" if rid else "remote_submission_ambiguous",
            "remote_recovery",
            "inspect_existing_request" if rid else "manual_reconcile_before_retry",
            stage=stage, provider=provider, request_id_present=rid,
        )
    if status == "submitted" and paid:
        return _record(
            "remote_request_pending" if rid else "remote_submission_ambiguous",
            "remote_recovery",
            "inspect_existing_request" if rid else "manual_reconcile_before_retry",
            stage=stage, provider=provider, request_id_present=rid,
        )
    if status in ("running", "failed", "submitting", "submitted", "uncertain"):
        data = task.get("data") or {}
        if status == "failed" and isinstance(data.get("failure"), dict):
            failure = data["failure"]
            if failure.get("code") in (
                    "local_transport_failure", "technical_validation",
                    "stage_execution_error", "artifact_integrity"):
                return _record(failure["code"], failure["category"],
                               failure["next_action"], stage=stage, provider=provider)
        if paid:
            return _record("remote_submission_ambiguous", "remote_recovery",
                           "manual_reconcile_before_retry",
                           stage=stage, provider=provider, request_id_present=rid)
        return _record("local_stage_incomplete" if status == "running"
                       else "local_stage_failed",
                       "execution", "inspect_and_retry_nonpaid",
                       stage=stage, provider=provider)
    # Unknown persisted task states are not silently reclassified as safe.
    return _record("unknown_stage_state", "unknown", "manual_review",
                   stage=stage, provider=provider, request_id_present=rid)


def classify_asset(status: str, *, integrity_error: bool = False) -> dict | None:
    """Fallback for old saved results without a typed failure field."""
    if status == "accepted":
        return None
    if integrity_error:
        return _record("artifact_integrity", "integrity",
                       "inspect_and_restore_artifact", stage="asset", provider="local")
    mapping = {
        "failed_cutouts": ("cutout_validation_failed", "quality", "inspect_or_repair_cutout"),
        "rejected": ("asset_rejected", "quality", "inspect_or_adjust_quality_policy"),
        "error": ("asset_processing_error", "execution", "inspect_asset_stages"),
    }
    code, cat, act = mapping.get(status, ("asset_incomplete", "unknown", "inspect_asset"))
    return _record(code, cat, act, stage="asset", provider="local")


def summarize_failures(tasks: list[dict], results: dict) -> dict:
    """Deterministic public-safe aggregate; task identifiers are SHA256 only.

    Raw request IDs, exception messages, prompts and filesystem paths never
    enter this new summary. Existing legacy report fields are separate.
    """
    by_stage = Counter()
    by_asset = Counter()
    actions = Counter()
    pending = []
    for task in tasks:
        failure = classify_task(task)
        if failure is None:
            continue
        by_stage[failure["code"]] += 1
        actions[failure["next_action"]] += 1
        pending.append({
            "task_key_sha256": hashlib.sha256(
                task["task_key"].encode("utf-8")).hexdigest(),
            "status": task.get("status"),
            **failure,
        })
    for asset_id, row in sorted(results.items()):
        if not isinstance(row, dict):
            raise ValueError("Invalid asset result")
        failure = row.get("failure")
        if not isinstance(failure, dict) or row.get("status") == "accepted":
            failure = classify_asset(row.get("status", "not_processed"),
                                     integrity_error=bool(row.get("integrity_error")))
        if failure is None:
            continue
        by_asset[failure["code"]] += 1
        actions[failure["next_action"]] += 1
    return {
        "schema_version": TAXONOMY_VERSION,
        "stage_failure_counts": dict(sorted(by_stage.items())),
        "asset_failure_counts": dict(sorted(by_asset.items())),
        "next_action_counts": dict(sorted(actions.items())),
        "unresolved_operations": sorted(pending, key=lambda p: p["task_key_sha256"]),
        "warnings": [
            "A recovered stage ID is not permission to submit a second paid call.",
            "Unknown provider invoice amounts remain unknown.",
            "Failure counts are snapshot state, not a historical incident counter.",
        ],
    }
