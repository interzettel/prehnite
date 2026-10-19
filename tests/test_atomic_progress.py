"""Archived v1 atomic evidence is preserved, but no longer an active score."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_immutable_v1_atomic_snapshot_and_historical_parent_ids():
    archive = ROOT / "progress/archive/v1"
    ledger = json.loads((archive / "ledger.json").read_text())
    atomic = json.loads((archive / "atomic.json").read_text())
    units = {u["id"]: u for m in ledger["milestones"] for u in m["units"]}
    assert len(units) == 61
    assert sum(u["state"] == "done" for u in units.values()) == 43
    assert len(atomic["tasks"]) == atomic["baseline_task_count"] == 73
    assert sum(t["state"] == "done" for t in atomic["tasks"]) == 21
    assert len(atomic["baseline_open_parent_ids"]) == 19
    assert all(t["parent"] in units for t in atomic["tasks"])
    assert {u["id"] for u in units.values() if u["state"] != "done"} == {
        t["parent"] for t in atomic["tasks"]
    }


def test_archived_reports_remain_available_but_no_parallel_active_dashboard():
    assert (ROOT / "docs/archive/v1/STATUS.md").exists()
    assert (ROOT / "docs/archive/v1/ATOMIC.md").exists()
    assert (ROOT / "docs/archive/v1/atomic.svg").exists()
    assert (ROOT / "docs/archive/v1/progress.svg").exists()
    assert not (ROOT / "docs/progress/ATOMIC.md").exists()
    assert not (ROOT / "docs/progress/atomic.svg").exists()
    assert not (ROOT / "docs/progress/progress.svg").exists()


def test_every_v1_unfinished_obligation_has_traceable_crosswalk():
    current = json.loads((ROOT / "progress/roadmap.json").read_text())
    ledger = json.loads((ROOT / "progress/archive/v1/ledger.json").read_text())
    original_open = {u["id"] for m in ledger["milestones"] for u in m["units"]
                     if u["state"] != "done"}
    refs = current["legacy_crosswalk"]
    assert len(refs) == 18
    assert {x["legacy_unit"] for x in refs} == original_open
    assert any(x["relationship"] == "legacy_release_only" for x in refs)
