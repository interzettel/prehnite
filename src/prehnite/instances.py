"""Deterministic, owner-declared instance identity *plans* (S04-A02).

This contract does not run segmentation, bind masks to instances, select a
candidate, write output images, or authorize any automatic acceptance.
Those steps belong to later S04 tasks.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from .schema import relative_name

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_KEY = re.compile(r"[a-z][a-z0-9-]{0,47}\Z")
_MAX_TARGETS = 32
_MAX_INSTANCES = 128


class InstancePlanRefused(ValueError):
    """Owner-declared target/instance identity is ambiguous or unsafe."""


@dataclass(frozen=True)
class TargetIntent:
    """Stable owner-declared target and *keys*, never detector indices."""

    target_id: str
    phrase: str
    instance_keys: tuple[str, ...]


@dataclass(frozen=True)
class PlannedInstance:
    target_id: str
    target_phrase: str
    instance_key: str
    instance_id: str
    intended_output: str


@dataclass(frozen=True)
class InstancePlan:
    asset_id: str
    source_sha256: str
    instances: tuple[PlannedInstance, ...]
    identity_sha256: str

    def to_record(self) -> dict:
        """A reproducible, serializable declaration; no mask or file selected."""
        return {
            "schema_version": 1,
            "kind": "instance_identity_plan",
            "asset_id": self.asset_id,
            "source_sha256": self.source_sha256,
            "instances": [asdict(item) for item in self.instances],
            "identity_sha256": self.identity_sha256,
            "binding_status": "unbound",
            "output_status": "not_written",
        }


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _safe_key(value: str, kind: str) -> str:
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise InstancePlanRefused(f"invalid_{kind}_key")
    try:
        relative_name(value)
    except ValueError as exc:
        raise InstancePlanRefused(f"unsafe_{kind}_key") from exc
    return value


def plan_instance_outputs(*, asset_id: str, source_sha256: str,
                          targets: Iterable[TargetIntent]) -> InstancePlan:
    """Map an immutable source and explicit owner keys to deterministic paths.

    The order in which a detector returns masks, or a caller provides target
    declarations, cannot affect the instance IDs, path names or plan hash.
    Changing a source, a target phrase, or an owner key changes identity
    rather than silently reusing an old accepted output.
    """
    asset = _safe_key(asset_id, "asset")
    if not isinstance(source_sha256, str) or not _SHA.fullmatch(source_sha256):
        raise InstancePlanRefused("invalid_source_sha256")
    if not isinstance(targets, (tuple, list)) or not 1 <= len(targets) <= _MAX_TARGETS:
        raise InstancePlanRefused("invalid_target_count")
    entries: list[PlannedInstance] = []
    targets_seen: set[str] = set()
    for target in targets:
        if not isinstance(target, TargetIntent):
            raise InstancePlanRefused("invalid_target_declaration")
        target_id = _safe_key(target.target_id, "target")
        if target_id in targets_seen:
            raise InstancePlanRefused("duplicate_target_id")
        targets_seen.add(target_id)
        if (not isinstance(target.phrase, str) or not 2 <= len(target.phrase) <= 160
                or target.phrase != target.phrase.strip()
                or not target.phrase.isprintable()):
            raise InstancePlanRefused("invalid_target_phrase")
        keys = target.instance_keys
        if not isinstance(keys, (tuple, list)) or not keys:
            raise InstancePlanRefused("missing_explicit_instance_keys")
        instance_seen: set[str] = set()
        for raw_key in keys:
            key = _safe_key(raw_key, "instance")
            if key in instance_seen:
                raise InstancePlanRefused("duplicate_instance_key")
            instance_seen.add(key)
            identity_material = {
                "schema_version": 1,
                "asset_id": asset,
                "source_sha256": source_sha256,
                "target_id": target_id,
                "target_phrase": target.phrase,
                "instance_key": key,
            }
            digest = hashlib.sha256(_canonical(identity_material)).hexdigest()
            path = f"cutouts/{asset}/{target_id}/{key}-{digest[:16]}.png"
            try:
                relative_name(path)
            except ValueError as exc:
                raise InstancePlanRefused("unsafe_intended_output") from exc
            entries.append(PlannedInstance(
                target_id=target_id, target_phrase=target.phrase,
                instance_key=key, instance_id=f"inst-{digest[:24]}",
                intended_output=path))
            if len(entries) > _MAX_INSTANCES:
                raise InstancePlanRefused("too_many_instances")
    entries.sort(key=lambda item: (item.target_id, item.instance_key))
    output_paths = [item.intended_output.casefold() for item in entries]
    instance_ids = [item.instance_id for item in entries]
    if len(set(output_paths)) != len(output_paths) or len(set(instance_ids)) != len(instance_ids):
        raise InstancePlanRefused("identity_or_output_collision")
    payload = {
        "schema_version": 1,
        "kind": "instance_identity_plan",
        "asset_id": asset,
        "source_sha256": source_sha256,
        "instances": [asdict(item) for item in entries],
    }
    return InstancePlan(
        asset_id=asset,
        source_sha256=source_sha256,
        instances=tuple(entries),
        identity_sha256=hashlib.sha256(_canonical(payload)).hexdigest(),
    )


def verify_instance_plan_record(plan: InstancePlan, recorded: Mapping) -> None:
    """Refuse an altered prior plan before future bind/export/resume work.

    A previous plan is a *declaration*, not proof that any output exists.
    """
    if not isinstance(recorded, dict) or recorded != plan.to_record():
        raise InstancePlanRefused("instance_plan_changed_on_resume")
