"""Canonical progress ledger: reproducible outputs and evidence integrity."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def progress_module():
    spec = importlib.util.spec_from_file_location("prehnite_progress", ROOT / "scripts/progress.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def ledger():
    return json.loads((ROOT / "progress/ledger.json").read_text(encoding="utf-8"))


def test_current_ledger_and_generated_outputs_match():
    module = progress_module()
    data = ledger()
    module.validate(data)
    assert module.render_svg(data) == (ROOT / "docs/progress/progress.svg").read_text(encoding="utf-8")
    assert module.render_markdown(data) == (ROOT / "docs/progress/STATUS.md").read_text(encoding="utf-8")


def test_done_units_need_evidence():
    module = progress_module()
    data = ledger()
    data["milestones"][0]["units"][0].pop("evidence")
    with pytest.raises(ValueError, match="evidence"):
        module.validate(data)


def test_unknown_prerequisite_is_rejected():
    module = progress_module()
    data = ledger()
    data["milestones"][-1]["units"][-1]["dependsOn"] = ["NOT99"]
    with pytest.raises(ValueError, match="Unknown prerequisite"):
        module.validate(data)


def test_dependency_cycle_is_rejected():
    module = progress_module()
    data = ledger()
    # Two planned units with otherwise valid prerequisites may not depend on each other.
    a = data["milestones"][1]["units"][6]  # C07 planned
    b = data["milestones"][1]["units"][9]  # C10 planned
    a["dependsOn"] = [b["id"]]
    b["dependsOn"] = [a["id"]]
    with pytest.raises(ValueError, match="Dependency cycle"):
        module.validate(data)


def test_duplicate_unit_is_rejected():
    module = progress_module()
    data = ledger()
    data["milestones"][0]["units"].append(copy.deepcopy(data["milestones"][0]["units"][0]))
    with pytest.raises(ValueError, match="Duplicate unit"):
        module.validate(data)


def test_premature_completion_is_rejected():
    module = progress_module()
    data = ledger()
    # Select a still-unfinished unit with a still-unfinished prerequisite.
    # This remains meaningful as dependencies are progressively completed.
    all_units = [u for m in data["milestones"] for u in m["units"]]
    by_id = {u["id"]: u for u in all_units}
    item = next(u for u in all_units
                if u["state"] == "planned" and any(
                    by_id[dep]["state"] != "done" for dep in u["dependsOn"]))
    item["state"] = "done"
    item["evidence"] = "https://github.com/interzettel/prehnite/issues/15"
    with pytest.raises(ValueError, match="Premature completion"):
        module.validate(data)


def test_milestone_gate_must_reference_own_unit():
    module = progress_module()
    data = ledger()
    data["milestones"][0]["gate"].append("P09")
    with pytest.raises(ValueError, match="Invalid milestone gate"):
        module.validate(data)


def test_milestone_percent_and_gates():
    module = progress_module()
    data = ledger()
    stats = module.stats(module.units(data))
    assert stats["total"] == 61
    assert stats["done"] == 30
    assert module.stats(data["milestones"][0]["units"])["pct"] == 100
    assert all(unit["state"] == "done" for unit in data["milestones"][0]["units"])
    assert data["milestones"][0]["gate"] == ["F06"]
