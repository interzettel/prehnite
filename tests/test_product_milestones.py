"""One active product milestone source, including research and user acceptance."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module():
    spec = importlib.util.spec_from_file_location("roadmap_product_test", ROOT / "scripts/roadmap.py")
    obj = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(obj)
    return obj


def test_canonical_v2_has_research_code_experiment_and_acceptance():
    m = module()
    data = m.load()
    m.validate(data)
    kinds = Counter(t["kind"] for t in data["tasks"])
    assert kinds == {
        "research": 3, "decision": 2, "implementation": 49,
        "experiment": 5, "acceptance": 4,
    }
    assert data["phases"][0]["exit_milestone"] == "P1-M05"
    assert data["phases"][1]["exit_milestone"] == "P2-M03"
    assert data["milestones"][0]["id"] == "P1-M00"
    assert data["milestones"][0]["state"] == "verified"
    assert len([t for t in data["tasks"] if t["state"] == "verified"]) == 43
    assert len(data["migration_integrity"]["carried_forward_v1_unit_ids"]) == 43


def test_owner_decision_needs_owner_receipt():
    m = module()
    data = deepcopy(m.load())
    target = next(t for t in data["tasks"] if t["id"] == "P1-M01-R02")
    target["state"] = "verified"
    target["evidence"] = [{"type": "merged_pr",
                           "url": "https://github.com/interzettel/prehnite/pull/183"}]
    with pytest.raises(ValueError, match="premature task credit|required evidence kind"):
        m.validate(data)


def test_historical_baseline_must_remain_unchanged():
    m = module()
    data = deepcopy(m.load())
    data["historical_archive"]["snapshot_atomic"]["done"] = 73
    with pytest.raises(ValueError, match="historical atomic snapshot"):
        m.validate(data)


def test_foundation_pr_evidence_must_match_archived_units():
    m = module()
    data = deepcopy(m.load())
    target = next(t for t in data["tasks"] if t["id"] == "P1-M00-F01")
    target["evidence"][0]["url"] = "https://github.com/interzettel/prehnite/pull/999999"
    with pytest.raises(ValueError, match="foundation evidence provenance"):
        m.validate(data)


def test_product_plan_does_not_authorize_model_execution():
    data = module().load()
    assert "GPU execution" not in data.get("adopted_from", "")
    assert all(t.get("state") != "verified" for t in data["tasks"]
               if t["kind"] == "experiment")
    assert "4 GiB benchmarking" in data["excluded_hardware_campaigns"]
    assert "6 GiB benchmarking" in data["excluded_hardware_campaigns"]


def test_legacy_implementation_receipts_cannot_be_fabricated():
    m = module()
    data = deepcopy(m.load())
    legacy = next(t for t in data["tasks"] if t.get("original_unit") == "P07")
    legacy["evidence"][0]["url"] = "https://github.com/interzettel/prehnite/pull/999999"
    with pytest.raises(ValueError, match="foundation evidence provenance"):
        m.validate(data)


def test_progress_not_awarded_from_untested_provider_code():
    data = module().load()
    assert len(data["tasks"]) == 63
    assert sum(t["state"] == "verified" for t in data["tasks"]) == 43
    assert all(t["state"] != "verified" for t in data["tasks"] if t["kind"] == "experiment")
    assert next(m for m in data["milestones"] if m["id"] == "P1-M02")["state"] != "verified"
