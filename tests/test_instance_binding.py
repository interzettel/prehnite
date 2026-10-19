"""S04-A03: explicit owner point inside a region binds one mask, never its neighbour."""
from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from prehnite.images import sha256
from prehnite.instance_binding import (
    InstanceBindingRefused,
    OwnerRegion,
    bind_owner_region,
    verify_owner_region_binding,
)
from prehnite.instances import TargetIntent, plan_instance_outputs


def scene(tmp_path: Path):
    source = tmp_path / "source.png"
    Image.new("RGB", (80, 64), (203, 191, 155)).save(source)
    masks = []
    for name, shape in [
        ("left", (7, 10, 43, 49)),
        ("right", (35, 14, 72, 52)),
    ]:
        mask = Image.new("L", (80, 64), 0)
        ImageDraw.Draw(mask).rectangle(shape, fill=255)
        path = tmp_path / f"{name}.png"
        mask.save(path)
        masks.append(path)
    plan = plan_instance_outputs(
        asset_id="tabletop", source_sha256=sha256(source),
        targets=[TargetIntent("mug", "two overlapping mugs", ("owner-left", "owner-right"))],
    )
    instances = {item.instance_key: item.instance_id for item in plan.instances}
    return source, masks, plan, instances


def selected(tmp_path, *, seed=(12, 22), masks=None, instance="owner-left"):
    source, originals, plan, names = scene(tmp_path)
    candidate_masks = originals if masks is None else masks
    return source, originals, plan, names, OwnerRegion(5, 5, 76, 58, *seed), candidate_masks


def test_owner_seed_binds_unique_left_mask_preserving_all_candidate_bytes(tmp_path):
    source, masks, plan, names, region, _ = selected(tmp_path)
    before = [sha256(path) for path in [source, *masks]]
    receipt = bind_owner_region(
        plan, instance_id=names["owner-left"], source=source,
        candidate_masks=masks, region=region,
    )
    assert receipt["selected_mask_sha256"] == sha256(masks[0])
    assert receipt["unselected_mask_sha256"] == [sha256(masks[1])]
    assert receipt["instance_id"] == names["owner-left"]
    assert receipt["intended_output"].startswith("cutouts/tabletop/mug/owner-left-")
    assert receipt["binding_status"] == "owner_region_bound"
    assert receipt["output_status"] == "not_written"
    assert receipt["visual_acceptance"] == "not_recorded"
    assert receipt["plan_sha256"] == plan.identity_sha256
    assert before == [sha256(path) for path in [source, *masks]]
    assert len(list(tmp_path.iterdir())) == 3  # Source and the two input masks only.


def test_bind_right_instance_without_editing_left_or_right_masks(tmp_path):
    source, masks, plan, names, _, _ = selected(tmp_path)
    region = OwnerRegion(5, 5, 76, 58, 65, 25)
    before = tuple(p.read_bytes() for p in masks)
    receipt = bind_owner_region(
        plan, instance_id=names["owner-right"], source=source,
        candidate_masks=masks, region=region,
    )
    assert receipt["selected_mask_sha256"] == sha256(masks[1])
    assert [x.read_bytes() for x in masks] == list(before)


def test_reordered_candidates_and_recreated_plan_produce_identical_receipt(tmp_path):
    source, masks, plan, names, region, _ = selected(tmp_path)
    receipt = bind_owner_region(
        plan, instance_id=names["owner-left"], source=source,
        candidate_masks=masks, region=region,
    )
    recomputed = plan_instance_outputs(
        asset_id="tabletop", source_sha256=sha256(source),
        targets=[TargetIntent("mug", "two overlapping mugs", ("owner-right", "owner-left"))],
    )
    other = bind_owner_region(
        recomputed, instance_id=names["owner-left"], source=source,
        candidate_masks=list(reversed(masks)), region=region,
    )
    assert other == receipt
    verify_owner_region_binding(
        receipt, plan, instance_id=names["owner-left"], source=source,
        candidate_masks=masks, region=region,
    )


def test_ambiguous_point_inside_both_masks_never_silently_selects(tmp_path):
    source, masks, plan, names, _, _ = selected(tmp_path)
    with pytest.raises(InstanceBindingRefused, match="multiple_masks_at_owner_seed"):
        bind_owner_region(
            plan, instance_id=names["owner-left"], source=source,
            candidate_masks=masks,
            region=OwnerRegion(5, 5, 76, 58, 40, 25),
        )


def test_empty_background_selection_refused(tmp_path):
    source, masks, plan, names, _, _ = selected(tmp_path)
    with pytest.raises(InstanceBindingRefused, match="no_mask_at_owner_seed"):
        bind_owner_region(
            plan, instance_id=names["owner-left"], source=source,
            candidate_masks=masks, region=OwnerRegion(0, 0, 79, 63, 2, 2),
        )


@pytest.mark.parametrize("region", [
    OwnerRegion(-1, 0, 70, 50, 10, 20),
    OwnerRegion(20, 10, 20, 40, 20, 25),
    OwnerRegion(0, 0, 81, 50, 10, 20),
    OwnerRegion(5, 5, 40, 40, 70, 20),
    OwnerRegion(5, 5, 40, 40, 40, 20),
    OwnerRegion(True, 5, 40, 40, 10, 20),
])
def test_invalid_owner_region_or_seed_refused(tmp_path, region):
    source, masks, plan, names, _, _ = selected(tmp_path)
    with pytest.raises(InstanceBindingRefused, match="region_|owner_seed_"):
        bind_owner_region(
            plan, instance_id=names["owner-left"], source=source,
            candidate_masks=masks, region=region,
        )


