"""S04-A04: crash-recoverable, owner-bound, named multi-object PNG exports.

No model execution or implicit human acceptance. Outputs are atomically
published under the immutable S04-A02 namespace and a durable journal.
A process killed after file publication but before journal commit is safely
reconciled by recomputing the deterministic image SHA256, never overwritten.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .artifacts import atomic_text, temporary_sibling, verified_image
from .images import image_info, make_cutout, sha256
from .instance_binding import OwnerRegion, verify_owner_region_binding
from .instances import InstancePlan
from .schema import relative_name

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_JOURNAL = "_instance_export_journal.json"
_LOCK = "_instance_export.lock"


class InstanceExportRefused(ValueError):
    """The output namespace, prior journal or owner binding is unsafe or changed."""


@dataclass(frozen=True)
class BoundExport:
    """One existing owner selection; this does not authorize visual acceptance."""

    instance_id: str
    receipt: dict
    region: OwnerRegion
    candidate_masks: tuple[Path, ...]


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _safe_path(root: Path, relative: str) -> Path:
    try:
        if relative_name(relative) != relative:
            raise ValueError("noncanonical")
    except (ValueError, TypeError) as exc:
        raise InstanceExportRefused("invalid_output_namespace") from exc
    path = root / relative
    # Reject symlinks (including intermediate directories) and junction escapes.
    if path.absolute() != path.resolve():
        raise InstanceExportRefused("linked_or_escaped_output")
    for parent in (path, *path.parents):
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise InstanceExportRefused("linked_output_component")
    return path


@contextmanager
def _lock(root: Path):
    """Portable OS-held nonblocking lock released even after process termination.

    The marker file is intentionally not deleted. Unlinking a lock file allows
    another process to lock an unrelated inode while the first still works.
    """
    path = _safe_path(root, _LOCK)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    locked = False
    try:
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except (OSError, BlockingIOError) as exc:
            raise InstanceExportRefused("concurrent_instance_export") from exc
        yield
    finally:
        if locked:
            os.lseek(fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _initial_journal(plan: InstancePlan, manifest: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "kind": "bound_multi_instance_export",
        "plan_sha256": plan.identity_sha256,
        "source_sha256": plan.source_sha256,
        "manifest": manifest,
        "outputs": {
            item["instance_id"]: {"status": "pending", "sha256": None}
            for item in manifest
        },
        "visual_acceptance": "not_recorded",
    }


def _load_or_initialize(path: Path, expected: dict) -> dict:
    if path.is_symlink():
        raise InstanceExportRefused("linked_journal")
    if not path.exists():
        atomic_text(path, _canonical(expected) + "\n")
        return expected
    if not path.is_file():
        raise InstanceExportRefused("invalid_journal")
    try:
        recorded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise InstanceExportRefused("unreadable_journal") from exc
    if not isinstance(recorded, dict) or set(recorded) != set(expected):
        raise InstanceExportRefused("changed_journal_schema")
    if any(recorded[k] != expected[k] for k in expected if k != "outputs"):
        raise InstanceExportRefused("source_binding_or_plan_drift")
    outputs = recorded.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != set(expected["outputs"]):
        raise InstanceExportRefused("changed_journal_instances")
    for entry in outputs.values():
        if not isinstance(entry, dict) or set(entry) != {"status", "sha256"}:
            raise InstanceExportRefused("invalid_journal_output")
        if entry == {"status": "pending", "sha256": None}:
            continue
        if entry["status"] != "written" or not isinstance(entry["sha256"], str) or not _HEX.fullmatch(entry["sha256"]):
            raise InstanceExportRefused("invalid_journal_output")
    return recorded


def export_bound_instances(
    plan: InstancePlan, *,
    source: Path,
    selections: Sequence[BoundExport],
    destination_root: Path,
    on_checkpoint: Callable[[str, str], None] | None = None,
) -> dict:
    """Export all declared objects to immutable named PNGs and resume safely.

    A checkpoint callback is a testing hook; it can simulate abrupt process
    death after file publication and after journal persistence. It is never
    used to auto-accept or enqueue external work.
    """
    if not isinstance(plan, InstancePlan) or len(plan.instances) < 2:
        raise InstanceExportRefused("requires_multi_instance_plan")
    if not isinstance(selections, (tuple, list)) or len(selections) != len(plan.instances):
        raise InstanceExportRefused("all_planned_instances_must_be_bound")
    if not isinstance(source, Path) or not isinstance(destination_root, Path):
        raise InstanceExportRefused("invalid_local_paths")
    if destination_root.absolute() != destination_root.resolve() or destination_root.is_symlink():
        raise InstanceExportRefused("unsafe_export_root")
    if destination_root.exists() and not destination_root.is_dir():
        raise InstanceExportRefused("invalid_export_root")

    expected_ids = {item.instance_id for item in plan.instances}
    actual_ids = [item.instance_id for item in selections if isinstance(item, BoundExport)]
    if len(actual_ids) != len(selections) or set(actual_ids) != expected_ids or len(set(actual_ids)) != len(actual_ids):
        raise InstanceExportRefused("duplicate_or_missing_bound_instance")

    by_id = {item.instance_id: item for item in plan.instances}
    manifest: list[dict] = []
    selected_masks: dict[str, Path] = {}
    # All owner bindings and candidate files are verified BEFORE first write.
    for selection in selections:
        intent = by_id[selection.instance_id]
        if not isinstance(selection.receipt, dict):
            raise InstanceExportRefused("invalid_binding_record")
        verify_owner_region_binding(
            selection.receipt, plan, instance_id=selection.instance_id,
            source=source, candidate_masks=selection.candidate_masks,
            region=selection.region,
        )
        selected_sha = selection.receipt["selected_mask_sha256"]
        matches = [
            mask for mask in selection.candidate_masks
            if sha256(mask) == selected_sha
        ]
        if len(matches) != 1:
            raise InstanceExportRefused("changed_or_missing_selected_mask")
        selected_masks[selection.instance_id] = matches[0]
        manifest.append({
            "instance_id": intent.instance_id,
            "binding_sha256": selection.receipt["binding_sha256"],
            "selected_mask_sha256": selected_sha,
            "intended_output": intent.intended_output,
        })
    manifest.sort(key=lambda item: item["instance_id"])
    selected_digests = [item["selected_mask_sha256"] for item in manifest]
    if len(set(selected_digests)) != len(selected_digests):
        raise InstanceExportRefused("multiple_instances_share_one_mask")

    root = destination_root
    root.mkdir(parents=True, exist_ok=True)
    with _lock(root):
        outputs = {
            item["instance_id"]: _safe_path(root, item["intended_output"])
            for item in manifest
        }
        journal_path = _safe_path(root, _JOURNAL)
        # Refuse a dangerous namespace overlap even if the plan was altered.
        if len({str(p).casefold() for p in outputs.values()}) != len(outputs):
            raise InstanceExportRefused("duplicate_output_name")
        expected = _initial_journal(plan, manifest)
        # Existing outputs with NO journal are unattributed and may not be taken.
        if not journal_path.exists() and any(p.exists() or p.is_symlink() for p in outputs.values()):
            raise InstanceExportRefused("orphan_outputs_without_journal")
        journal = _load_or_initialize(journal_path, expected)
        # Prevalidate every committed output before creating any new output.
        for instance_id, output in outputs.items():
            entry = journal["outputs"][instance_id]
            if entry["status"] == "written":
                try:
                    verified_image(output, entry["sha256"])
                except (OSError, ValueError) as exc:
                    raise InstanceExportRefused("committed_output_tampered_or_missing") from exc
            elif output.is_symlink():
                raise InstanceExportRefused("pending_output_is_link")

        for item in manifest:
            instance_id = item["instance_id"]
            output = outputs[instance_id]
            entry = journal["outputs"][instance_id]
            if entry["status"] == "written":
                continue

            output.parent.mkdir(parents=True, exist_ok=True)
            if output.absolute() != output.resolve():
                raise InstanceExportRefused("linked_output_component")
            # Stage on the same filesystem. Publish with a create-only hardlink;
            # a crash between publication and journal write cannot overwrite.
            with temporary_sibling(output) as staged:
                make_cutout(source, selected_masks[instance_id], staged, refine=False)
                staged_info = image_info(staged)
                digest = staged_info["sha256"]
                if output.exists():
                    # Crash after promotion but before journal: reconstruct
                    # expected bytes and adopt only an exact SHA256 match.
                    try:
                        verified_image(output, digest)
                    except (OSError, ValueError) as exc:
                        raise InstanceExportRefused("uncommitted_output_hash_mismatch") from exc
                else:
                    try:
                        os.link(staged, output)
                    except FileExistsError as exc:
                        raise InstanceExportRefused("output_appeared_during_publication") from exc
                    if on_checkpoint:
                        on_checkpoint("after_publish", instance_id)
            journal["outputs"][instance_id] = {"status": "written", "sha256": digest}
            atomic_text(journal_path, _canonical(journal) + "\n")
            if on_checkpoint:
                on_checkpoint("after_journal", instance_id)

        # Exact acceptance here is output identity, not human cutout quality.
        result = {
            "schema_version": 1,
            "kind": "bound_multi_instance_export_result",
            "plan_sha256": plan.identity_sha256,
            "source_sha256": plan.source_sha256,
            "outputs": [
                {"instance_id": item["instance_id"],
                 "relative_path": item["intended_output"],
                 "sha256": journal["outputs"][item["instance_id"]]["sha256"]}
                for item in manifest
            ],
            "output_status": "written",
            "visual_acceptance": "not_recorded",
            "journal_sha256": hashlib.sha256(_canonical(journal).encode("utf-8")).hexdigest(),
        }
        return result
