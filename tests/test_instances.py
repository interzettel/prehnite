"""S04-A02: stable owner-declared instance names, hierarchies and retry identities."""
from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from prehnite.instances import (
    InstancePlanRefused,
    TargetIntent,
    plan_instance_outputs,
    verify_instance_plan_record,
)

SOURCE = "a" * 64


def plan(*, targets=None, source=SOURCE, asset="product-01"):
    if targets is None:
        targets = [
            TargetIntent("bag", "backpack", ("back-left", "back-right")),
            TargetIntent("handle", "bag handle", ("top-loop",)),
        ]
    return plan_instance_outputs(asset_id=asset, source_sha256=source, targets=targets)


def test_hierarchy_namespaces_individual_outputs_without_filesystem_writes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = plan()
    assert len(result.instances) == 3
    assert [x.instance_key for x in result.instances] == [
        "back-left", "back-right", "top-loop",
    ]
    assert all(x.instance_id.startswith("inst-") for x in result.instances)
    assert len({x.instance_id for x in result.instances}) == 3
    assert len({x.intended_output for x in result.instances}) == 3
    assert result.instances[0].intended_output.startswith(
        "cutouts/product-01/bag/back-left-"
    )
    assert result.instances[2].intended_output.startswith(
        "cutouts/product-01/handle/top-loop-"
    )
    assert all(x.intended_output.endswith(".png") for x in result.instances)
    assert list(tmp_path.iterdir()) == []  # No export is performed by planning
    record = result.to_record()
    assert record["binding_status"] == "unbound"
    assert record["output_status"] == "not_written"


def test_declared_instance_and_target_order_do_not_change_identity_or_output():
    original = plan()
    reversed_order = plan(targets=[
        TargetIntent("handle", "bag handle", ("top-loop",)),
        TargetIntent("bag", "backpack", ("back-right", "back-left")),
    ])
    assert original == reversed_order
    assert original.to_record() == reversed_order.to_record()
    assert original.identity_sha256 == reversed_order.identity_sha256


def test_multiple_instances_with_same_phrase_cannot_share_identity():
    result = plan(targets=[
        TargetIntent("shoe", "red sneaker", ("first", "second"))
    ])
    first, second = result.instances
    assert first.target_phrase == second.target_phrase
    assert first.instance_id != second.instance_id
    assert first.intended_output != second.intended_output


def test_same_explicit_key_under_different_targets_is_separately_namespaced():
    result = plan(targets=[
        TargetIntent("person", "person", ("first",)),
        TargetIntent("bag", "backpack", ("first",)),
    ])
    assert result.instances[0].instance_id != result.instances[1].instance_id
    assert result.instances[0].intended_output != result.instances[1].intended_output


def test_restart_record_verification_preserves_plan_without_acceptance(tmp_path):
    original = plan()
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(original.to_record(), sort_keys=True), encoding="utf-8")
    prior = json.loads(path.read_text(encoding="utf-8"))
    resumed = plan(targets=[
        TargetIntent("handle", "bag handle", ("top-loop",)),
        TargetIntent("bag", "backpack", ("back-right", "back-left")),
    ])
    verify_instance_plan_record(resumed, prior)
    assert prior == resumed.to_record()
    assert prior["binding_status"] == "unbound"
    assert prior["output_status"] == "not_written"


def test_new_interpreter_recomputes_exact_original_identity_and_paths():
    code = (
        "import json; from prehnite.instances import TargetIntent,plan_instance_outputs;"
        "x=plan_instance_outputs(asset_id='product-01',source_sha256='"
        + SOURCE +
        "',targets=[TargetIntent('handle','bag handle',('top-loop',)),"
        "TargetIntent('bag','backpack',('back-right','back-left'))]);"
        "print(json.dumps(x.to_record(),sort_keys=True))"
    )
    run = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, check=True, timeout=15,
    )
    assert json.loads(run.stdout) == plan().to_record()


@pytest.mark.parametrize("change", [
    lambda d: d.update(asset_id="other-asset"),
    lambda d: d.update(source_sha256="b" * 64),
    lambda d: d["instances"][0].update(instance_id="inst-" + "0" * 24),
    lambda d: d["instances"][0].update(intended_output="../../escape.png"),
    lambda d: d["instances"].reverse(),
    lambda d: d.update(binding_status="selected"),
    lambda d: d.update(output_status="written"),
])
def test_modified_resume_record_is_rejected(change):
    p = plan()
    altered = deepcopy(p.to_record())
    change(altered)
    with pytest.raises(InstancePlanRefused, match="instance_plan_changed_on_resume"):
        verify_instance_plan_record(p, altered)


def test_source_target_phrase_and_owner_key_changes_change_identities():
    base = plan(targets=[TargetIntent("shoe", "red sneaker", ("left",))])
    alternate_source = plan(source="b" * 64, targets=[
        TargetIntent("shoe", "red sneaker", ("left",))
    ])
    alternate_phrase = plan(targets=[
        TargetIntent("shoe", "blue sneaker", ("left",))
    ])
    alternate_key = plan(targets=[
        TargetIntent("shoe", "red sneaker", ("right",))
    ])
    for candidate in (alternate_source, alternate_phrase, alternate_key):
        assert candidate.identity_sha256 != base.identity_sha256
        assert candidate.instances[0].instance_id != base.instances[0].instance_id
        assert candidate.instances[0].intended_output != base.instances[0].intended_output


@pytest.mark.parametrize(("targets", "reason"), [
    ([], "invalid_target_count"),
    ([TargetIntent("bag", "backpack", ())], "missing_explicit_instance_keys"),
    ([TargetIntent("bag", "backpack", ("one", "one"))], "duplicate_instance_key"),
    ([TargetIntent("bag", "backpack", ("one",)),
      TargetIntent("bag", "backpack", ("two",))], "duplicate_target_id"),
    ([TargetIntent("bag", "backpack", ("1",))], "invalid_instance_key"),
    ([TargetIntent("bag", "backpack", ("../one",))], "invalid_instance_key"),
    ([TargetIntent("bag", "backpack", ("CON",))], "invalid_instance_key"),
    ([TargetIntent("bag", "backpack", ("con",))], "unsafe_instance_key"),
    ([TargetIntent("bag", " backpack ", ("one",))], "invalid_target_phrase"),
    ([TargetIntent("bag", "x", ("one",))], "invalid_target_phrase"),
])
def test_ambiguous_or_unsafe_instance_contract_fails_closed(targets, reason):
    with pytest.raises(InstancePlanRefused, match=reason):
        plan(targets=targets)


def test_invalid_source_or_asset_or_excessive_cardinality_is_refused():
    with pytest.raises(InstancePlanRefused, match="invalid_source_sha256"):
        plan(source="ABC")
    with pytest.raises(InstancePlanRefused, match="invalid_asset_key"):
        plan(asset="../asset")
    with pytest.raises(InstancePlanRefused, match="too_many_instances"):
        plan(targets=[TargetIntent("items", "multiple items",
                                   tuple("item-" + str(i) for i in range(129)))])


def test_no_auto_selection_can_be_inferred_from_detector_candidate_order():
    keys = ("owner-a", "owner-b")
    first = plan(targets=[TargetIntent("bag", "backpack", keys)])
    # Inference order (which candidate mask is first) is deliberately absent.
    assert "mask" not in first.to_record()
    assert "candidate" not in first.to_record()
    assert "selection" not in first.to_record()
    assert first.to_record()["binding_status"] == "unbound"
