"""Validate the proposed 8 GiB product milestones without awarding delivery credit.

The v2 register is an advisory plan until separately adopted. Its evidence
cannot replace the frozen 61-unit and 73-task releases/progress systems.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "progress" / "product_milestones.v2.proposed.json"
KINDS = frozenset({"research", "decision", "implementation", "experiment", "acceptance"})
STATES = frozenset({"proposed", "ready", "active", "in_review", "blocked", "verified"})
RELATIONSHIPS = frozenset({
    "direct", "partial_overlap", "legacy_release_only", "separate_administration",
})


def load_plan(root: Path = ROOT) -> tuple[dict, dict, dict]:
    """Read proposal and existing canonical registers. No modifications."""
    progress = root / "progress"
    return (
        json.loads((progress / "product_milestones.v2.proposed.json").read_text()),
        json.loads((progress / "ledger.json").read_text()),
        json.loads((progress / "atomic.json").read_text()),
    )


def _unique(objects: list[dict], name: str) -> dict[str, dict]:
    if not isinstance(objects, list) or not objects:
        raise ValueError(f"{name} must be a nonempty list")
    keys = [item.get("id") for item in objects]
    if any(not isinstance(k, str) or not k for k in keys) or len(set(keys)) != len(keys):
        raise ValueError(f"{name} has duplicate or invalid ids")
    return {item["id"]: item for item in objects}


def _acyclic(items: dict[str, dict], label: str) -> None:
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise ValueError(f"{label} dependency cycle: {key}")
        if key in visited:
            return
        visiting.add(key)
        for dep in items[key].get("depends_on", []):
            if dep not in items:
                raise ValueError(f"{label} unknown dependency: {dep}")
            visit(dep)
        visiting.remove(key)
        visited.add(key)

    for key in items:
        visit(key)


def validate(plan: dict, ledger: dict, atomic: dict) -> dict[str, int]:
    """Require structurally sound proposed gates, crosswalk and no false credit."""
    if plan.get("schema_version") != 2 or plan.get("plan_status") != "proposed":
        raise ValueError("v2 product plan must remain a proposal until owner adoption")
    if "8 GiB" not in plan.get("primary_hardware", ""):
        raise ValueError("8 GiB actual laptop focus missing")
    phases = _unique(plan.get("phases"), "phases")
    if set(phases) != {"P1", "P2"}:
        raise ValueError("only the two agreed product phases are supported")
    milestones = _unique(plan.get("milestones"), "milestones")
    tasks = _unique(plan.get("tasks"), "tasks")
    _acyclic(milestones, "milestone")
    _acyclic(tasks, "task")

    canonical_units = [unit for m in ledger["milestones"] for unit in m["units"]]
    if len(canonical_units) != 61 or len(atomic["tasks"]) != 73:
        raise ValueError("canonical 61/73 baselines changed")
    original = plan.get("legacy_accounting", {})
    historical_release = original.get("original_units", {})
    historical_tasks = original.get("original_tasks", {})
    if (historical_release != {"done": 43, "total": 61}
            or historical_tasks != {"done": 21, "total": 73}):
        raise ValueError("proposal must show actual original historical snapshot")
    if (sum(x["state"] == "done" for x in canonical_units) < 43
            or sum(x["state"] == "done" for x in atomic["tasks"]) < 21):
        raise ValueError("historical evidence has been lost")

    for phase in phases.values():
        gate = phase.get("exit_milestone")
        if gate not in milestones or milestones[gate].get("phase") != phase["id"]:
            raise ValueError(f"invalid phase exit gate: {phase['id']}")

    used: set[str] = set()
    for milestone in milestones.values():
        if milestone.get("phase") not in phases:
            raise ValueError("unknown milestone phase")
        if milestone.get("state") != "proposed" or milestone.get("evidence") != []:
            raise ValueError("proposal cannot certify a milestone")
        gates = milestone.get("gate_tasks")
        if not isinstance(gates, list) or not gates or len(gates) != len(set(gates)):
            raise ValueError("milestone must have unique gate tasks")
        for gate in gates:
            if gate not in tasks or tasks[gate].get("milestone") != milestone["id"]:
                raise ValueError("invalid milestone gate reference")
            if gate in used:
                raise ValueError("task gates cannot be double-counted")
            used.add(gate)
    if used != set(tasks):
        raise ValueError("each proposed task needs exactly one milestone gate")

    for task in tasks.values():
        if task.get("kind") not in KINDS or task.get("state") not in STATES:
            raise ValueError("invalid task type or status")
        if task["state"] != "proposed" or task.get("evidence") != []:
            raise ValueError("proposal cannot certify task evidence or progress")
        if task.get("owner") not in ledger["lanes"]:
            raise ValueError("unknown agent/owner lane")
        if (not isinstance(task.get("issue"), int) or isinstance(task["issue"], bool)
                or task["issue"] <= 0 or not task.get("acceptance")):
            raise ValueError("task must link a real issue number and acceptance criteria")

    refs = plan.get("legacy_crosswalk")
    if not isinstance(refs, list) or len(refs) != 18:
        raise ValueError("crosswalk must retain all 18 originally unfinished units")
    names = {item["id"] for item in canonical_units}
    crosswalk_ids: set[str] = set()
    for ref in refs:
        legacy_id = ref.get("legacy_unit")
        if legacy_id not in names or legacy_id in crosswalk_ids:
            raise ValueError("duplicate or unknown legacy unit in crosswalk")
        crosswalk_ids.add(legacy_id)
        if (ref.get("relationship") not in RELATIONSHIPS
                or not isinstance(ref.get("note"), str) or not ref["note"]):
            raise ValueError("crosswalk relation and limitations required")
        target = ref.get("product_milestone")
        if target is not None and target not in milestones:
            raise ValueError("unknown crosswalk milestone target")

    if set(names) - {u["id"] for u in canonical_units if u["state"] == "done"} != crosswalk_ids:
        # The live ledger may advance after the proposal, but historical mapped
        # units can only be removed from this set by documented original credit.
        if not crosswalk_ids.issuperset({
            u["id"] for u in canonical_units if u["state"] != "done"
        }):
            raise ValueError("original unfinished units missing from crosswalk")

    return {
        "phases": len(phases), "milestones_proposed": len(milestones),
        "tasks_proposed": len(tasks), "legacy_units_preserved": len(refs),
    }


def main() -> int:
    plan, ledger, atomic = load_plan()
    print(json.dumps(validate(plan, ledger, atomic), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