def test_wrong_instance_id_refused_even_when_seed_matches_mask(tmp_path):
    source, masks, plan, _, region, _ = selected(tmp_path)
    with pytest.raises(InstanceBindingRefused, match="unplanned_or_ambiguous_instance"):
        bind_owner_region(
            plan, instance_id="inst-" + "0" * 24,
            source=source, candidate_masks=masks, region=region,
        )


def test_source_changed_since_plan_refused_and_masks_left_intact(tmp_path):
    source, masks, plan, names, region, _ = selected(tmp_path)
    before = [p.read_bytes() for p in masks]
    Image.new("RGB", (80, 64), (0, 0, 0)).save(source)
    with pytest.raises(InstanceBindingRefused, match="source_identity_mismatch"):
        bind_owner_region(
            plan, instance_id=names["owner-left"], source=source,
            candidate_masks=masks, region=region,
        )
    assert before == [p.read_bytes() for p in masks]


def test_disconnected_candidate_mask_is_refused_even_when_seed_on_valid_component(tmp_path):
    source, masks, plan, names, region, _ = selected(tmp_path)
    with Image.open(masks[0]) as im:
        copy = im.copy()
    ImageDraw.Draw(copy).rectangle((0, 0, 2, 2), fill=255)
    copy.save(masks[0])
    with pytest.raises(InstanceBindingRefused, match="ambiguous_or_invalid_candidate_components"):
        bind_owner_region(
            plan, instance_id=names["owner-left"], source=source,
            candidate_masks=masks, region=region,
        )


def test_duplicate_mask_bytes_refused_not_two_independent_candidates(tmp_path):
    source, masks, plan, names, region, _ = selected(tmp_path)
    duplicate = tmp_path / "duplicate.png"
    duplicate.write_bytes(masks[0].read_bytes())
    with pytest.raises(InstanceBindingRefused, match="duplicate_candidate_bytes"):
        bind_owner_region(
            plan, instance_id=names["owner-left"], source=source,
            candidate_masks=[masks[0], duplicate, masks[1]], region=region,
        )


@pytest.mark.parametrize("variant", ["geometry", "channel", "empty", "full"])
def test_invalid_masks_fail_closed_without_changing_other_files(tmp_path, variant):
    source, masks, plan, names, region, _ = selected(tmp_path)
    untouched = masks[1].read_bytes()
    if variant == "geometry":
        invalid = Image.new("L", (79, 64), 0)
    elif variant == "channel":
        invalid = Image.new("RGB", (80, 64), (255, 0, 0))
    elif variant == "empty":
        invalid = Image.new("L", (80, 64), 0)
    else:
        invalid = Image.new("L", (80, 64), 255)
    invalid.save(masks[0])
    with pytest.raises(InstanceBindingRefused, match="invalid_mask_channel_or_geometry|ambiguous_or_invalid_candidate_components"):
        bind_owner_region(
            plan, instance_id=names["owner-left"], source=source,
            candidate_masks=masks, region=region,
        )
    assert masks[1].read_bytes() == untouched


def test_symlink_candidate_refused_if_host_supports_links(tmp_path):
    source, masks, plan, names, region, _ = selected(tmp_path)
    alias = tmp_path / "alias.png"
    try:
        alias.symlink_to(masks[0])
    except (OSError, NotImplementedError):
        pytest.skip("Host disallows symlinks")
    with pytest.raises(InstanceBindingRefused, match="unsafe_candidate_path"):
        bind_owner_region(
            plan, instance_id=names["owner-left"], source=source,
            candidate_masks=[alias, masks[1]], region=region,
        )


@pytest.mark.parametrize("edit", [
    lambda x: x.update(selected_mask_sha256="0" * 64),
    lambda x: x["unselected_mask_sha256"].clear(),
    lambda x: x["owner_region"].update(seed_x=65),
    lambda x: x.update(output_status="accepted"),
    lambda x: x.update(binding_sha256="0" * 64),
])
def test_modified_owner_receipt_refused_on_recheck(tmp_path, edit):
    source, masks, plan, names, region, _ = selected(tmp_path)
    receipt = bind_owner_region(
        plan, instance_id=names["owner-left"], source=source,
        candidate_masks=masks, region=region,
    )
    altered = deepcopy(receipt)
    edit(altered)
    with pytest.raises(InstanceBindingRefused, match="owner_binding_changed_on_resume"):
        verify_owner_region_binding(
            altered, plan, instance_id=names["owner-left"],
            source=source, candidate_masks=masks, region=region,
        )


def test_mutated_mask_between_binding_and_resume_is_rejected(tmp_path):
    source, masks, plan, names, region, _ = selected(tmp_path)
    record = bind_owner_region(
        plan, instance_id=names["owner-left"], source=source,
        candidate_masks=masks, region=region,
    )
    with Image.open(masks[1]) as im:
        changed = im.copy()
    changed.putpixel((70, 25), 0)
    changed.save(masks[1])
    with pytest.raises(InstanceBindingRefused, match="owner_binding_changed_on_resume"):
        verify_owner_region_binding(
            record, plan, instance_id=names["owner-left"], source=source,
            candidate_masks=masks, region=region,
        )


def test_binding_receipt_is_json_serializable_and_content_hash_binds_selection(tmp_path):
    source, masks, plan, names, region, _ = selected(tmp_path)
    record = bind_owner_region(
        plan, instance_id=names["owner-left"], source=source,
        candidate_masks=masks, region=region,
    )
    restored = json.loads(json.dumps(record, sort_keys=True))
    assert restored == record
    assert record["selected_mask_sha256"] != record["unselected_mask_sha256"][0]
    assert "path" not in record
    assert "mask_files" not in record
    assert "owner_region" in record
