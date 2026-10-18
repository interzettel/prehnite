"""Atomic tracker contract: small-agent task IDs, stable denominator, honest evidence."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def tracker():
    spec = importlib.util.spec_from_file_location(
        "prehnite_atomic_progress", ROOT / "scripts" / "atomic_progress.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def data():
    return (json.loads((ROOT / "progress/ledger.json").read_text()),
            json.loads((ROOT / "progress/atomic.json").read_text()))


def find(atomic, id_):
    return next(t for t in atomic["tasks"] if t["id"] == id_)


def unfinished_planned(atomic):
    """Use the current original registry, not a task assumed planned forever."""
    return next(t for t in atomic["tasks"]
                if t["state"] == "planned" and not t["dependsOn"])


def planned_pair(atomic):
    """Find two initially unrelated unfinished tasks under one parent."""
    for first in atomic["tasks"]:
        if first["state"] != "planned" or first["dependsOn"]:
            continue
        for second in atomic["tasks"]:
            if (second["parent"] == first["parent"] and second["id"] != first["id"]
                    and second["state"] == "planned" and not second["dependsOn"]):
                return first, second
    raise AssertionError("Need two unblocked planned original tasks to test cycles")


def test_frozen_scope_covers_every_initially_unfinished_release_unit():
    module = tracker()
    ledger, atomic = data()
    module.validate(ledger, atomic)
    m = module.counts(ledger, atomic)
    assert m["parent_total"] == 61
    assert m["parent_done"] >= 42
    assert m["task_total"] == atomic["baseline_task_count"] == 73
    assert len(atomic["baseline_open_parent_ids"]) == 19
    assert {u["id"] for milestone in ledger["milestones"] for u in milestone["units"]
            if u["state"] != "done"}.issubset(set(atomic["baseline_open_parent_ids"]))
    assert m["done"] >= 10
    assert m["done"] + m["in_review"] + m["active"] + m["blocked"] + m["planned"] == 73


def test_generated_svg_and_markdown_are_reproducible():
    module = tracker()
    ledger, atomic = data()
    generated = module.outputs(ledger, atomic)
    for path, contents in generated.items():
        assert path.read_text(encoding="utf-8") == contents
    svg = module.render_svg(ledger, atomic)
    md = module.render_md(ledger, atomic)
    status = module.counts(ledger, atomic)
    assert module.pct(status["parent_done"], status["parent_total"]) in svg
    assert module.pct(status["done"], status["task_total"]) in md
    assert "not an overall project completion score" in md
    assert "PR-SIZED TASKS BY UNFINISHED UNIT" in svg
    assert f'{status["parent_done"]}/{status["parent_total"]}' in md
    assert f'{status["done"]}/{status["task_total"]}' in md


@pytest.mark.parametrize("mutation,expected", [
    (lambda x: x["tasks"].pop(), "denominator"),
    (lambda x: x["tasks"][0].update(id=x["tasks"][1]["id"]), "Duplicate"),
    (lambda x: x["tasks"][0].update(parent="X99"), "orphan"),
    (lambda x: x["tasks"][0].update(acceptance="yes"), "acceptance"),
    (lambda x: x.update(baseline_date="2026-10-18"), "Baseline"),
    (lambda x: x["tasks"][0].update(issue=999999), "owner"),
])
def test_invalid_task_scopes_cannot_inflate_progress(mutation, expected):
    module = tracker()
    ledger, atomic = data()
    mutation(atomic)
    with pytest.raises(ValueError, match=expected):
        module.validate(ledger, atomic)


def test_review_cannot_be_relabelled_done_without_merge_receipt():
    module = tracker()
    ledger, atomic = data()
    # Construct an unmerged review state instead of assuming a specific PR
    # stays open forever. That state earns no credit even if relabeled.
    item = unfinished_planned(atomic)
    item["state"] = "in_review"
    item["review_url"] = "https://github.com/interzettel/prehnite/pull/9999"
    assert module.counts(ledger, atomic)["done"] == module.counts(*data())["done"]
    item["state"] = "done"
    with pytest.raises(ValueError, match="evidence"):
        module.validate(ledger, atomic)


def test_nonexistent_or_non_repository_merge_proof_rejected():
    module = tracker()
    ledger, atomic = data()
    item = find(atomic, "S03-A01")
    assert item["state"] == "done"
    item["evidence"] = "https://example.com/pull/119"
    with pytest.raises(ValueError, match="evidence"):
        module.validate(ledger, atomic)


def test_blocked_task_requires_unblocking_action():
    module = tracker()
    ledger, atomic = data()
    item = find(atomic, "S06-A04")
    assert item["state"] == "blocked"
    del item["blocker"]
    with pytest.raises(ValueError, match="Blocked"):
        module.validate(ledger, atomic)


def test_parent_cannot_be_marked_done_with_remaining_subtasks():
    module = tracker()
    ledger, atomic = data()
    for milestone in ledger["milestones"]:
        for item in milestone["units"]:
            if item["id"] == "S03":
                item["state"] = "done"
    with pytest.raises(ValueError, match="parent"):
        module.validate(ledger, atomic)


def test_done_child_cannot_depend_on_unfinished_atomic_child():
    module = tracker()
    ledger, atomic = data()
    find(atomic, "S03-A01")["dependsOn"] = [unfinished_planned(atomic)["id"]]
    with pytest.raises(ValueError, match="Premature"):
        module.validate(ledger, atomic)


def test_cycles_and_unknown_dependencies_rejected():
    module = tracker()
    ledger, original = data()
    broken = deepcopy(original)
    first, second = planned_pair(broken)
    first["dependsOn"] = [second["id"]]
    second["dependsOn"] = [first["id"]]
    with pytest.raises(ValueError, match="cycle"):
        module.validate(ledger, broken)
    broken = deepcopy(original)
    find(broken, "S03-A04")["dependsOn"] = ["BOGUS-A01"]
    with pytest.raises(ValueError, match="Unknown"):
        module.validate(ledger, broken)


def test_release_completion_is_unchanged_by_atom_progress_changes():
    module = tracker()
    ledger, atomic = data()
    prev = module.counts(ledger, atomic)
    item = unfinished_planned(atomic)
    item["state"] = "done"
    item["evidence"] = "https://github.com/interzettel/prehnite/pull/9999"
    item["verified_at"] = atomic["updated"]
    after = module.counts(ledger, atomic)
    assert after["done"] == prev["done"] + 1
    assert after["parent_done"] == prev["parent_done"]
    assert after["parent_total"] == prev["parent_total"]


def test_merge_evidence_is_real_link_not_raw_issue():
    module = tracker()
    ledger, atomic = data()
    task = find(atomic, "S05-A02")
    assert task["evidence"].endswith("/pull/119")
    task["evidence"] = "https://github.com/interzettel/prehnite/issues/31"
    with pytest.raises(ValueError, match="evidence"):
        module.validate(ledger, atomic)
