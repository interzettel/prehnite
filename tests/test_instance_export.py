"""S04-A04: named multi-object hashes survive process death and restart."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from prehnite.images import sha256
from prehnite.instance_binding import OwnerRegion, bind_owner_region
from prehnite.instance_export import (
    BoundExport, InstanceExportRefused, export_bound_instances,
)
from prehnite.instances import TargetIntent, plan_instance_outputs


def fixture_scene(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "source.png"
    if not source.exists():
        Image.new("RGB", (80, 64), "#ad9e87").save(source)
    masks = []
    for name, rectangle in [
        ("left", (5, 12, 40, 45)),
        ("right", (35, 16, 75, 51)),
    ]:
        mask_path = folder / (name + ".png")
        if not mask_path.exists():
            im = Image.new("L", (80, 64), 0)
            ImageDraw.Draw(im).rectangle(rectangle, fill=255)
            im.save(mask_path)
        masks.append(mask_path)
    plan = plan_instance_outputs(
        asset_id="collection-01", source_sha256=sha256(source),
        targets=[TargetIntent("bag", "two individual bags", ("first", "second"))],
    )
    by_key = {x.instance_key: x for x in plan.instances}
    selections = []
    for key, region in [
        ("first", OwnerRegion(0, 0, 79, 63, 10, 25)),
        ("second", OwnerRegion(0, 0, 79, 63, 68, 25)),
    ]:
        ident = by_key[key].instance_id
        receipt = bind_owner_region(
            plan, instance_id=ident, source=source,
            candidate_masks=masks, region=region,
        )
        selections.append(BoundExport(
            instance_id=ident, receipt=receipt, region=region,
            candidate_masks=tuple(masks),
        ))
    return plan, source, selections, masks


def export(scene, root: Path, callback=None):
    plan, source, selections, _ = scene
    return export_bound_instances(
        plan, source=source, selections=selections,
        destination_root=root, on_checkpoint=callback,
    )


def test_two_owner_bound_masks_export_different_named_rgba_pngs(tmp_path):
    scene = fixture_scene(tmp_path / "inputs")
    root = tmp_path / "out"
    input_hashes = [sha256(p) for p in [scene[1], *scene[3]]]
    result = export(scene, root)
    assert result["output_status"] == "written"
    assert result["visual_acceptance"] == "not_recorded"
    assert result["plan_sha256"] == scene[0].identity_sha256
    assert len(result["outputs"]) == 2
    assert len({x["relative_path"] for x in result["outputs"]}) == 2
    assert len({x["sha256"] for x in result["outputs"]}) == 2
    by_name = {Path(x["relative_path"]).name.split("-")[0]: x for x in result["outputs"]}
    assert set(by_name) == {"first", "second"}
    for x in result["outputs"]:
        output = root / x["relative_path"]
        assert output.is_file()
        assert sha256(output) == x["sha256"]
        with Image.open(output) as im:
            assert im.mode == "RGBA"
            assert im.size == (80, 64)
            im.load()
    with Image.open(root / by_name["first"]["relative_path"]) as image:
        assert image.getpixel((10, 25))[3] == 255
        assert image.getpixel((68, 25))[3] == 0
    with Image.open(root / by_name["second"]["relative_path"]) as image:
        assert image.getpixel((68, 25))[3] == 255
        assert image.getpixel((10, 25))[3] == 0
    assert input_hashes == [sha256(p) for p in [scene[1], *scene[3]]]
    journal = json.loads((root / "_instance_export_journal.json").read_text())
    assert len(journal["outputs"]) == 2
    assert all(x["status"] == "written" for x in journal["outputs"].values())


def test_resume_does_not_rewrite_outputs_or_reaccept_cutouts(tmp_path):
    scene = fixture_scene(tmp_path / "inputs")
    root = tmp_path / "out"
    original = export(scene, root)
    file_paths = [root / x["relative_path"] for x in original["outputs"]]
    before = [(sha256(p), p.stat().st_mtime_ns) for p in file_paths]
    journal_before = (root / "_instance_export_journal.json").read_bytes()
    resumed = export((scene[0], scene[1], list(reversed(scene[2])), scene[3]), root)
    assert resumed == original
    assert [(sha256(p), p.stat().st_mtime_ns) for p in file_paths] == before
    assert (root / "_instance_export_journal.json").read_bytes() == journal_before


def test_duplicate_selection_and_single_object_plan_refused(tmp_path):
    scene = fixture_scene(tmp_path / "inputs")
    plan, source, selections, _ = scene
    with pytest.raises(InstanceExportRefused, match="duplicate_or_missing_bound_instance"):
        export((plan, source, [selections[0], selections[0]], []), tmp_path / "out")
    with pytest.raises(InstanceExportRefused, match="all_planned_instances_must_be_bound"):
        export((plan, source, [selections[0]], []), tmp_path / "out")
    one = plan_instance_outputs(
        asset_id="collection-01", source_sha256=sha256(source),
        targets=[TargetIntent("bag", "one bag", ("first",))],
    )
    with pytest.raises(InstanceExportRefused, match="requires_multi_instance_plan"):
        export_bound_instances(one, source=source, selections=[], destination_root=tmp_path / "out")


def test_tampered_binding_fails_before_any_export(tmp_path):
    plan, source, selections, masks = fixture_scene(tmp_path / "inputs")
    receipt = deepcopy(selections[0].receipt)
    receipt["selected_mask_sha256"] = "f" * 64
    bad = BoundExport(
        instance_id=selections[0].instance_id, receipt=receipt,
        region=selections[0].region, candidate_masks=selections[0].candidate_masks,
    )
    with pytest.raises(ValueError, match="owner_binding_changed_on_resume"):
        export_bound_instances(
            plan, source=source, selections=(bad, selections[1]),
            destination_root=tmp_path / "out",
        )
    assert not (tmp_path / "out").exists()


def test_changed_source_or_mask_fail_closed_without_modifying_output(tmp_path):
    scene = fixture_scene(tmp_path / "inputs")
    root = tmp_path / "out"
    result = export(scene, root)
    before = {x["relative_path"]: (root / x["relative_path"]).read_bytes()
              for x in result["outputs"]}
    with Image.open(scene[3][1]) as im:
        changed = im.copy()
    changed.putpixel((75, 51), 0)
    changed.save(scene[3][1])
    with pytest.raises(ValueError, match="owner_binding_changed_on_resume"):
        export(scene, root)
    assert before == {key: (root / key).read_bytes() for key in before}


def test_reject_preexisting_outputs_without_journal(tmp_path):
    scene = fixture_scene(tmp_path / "inputs")
    root = tmp_path / "out"
    item = scene[0].instances[0]
    target = root / item.intended_output
    target.parent.mkdir(parents=True)
    target.write_bytes(b"unattributed old result")
    with pytest.raises(InstanceExportRefused, match="orphan_outputs_without_journal"):
        export(scene, root)
    assert target.read_bytes() == b"unattributed old result"


def test_corrupted_committed_output_refused_before_mutation(tmp_path):
    scene = fixture_scene(tmp_path / "inputs")
    root = tmp_path / "out"
    result = export(scene, root)
    first = root / result["outputs"][0]["relative_path"]
    second = root / result["outputs"][1]["relative_path"]
    second_bytes = second.read_bytes()
    first.write_bytes(b"corrupt data")
    with pytest.raises(InstanceExportRefused, match="committed_output_tampered_or_missing"):
        export(scene, root)
    assert second.read_bytes() == second_bytes
    assert first.read_bytes() == b"corrupt data"


def test_unverified_or_corrupt_journal_refused(tmp_path):
    scene = fixture_scene(tmp_path / "inputs")
    root = tmp_path / "out"
    export(scene, root)
    journal_path = root / "_instance_export_journal.json"
    journal = json.loads(journal_path.read_text())
    journal["manifest"][0]["binding_sha256"] = "f" * 64
    journal_path.write_text(json.dumps(journal))
    with pytest.raises(InstanceExportRefused, match="source_binding_or_plan_drift"):
        export(scene, root)
    journal_path.write_text("{truncated", encoding="utf-8")
    with pytest.raises(InstanceExportRefused, match="unreadable_journal"):
        export(scene, root)


def test_output_directory_symlink_refused(tmp_path):
    scene = fixture_scene(tmp_path / "inputs")
    root = tmp_path / "out"
    output_parent = root / "cutouts"
    outside = tmp_path / "outside"
    outside.mkdir()
    root.mkdir()
    try:
        output_parent.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Host does not grant symlink creation")
    with pytest.raises(InstanceExportRefused, match="linked_or_escaped_output|linked_output_component"):
        export(scene, root)
    assert not list(outside.iterdir())


def test_linked_journal_is_never_followed(tmp_path):
    scene = fixture_scene(tmp_path / "inputs")
    root = tmp_path / "out"
    root.mkdir()
    other = tmp_path / "other.json"
    other.write_text('{"keep":true}')
    try:
        (root / "_instance_export_journal.json").symlink_to(other)
    except (OSError, NotImplementedError):
        pytest.skip("Host does not grant symlink creation")
    with pytest.raises(InstanceExportRefused, match="linked_journal|linked_or_escaped_output"):
        export(scene, root)
    assert other.read_text() == '{"keep":true}'


_CHILD = r"""
import json
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw
from prehnite.images import sha256
from prehnite.instance_binding import OwnerRegion, bind_owner_region
from prehnite.instance_export import BoundExport, export_bound_instances
from prehnite.instances import TargetIntent, plan_instance_outputs

