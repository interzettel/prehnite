"""Single active Prehnite v2 product roadmap: validate evidence and render status.

V1 release and atomic reports are immutable, archived historical snapshots.
No legacy denominator participates in current completion percentages.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "progress" / "roadmap.json"
OUTPUT = ROOT / "docs" / "progress" / "STATUS.md"
KINDS = {"research", "decision", "implementation", "experiment", "acceptance"}
STATES = {"planned", "active", "in_review", "blocked", "verified"}
EVIDENCE_TYPES = {
    "merged_pr", "research_review", "owner_decision",
    "observed_experiment", "independent_review", "human_acceptance",
    "historical_receipt",
}
REPO_PREFIX = "https://github.com/interzettel/prehnite/"


def load(root: Path = ROOT) -> dict:
    return json.loads((root / "progress" / "roadmap.json").read_text(encoding="utf-8"))


def _identities(items: list[dict], name: str) -> dict[str, dict]:
    if not isinstance(items, list) or not items:
        raise ValueError(f"{name} must be a nonempty list")
    ids = [x.get("id") for x in items]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{name}: duplicate/invalid id")
    return {x["id"]: x for x in items}


def _check_graph(items: dict[str, dict], name: str) -> None:
    seen: set[str] = set()
    stack: set[str] = set()

    def visit(key: str) -> None:
        if key in stack:
            raise ValueError(f"{name} dependency cycle {key}")
        if key in seen:
            return
        stack.add(key)
        for dep in items[key].get("depends_on", []):
            if dep not in items:
                raise ValueError(f"{name} unknown prerequisite {dep}")
            visit(dep)
        stack.remove(key)
        seen.add(key)
    for key in items:
        visit(key)


def _evidence(item: dict) -> None:
    if item.get("state") == "verified":
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"verified item has no evidence: {item.get('id')}")
        for entry in evidence:
            if not isinstance(entry, dict) or entry.get("type") not in EVIDENCE_TYPES:
                raise ValueError("invalid evidence type")
            url = entry.get("url")
            if not isinstance(url, str) or not url.startswith(REPO_PREFIX):
                raise ValueError("verifiable repository evidence URL required")
    elif item.get("evidence"):
        raise ValueError(f"unverified item claims evidence credit: {item.get('id')}")


def validate(data: dict, root: Path = ROOT) -> dict:
    if data.get("schema_version") != 2 or data.get("plan_status") != "active":
        raise ValueError("expected one active v2 roadmap")
    if data.get("canonical_source") != "progress/roadmap.json":
        raise ValueError("canonical roadmap path mismatch")
    if "8 GiB" not in data.get("primary_hardware", ""):
        raise ValueError("current physical 8 GiB reference hardware required")
    phases = _identities(data.get("phases"), "phases")
    if set(phases) != {"P1", "P2"}:
        raise ValueError("only two product phases are authorized")
    milestones = _identities(data.get("milestones"), "milestones")
    tasks = _identities(data.get("tasks"), "tasks")
    _check_graph(milestones, "milestone")
    _check_graph(tasks, "task")
    if set(milestones) != {x for p in phases.values() for x in p.get("milestones", [])}:
        raise ValueError("all milestones must appear exactly once in phase hierarchy")
    if sum(len(p["milestones"]) for p in phases.values()) != len(milestones):
        raise ValueError("duplicate milestone in phases")
    for phase in phases.values():
        exit_id = phase.get("exit_milestone")
        if exit_id not in milestones or milestones[exit_id].get("phase") != phase["id"]:
            raise ValueError("invalid phase exit milestone")

    occupied = set()
    for mid, m in milestones.items():
        if m.get("phase") not in phases or m.get("state") not in STATES:
            raise ValueError("invalid milestone phase/state")
        gate = m.get("gate_tasks")
        if not isinstance(gate, list) or not gate or len(gate) != len(set(gate)):
            raise ValueError("missing/duplicate milestone task gate")
        for tid in gate:
            if tid not in tasks or tasks[tid].get("milestone") != mid or tid in occupied:
                raise ValueError("orphan or double-counted gate task")
            occupied.add(tid)
        _evidence(m)
        if m["state"] == "verified":
            if any(tasks[t]["state"] != "verified" for t in gate):
                raise ValueError("premature milestone credit: unverified gate task")
            if any(milestones[d]["state"] != "verified" for d in m.get("depends_on", [])):
                raise ValueError("premature milestone credit: dependency")
    if occupied != set(tasks):
        raise ValueError("unassigned milestone task")

    for tid, task in tasks.items():
        if task.get("kind") not in KINDS or task.get("state") not in STATES:
            raise ValueError("invalid task kind/state")
        if task.get("owner") not in {"Owner", "Agent local", "Agent cloud"}:
            raise ValueError("invalid task owner")
        issue = task.get("issue")
        if type(issue) is not int or issue <= 0 or not task.get("acceptance"):
            raise ValueError("missing task acceptance or issue")
        _evidence(task)
        if task["state"] == "verified":
            if any(tasks[d]["state"] != "verified" for d in task.get("depends_on", [])):
                raise ValueError(f"premature task credit: {tid}")
            expected = {
                "research": {"research_review"},
                "decision": {"owner_decision"},
                "implementation": ({"merged_pr", "historical_receipt"}
                                   if task.get("source") == "v1_verified"
                                   else {"merged_pr"}),
                "experiment": {"observed_experiment", "independent_review"},
                "acceptance": {"human_acceptance", "owner_decision"},
            }[task["kind"]]
            actual = {x["type"] for x in task["evidence"]}
            if not expected.intersection(actual):
                raise ValueError(f"verified task missing required evidence kind: {tid}")
        if task["kind"] == "experiment" and task["state"] == "blocked" and not task.get("blocker"):
            raise ValueError("blocked experiment needs explicit authorization blocker")

    original = data.get("historical_archive", {})
    if original.get("snapshot_release") != {"done": 43, "total": 61}:
        raise ValueError("historical release snapshot altered")
    if original.get("snapshot_atomic") != {"done": 21, "total": 73}:
        raise ValueError("historical atomic snapshot altered")
    archive = root / "progress" / "archive" / "v1"
    old_ledger = json.loads((archive / "ledger.json").read_text(encoding="utf-8"))
    old_atomic = json.loads((archive / "atomic.json").read_text(encoding="utf-8"))
    old_units = [u for x in old_ledger["milestones"] for u in x["units"]]
    if (len(old_units), sum(u["state"] == "done" for u in old_units)) != (61, 43):
        raise ValueError("immutable release archive drift")
    if (len(old_atomic["tasks"]), sum(x["state"] == "done" for x in old_atomic["tasks"])) != (73, 21):
        raise ValueError("immutable atomic archive drift")
    original_ids = {u["id"] for u in old_units}
    historical_open = {u["id"] for u in old_units if u["state"] != "done"}
    refs = data.get("legacy_crosswalk")
    if not isinstance(refs, list) or len(refs) != 18:
        raise ValueError("all 18 unfinished legacy units must be mapped")
    mapped = [r.get("legacy_unit") for r in refs]
    if len(set(mapped)) != 18 or set(mapped) != historical_open:
        raise ValueError("missing or duplicate retired legacy obligation")
    for ref in refs:
        target = ref.get("product_milestone")
        if target is not None and target not in milestones:
            raise ValueError("legacy crosswalk references missing milestone")
        if not ref.get("note") or not ref.get("relationship"):
            raise ValueError("unexplained legacy obligation")
    historical_done = {u["id"]: u for u in old_units if u["state"] == "done"}
    carried = data.get("migration_integrity", {}).get("carried_forward_v1_unit_ids")
    if not isinstance(carried, list) or set(carried) != set(historical_done) or len(carried) != 43:
        raise ValueError("all 43 originally verified capabilities must be carried exactly once")
    inherited = [t for t in tasks.values() if any(
        e.get("legacy_unit") for e in t.get("evidence", [])
    )]
    if len(inherited) != 43:
        raise ValueError("v2 inherited verification count must equal 43")
    received: set[str] = set()
    for task in inherited:
        if task.get("state") != "verified":
            raise ValueError("historical evidence lost from active roadmap")
        for proof in task["evidence"]:
            unit_id = proof.get("legacy_unit")
            if not unit_id:
                continue
            if unit_id not in historical_done or unit_id in received:
                raise ValueError("duplicate or unverified historical capability")
            received.add(unit_id)
            old = historical_done[unit_id]
            if proof.get("url") != old.get("evidence"):
                raise ValueError("foundation evidence provenance lost")
            expected_kind = ("merged_pr" if "/pull/" in old["evidence"]
                             else "historical_receipt")
            if proof.get("type") != expected_kind:
                raise ValueError("historical proof classification mismatch")
            if task.get("issue") != old.get("issue"):
                raise ValueError("historical unit issue mismatch")
            if not task["id"].endswith("-" + unit_id):
                raise ValueError("historical unit mapping mismatch")
    if received != set(historical_done):
        raise ValueError("all original completed work must remain represented")
    for task in tasks.values():
        if task.get("source") == "v1_verified" and not any(
            e.get("legacy_unit") for e in task.get("evidence", [])
        ):
            raise ValueError("inherited task has no original evidence")
        if task.get("source") != "v1_verified" and any(
            e.get("type") == "historical_receipt" for e in task.get("evidence", [])
        ):
            raise ValueError("new work cannot claim a historical receipt")
    for m in milestones.values():
        if type(m.get("priority")) is not int or m["priority"] not in range(5):
            raise ValueError("priority ranking must be P0 through P4")
        if not m.get("workstream") or not m.get("next_action"):
            raise ValueError("workstream and next action required")
    return {
        "phases": len(phases), "milestones": len(milestones),
        "milestones_verified": sum(m["state"] == "verified" for m in milestones.values()),
        "tasks": len(tasks), "tasks_verified": sum(t["state"] == "verified" for t in tasks.values()),
        "transferred_verified_capabilities": len(received),
        "archived_release_units": 61, "archived_atomic_tasks": 73,
    }


def render(data: dict) -> str:
    milestone_by_id = {m["id"]: m for m in data["milestones"]}
    task_by_id = {t["id"]: t for t in data["tasks"]}
    done = sum(m["state"] == "verified" for m in data["milestones"])
    lines = [
        "# Prehnite — one canonical product roadmap",
        "",
        "> Generated from progress/roadmap.json by scripts/roadmap.py. The original",
        "> 61-unit release scope and 73-task register are archived historical evidence,",
        "> not competing active project percentages.",
        "",
        f"**Product outcomes:** {done}/{len(data['milestones'])} milestones verified.  ",
        f"**Scope:** 8 GiB RTX 4070 laptop, measured host RAM; two phases; no 4/6 GiB program.  ",
        "**Evidence rule:** research != code != GPU observations != owner acceptance.",
        "",
        "| Phase | Milestone | State | Evidence gates | Next work |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for phase in data["phases"]:
        for mid in phase["milestones"]:
            m = milestone_by_id[mid]
            count = sum(task_by_id[t]["state"] == "verified" for t in m["gate_tasks"])
            next_ = next((t for t in m["gate_tasks"] if task_by_id[t]["state"] != "verified"), None)
            state = m["state"].replace("_", " ")
            lines.append(
                f"| {escape(phase['id'])} | {escape(mid)} — {escape(m['title'])} "
                f"| {state} | {count}/{len(m['gate_tasks'])} "
                f"| {escape(next_ or 'Milestone evidenced')} |"
            )
    lines += [
        "",
        "## Research, implementation, experiment, acceptance",
        "",
        "Every gate task has one question to answer and one accepted evidence type.",
        "The kinds are not interchangeable; an offline CI success cannot prove visual quality.",
        "",
    ]
    for phase in data["phases"]:
        lines.extend([f"### {escape(phase['id'])} — {escape(phase['name'])}", ""])
        for mid in phase["milestones"]:
            m = milestone_by_id[mid]
            lines.extend([f"#### {escape(mid)} — {escape(m['title'])}", "", m["objective"], ""])
            lines.extend(["| Task | Kind | State | Owner | Acceptance / evidence |",
                          "| --- | --- | --- | --- | --- |"])
            for tid in m["gate_tasks"]:
                task = task_by_id[tid]
                proof = task["acceptance"].replace("|", "/").replace("\n", " ")
                if task["state"] == "verified":
                    proof += "; " + ", ".join(
                        f"[evidence]({entry['url']})" for entry in task["evidence"]
                    )
                lines.append(
                    f"| {tid} | {task['kind']} | {task['state'].replace('_',' ')} "
                    f"| {task['owner']} | {proof} |"
                )
            lines.append("")
    lines += [
        "## Historical evidence (archive only)",
        "",
        "The previous 43/61 released-scope evidence and 21/73 atomic evidence",
        "remain preserved without being counted as parallel active progress.",
        "[Original 61-unit ledger](../../progress/archive/v1/ledger.json) ·",
        "[Original 73-task ledger](../../progress/archive/v1/atomic.json) ·",
        "[Migration notes](../ROADMAP_MIGRATION_V2.md).",
        "",
        "The old 90-image/paid-provider/licensing/administration obligations remain",
        "traceable in the crosswalk. A ten-image local test does not falsely close them.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument("--check", action="store_true")
    commands.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = load()
    verdict = validate(data)
    content = render(data)
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(content, encoding="utf-8")
    elif not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
        raise SystemExit("Product roadmap output stale; run python scripts/roadmap.py --write")
    print(json.dumps(verdict, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
