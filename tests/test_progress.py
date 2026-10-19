"""Canonical v2 roadmap: evidence migration and honest single-source milestones."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def roadmap():
    spec = importlib.util.spec_from_file_location("prehnite_v2_roadmap", ROOT / "scripts/roadmap.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_one_active_roadmap_and_reproducible_status():
    module = roadmap()
    data = module.load()
    result = module.validate(data)
    assert result["phases"] == 2
    assert result["milestones"] == 9
    assert result["milestones_verified"] == 1
    assert result["tasks"] == 26
    assert result["tasks_verified"] == 6
    assert module.render(data) == (ROOT / "docs/progress/STATUS.md").read_text()
    assert not (ROOT / "progress/ledger.json").exists()
    assert not (ROOT / "progress/atomic.json").exists()
    assert not (ROOT / "progress/product_milestones.v2.proposed.json").exists()


def test_no_new_credit_without_artifact_evidence():
    module = roadmap()
    data = deepcopy(module.load())
    target = next(t for t in data["tasks"] if t["id"] == "P1-M01-R01")
    target["state"] = "verified"
    with pytest.raises(ValueError, match="no evidence"):
        module.validate(data)


def test_prevent_synthetic_only_real_hardware_credit():
    module = roadmap()
    data = deepcopy(module.load())
    target = next(t for t in data["tasks"] if t["id"] == "P1-M02-E01")
    target["state"] = "verified"
    target["evidence"] = [{
        "type": "merged_pr",
        "url": "https://github.com/interzettel/prehnite/pull/181",
    }]
    with pytest.raises(ValueError, match="prerequisite|required evidence kind"):
        module.validate(data)


def test_product_milestone_gate_cannot_be_overridden():
    module = roadmap()
    data = deepcopy(module.load())
    gate = next(m for m in data["milestones"] if m["id"] == "P1-M02")
    gate["state"] = "verified"
    gate["evidence"] = [{
        "type": "merged_pr",
        "url": "https://github.com/interzettel/prehnite/pull/181",
    }]
    with pytest.raises(ValueError, match="premature milestone credit"):
        module.validate(data)


def test_cycle_and_orphan_detection():
    module = roadmap()
    a = deepcopy(module.load())
    a["milestones"][1]["depends_on"] = ["P1-M02"]
    with pytest.raises(ValueError, match="dependency cycle"):
        module.validate(a)
    b = deepcopy(module.load())
    b["milestones"][1]["gate_tasks"] = ["P1-M02-E01"]
    with pytest.raises(ValueError, match="orphan or double-counted"):
        module.validate(b)


def test_no_low_tier_campaign_or_phase_three():
    module = roadmap()
    a = deepcopy(module.load())
    a["phases"].append({"id": "P3", "name": "Video", "milestones": [], "exit_milestone": "P2-M03"})
    with pytest.raises(ValueError, match="two product phases"):
        module.validate(a)
