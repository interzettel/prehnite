"""Frozen cutout capability tracking must stay evidence-linked and reproducible."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def tracker():
    spec = importlib.util.spec_from_file_location(
        "cutout_capability_tracker", ROOT / "scripts" / "cutout_capability_progress.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def data():
    return json.loads((ROOT / "progress" / "cutout_capability.json").read_text(encoding="utf-8"))


def test_capability_evidence_is_distinct_from_release_denominators():
    module = tracker()
    doc = data()
    module.validate(doc)
    assert len(doc["milestones"]) == 13
    assert sum(item["state"] == "done" for item in doc["milestones"]) >= 8
    assert module.headline(doc) in (ROOT / "README.md").read_text(encoding="utf-8")
    assert module.headline(doc) in (ROOT / "docs" / "PROGRESS.md").read_text(encoding="utf-8")
    assert "42 / 61" in (ROOT / "docs" / "progress" / "STATUS.md").read_text(encoding="utf-8")
    assert "14/73" in (ROOT / "docs" / "progress" / "ATOMIC.md").read_text(encoding="utf-8")


def test_checked_in_report_is_deterministically_generated():
    module = tracker()
    content = module.render(data())
    assert content == (ROOT / "docs" / "progress" / "CUTOUT_CAPABILITY.md").read_text(
        encoding="utf-8"
    )
    assert "This percentage measures a fixed cutout workstream" in content
    assert "not" in content.lower()


@pytest.mark.parametrize("change", [
    lambda x: x["milestones"].pop(),
    lambda x: x.update(fixed_milestone_count=14),
    lambda x: x["milestones"][0].update(id="LP99"),
    lambda x: x.update(baseline_date="2026-10-19"),
])
def test_denominator_and_identity_cannot_be_silently_rebaselined(change):
    module = tracker()
    broken = deepcopy(data())
    change(broken)
    with pytest.raises(ValueError):
        module.validate(broken)


def test_unverified_work_cannot_claim_completion_without_new_evidence():
    module = tracker()
    broken = deepcopy(data())
    future = next(item for item in broken["milestones"] if item["id"] == "VL02")
    future["state"] = "done"
    future.pop("blocker")
    with pytest.raises(ValueError, match="evidence"):
        module.validate(broken)


def test_incomplete_work_cannot_carry_merged_credit():
    module = tracker()
    broken = deepcopy(data())
    future = next(item for item in broken["milestones"] if item["id"] == "VL03")
    future["evidence_kind"] = "merged_pr"
    future["evidence"] = "https://github.com/interzettel/prehnite/pull/161"
    with pytest.raises(ValueError, match="cannot claim evidence"):
        module.validate(broken)


def test_report_distinguishes_merged_code_from_private_operator_proof():
    module = tracker()
    content = module.render(data())
    assert "Private operator report" in content
    assert "Independent artifact review" in content
    assert "Merged public PR" in content
    assert "Merged regression test" in content
    assert "Not yet demonstrated" in content
