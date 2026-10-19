"""S04-A03: opt-in, fail-closed owner region -> planned instance binding.

The owner declares a rectangle and a point *inside* that rectangle. Exactly
one candidate mask must contain that point. This binds a selected existing
mask by content SHA256 to one S04-A02 instance, with all other masks untouched.
It neither generates masks nor exports, rewrites, or approves cutouts.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw

from .images import sha256
from .instances import InstancePlan, InstancePlanRefused

_MAX_MASKS = 128
_MAX_PIXELS = 12_000_000


class InstanceBindingRefused(ValueError):
    """Owner's region or mask evidence does not identify a unique instance."""


@dataclass(frozen=True)
class OwnerRegion:
    """Half-open image rectangle and explicit owner-chosen seed in image pixels."""

    x0: int
    y0: int
    x1: int
    y1: int
    seed_x: int
    seed_y: int

    def validate(self, size: tuple[int, int]) -> None:
        w, h = size
        if any(type(v) is not int for v in asdict(self).values()):
            raise InstanceBindingRefused("region_requires_integer_pixels")
        if not (0 <= self.x0 < self.x1 <= w and 0 <= self.y0 < self.y1 <= h):
            raise InstanceBindingRefused("owner_region_outside_source")
        if not (self.x0 <= self.seed_x < self.x1
                and self.y0 <= self.seed_y < self.y1):
            raise InstanceBindingRefused("owner_seed_outside_region")


def _safe_local_png(path: Path) -> Path:
    """Refuse link traversal: never read mask evidence through a mutable alias."""
    if not isinstance(path, Path) or path.suffix.lower() != ".png":
        raise InstanceBindingRefused("candidate_must_be_png")
    if not path.is_file() or path.is_symlink() or path.absolute() != path.resolve():
        raise InstanceBindingRefused("unsafe_candidate_path")
    return path


def _one_connected_foreground(mask: Image.Image) -> bool:
    """Threshold with four-neighbour semantics: a disjoint mask is ambiguous."""
    hard = mask.point(lambda value: 255 if value > 127 else 0)
    if hard.getextrema() != (0, 255):
        return False
    work = hard.copy()
    pixels = work.load()
    components = 0
    for y in range(work.height):
        for x in range(work.width):
            if pixels[x, y] == 255:
                components += 1
                if components > 1:
                    return False
                ImageDraw.floodfill(work, (x, y), 128, thresh=0)
    return components == 1