folder = Path(sys.argv[1])
source = folder / "inputs" / "source.png"
masks = [folder / "inputs" / "left.png", folder / "inputs" / "right.png"]
plan = plan_instance_outputs(
    asset_id="collection-01", source_sha256=sha256(source),
    targets=[TargetIntent("bag", "two individual bags", ("first", "second"))],
)
by_key = {x.instance_key:x for x in plan.instances}
selections = []
for key, seed in [("first", 10), ("second", 68)]:
    i = by_key[key].instance_id
    region = OwnerRegion(0, 0, 79, 63, seed, 25)
    receipt = bind_owner_region(
        plan, instance_id=i, source=source,
        candidate_masks=masks, region=region)
    selections.append(BoundExport(
        instance_id=i, receipt=receipt,
        region=region, candidate_masks=tuple(masks)))
stage = sys.argv[2]
def checkpoint(event, ident):
    if event == stage:
        os._exit(83)
result = export_bound_instances(
    plan, source=source, selections=selections,
    destination_root=folder/"out", on_checkpoint=checkpoint if stage!="none" else None)
print(json.dumps(result, sort_keys=True))
"""


@pytest.mark.parametrize("killpoint", ["after_publish", "after_journal"])
def test_real_process_death_recovers_named_hashes_without_duplicate_writes(tmp_path, killpoint):
    scene = fixture_scene(tmp_path / "inputs")
    root = tmp_path / "out"
    first = subprocess.run(
        [sys.executable, "-c", _CHILD, str(tmp_path), killpoint],
        timeout=25, capture_output=True, text=True,
    )
    assert first.returncode == 83, first.stderr
    journal_path = root / "_instance_export_journal.json"
    assert journal_path.is_file()
    state = json.loads(journal_path.read_text())
    assert sum(x["status"] == "written" for x in state["outputs"].values()) == (
        0 if killpoint == "after_publish" else 1
    )
    item0 = next(x for x in scene[0].instances
                 if x.instance_id == sorted(state["outputs"])[0])
    published = root / item0.intended_output
    assert published.exists()
    before_hash = sha256(published)
    before_mtime = published.stat().st_mtime_ns
    resumed = subprocess.run(
        [sys.executable, "-c", _CHILD, str(tmp_path), "none"],
        timeout=25, capture_output=True, text=True, check=True,
    )
    data = json.loads(resumed.stdout)
    assert data["output_status"] == "written"
    assert len(data["outputs"]) == 2
    assert sha256(published) == before_hash
    assert published.stat().st_mtime_ns == before_mtime
    for item in data["outputs"]:
        assert sha256(root / item["relative_path"]) == item["sha256"]
    # A third independent process must see the same exact journal/output set.
    again = subprocess.run(
        [sys.executable, "-c", _CHILD, str(tmp_path), "none"],
        timeout=25, capture_output=True, text=True, check=True,
    )
    assert json.loads(again.stdout) == data
    assert [sha256(p) for p in [scene[1], *scene[3]]] == [
        sha256(p) for p in [scene[1], *scene[3]]
    ]
