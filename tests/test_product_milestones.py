"""Regression checks: product planning must not falsify historical evidence."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module():
    spec = importlib.util.spec_from_file_location(
        "prehnite_product_milestones", ROOT / "scripts/check_product_milestones.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def data():
    return module().load_plan(ROOT)


def test_proposed_plan_and_original_ledgers_are_consistent():
    m = module()
    plan, ledger, atomic = data()
    result = m.validate(plan, ledger, atomic)
    assert result == {
        "phases": 2,
        "milestones_proposed": 8,
        "tasks_proposed": 20,
        "legacy_units_preserved": 18,
    }
    assert all(t["state"] == "proposed" for t in plan["tasks"])
    assert all(x["state"] == "proposed" for x in plan["milestones"])


@pytest.mark.parametrize("kind", ["research", "decision", "implementation", "experiment",
                                   "acceptance"])
def test_planning_register_has_distinct_work_kinds(kind):
    plan, _, _ = data()
    assert any(t["kind"] == kind for t in plan["tasks"])


def test_phase1_exit_depends_on_optimization_and_batch_evidence():
    plan, _, _ = data()
    exit_gate = next(x for x in plan["milestones"] if x["id"] == "P1-M05")
    assert set(exit_gate["depends_on"]) == {"P1-M03", "P1-M04"}


def test_no_phantom_milestone_completion():
    plan, ledger, atomic = data()
    plan = deepcopy(plan)
    plan["milestones"][0]["state"] = "verified"
    with pytest.raises(ValueError, match="cannot certify a milestone"):
        module().validate(plan, ledger, atomic)


def test_no_phantom_research_credit():
    plan, ledger, atomic = data()
    plan = deepcopy(plan)
    plan["tasks"][0]["state"] = "verified"
    plan["tasks"][0]["evidence"] = [{
        "url": "https://github.com/interzettel/prehnite/pull/183"
    }]
    with pytest.raises(ValueError, match="cannot certify task evidence"):
        module().validate(plan, ledger, atomic)


def test_unknown_dependency_rejected():
    plan, ledger, atomic = data()
    plan = deepcopy(plan)
    plan["tasks"][0]["depends_on"] = ["UNKNOWN-TASK"]
    with pytest.raises(ValueError, match="unknown dependency"):
        module().validate(plan, ledger, atomic)


def test_dependency_cycle_rejected():
    plan, ledger, atomic = data()
    plan = deepcopy(plan)
    plan["tasks"][0]["depends_on"] = [plan["tasks"][1]["id"]]
    plan["tasks"][1]["depends_on"] = [plan["tasks"][0]["id"]]
    with pytest.raises(ValueError, match="dependency cycle"):
        module().validate(plan, ledger, atomic)


def test_crosswalk_must_keep_18_legacy_units():
    plan, ledger, atomic = data()
    plan = deepcopy(plan)
    plan["legacy_crosswalk"].pop()
    with pytest.raises(ValueError, match="18 originally unfinished"):
        module().validate(plan, ledger, atomic)


def test_no_nonexistent_phase_or_4_6gb_phase():
    plan, ledger, atomic = data()
    plan = deepcopy(plan)
    plan["phases"].append({"id": "P3", "name": "Video studio", "exit_milestone": "P2-M03"})
    with pytest.raises(ValueError, match="two agreed product phases"):
        module().validate(plan, ledger, atomic)


def test_no_canonical_completion_loss():
    plan, ledger, atomic = data()
    ledger = deepcopy(ledger)
    unit = next(u for m in ledger["milestones"]
                for u in m["units"] if u["state"] == "done")
    unit["state"] = "planned"
    with pytest.raises(ValueError, match="historical evidence"):
        module().validate(plan, ledger, atomic)


def test_original_snapshot_not_silently_rewritten():
    plan, ledger, atomic = data()
    plan = deepcopy(plan)
    plan["legacy_accounting"]["original_tasks"]["done"] = 73
    with pytest.raises(ValueError, match="historical snapshot"):
        module().validate(plan, ledger, atomic)