def bind_owner_region(
    plan: InstancePlan, *,
    instance_id: str,
    source: Path,
    candidate_masks: Sequence[Path],
    region: OwnerRegion,
) -> dict:
    """Return a content-bound, read-only selection receipt (never an export).

    Candidate ordering and filenames are not part of the chosen identity.
    Masks must already refer to independent, single connected instances.
    All candidate bytes, including unrelated masks, are preserved exactly.
    """
    if not isinstance(plan, InstancePlan):
        raise InstanceBindingRefused("missing_verified_instance_plan")
    try:
        from .instances import plan_instance_outputs, TargetIntent
        # Defend against a forged dataclass or changed derived instance IDs.
        by_target: dict[str, tuple[str, list[str]]] = {}
        for item in plan.instances:
            old = by_target.get(item.target_id)
            if old is not None and old[0] != item.target_phrase:
                raise InstanceBindingRefused("target_phrase_identity_conflict")
            if old is None:
                by_target[item.target_id] = (item.target_phrase, [item.instance_key])
            else:
                old[1].append(item.instance_key)
        rebuilt = plan_instance_outputs(
            asset_id=plan.asset_id, source_sha256=plan.source_sha256,
            targets=[TargetIntent(k, phrase, tuple(keys))
                     for k, (phrase, keys) in by_target.items()],
        )
        if rebuilt != plan:
            raise InstanceBindingRefused("tampered_instance_plan")
    except (InstancePlanRefused, TypeError, AttributeError) as exc:
        raise InstanceBindingRefused("invalid_instance_plan") from exc
    instances = [item for item in plan.instances if item.instance_id == instance_id]
    if len(instances) != 1:
        raise InstanceBindingRefused("unplanned_or_ambiguous_instance")
    chosen_intent = instances[0]
    if not isinstance(source, Path) or not source.is_file() or source.is_symlink():
        raise InstanceBindingRefused("missing_or_unsafe_source")
    if source.absolute() != source.resolve() or sha256(source) != plan.source_sha256:
        raise InstanceBindingRefused("source_identity_mismatch")
    try:
        with Image.open(source) as image:
            image.load()
            size = image.size
            if image.width * image.height > _MAX_PIXELS or image.width < 2 or image.height < 2:
                raise InstanceBindingRefused("unsupported_source_geometry")
            if image.getexif().get(274, 1) != 1:
                raise InstanceBindingRefused("unresolved_source_orientation")
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InstanceBindingRefused("invalid_source_image") from exc
    if not isinstance(region, OwnerRegion):
        raise InstanceBindingRefused("missing_owner_region")
    region.validate(size)
    if (not isinstance(candidate_masks, (list, tuple))
            or not 1 <= len(candidate_masks) <= _MAX_MASKS):
        raise InstanceBindingRefused("invalid_candidate_count")

    inventory: set[str] = set()
    seed_matches: list[str] = []
    for candidate in candidate_masks:
        path = _safe_local_png(candidate)
        digest = sha256(path)
        if digest in inventory:
            raise InstanceBindingRefused("duplicate_candidate_bytes")
        inventory.add(digest)
        try:
            with Image.open(path) as opened:
                if (opened.format != "PNG" or opened.mode != "L"
                        or opened.size != size):
                    raise InstanceBindingRefused("invalid_mask_channel_or_geometry")
                opened.load()
                if not _one_connected_foreground(opened):
                    raise InstanceBindingRefused("ambiguous_or_invalid_candidate_components")
                if opened.getpixel((region.seed_x, region.seed_y)) > 127:
                    seed_matches.append(digest)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise InstanceBindingRefused("invalid_candidate_mask") from exc

    if not seed_matches:
        raise InstanceBindingRefused("no_mask_at_owner_seed")
    if len(seed_matches) != 1:
        raise InstanceBindingRefused("multiple_masks_at_owner_seed")

    selected = seed_matches[0]
    sorted_inventory = sorted(inventory)
    receipt_body = {
        "schema_version": 1,
        "kind": "owner_region_instance_binding",
        "plan_sha256": plan.identity_sha256,
        "asset_id": plan.asset_id,
        "source_sha256": plan.source_sha256,
        "instance_id": chosen_intent.instance_id,
        "target_id": chosen_intent.target_id,
        "target_phrase": chosen_intent.target_phrase,
        "instance_key": chosen_intent.instance_key,
        "intended_output": chosen_intent.intended_output,
        "owner_region": asdict(region),
        "selected_mask_sha256": selected,
        "candidate_mask_sha256": sorted_inventory,
        "unselected_mask_sha256": [item for item in sorted_inventory if item != selected],
    }
    serialized = json.dumps(receipt_body, sort_keys=True, separators=(",", ":"))
    return {
        **receipt_body,
        "binding_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "binding_status": "owner_region_bound",
        "output_status": "not_written",
        "visual_acceptance": "not_recorded",
    }


def verify_owner_region_binding(
    record: dict, plan: InstancePlan, *,
    instance_id: str, source: Path, candidate_masks: Sequence[Path],
    region: OwnerRegion,
) -> None:
    """Recheck current source/mask bytes and reject a changed receipt on resume."""
    expected = bind_owner_region(
        plan, instance_id=instance_id, source=source,
        candidate_masks=candidate_masks, region=region,
    )
    if not isinstance(record, dict) or record != expected:
        raise InstanceBindingRefused("owner_binding_changed_on_resume")
