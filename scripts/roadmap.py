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
    old_atomic_done = {t["id"]: t for t in old_atomic["tasks"] if t["state"] == "done"}
    original_folded = {key for key, t in old_atomic_done.items() if t["parent"] == "S04"}
    receipt_ids = data.get("migration_integrity", {}).get("carried_forward_atomic_ids")
    folded = data.get("migration_integrity", {}).get("folded_atomic_ids")
    if (not isinstance(receipt_ids, list) or not isinstance(folded, list)
            or len(receipt_ids) != 17 or len(folded) != 4
            or set(receipt_ids) != set(old_atomic_done) - original_folded
            or set(folded) != original_folded):
        raise ValueError("atomic receipts must carry 17 distinct and fold 4 overlapping tasks")
    actual = set()
    for task in tasks.values():
        atomic_proofs = [p for p in task["evidence"] if p.get("legacy_atomic_id")]
        if task.get("source") == "v1_atomic_verified" and len(atomic_proofs) != 1:
            raise ValueError("atomic source requires one original receipt")
        if task.get("source") != "v1_atomic_verified" and atomic_proofs:
            raise ValueError("only original atomic sources may claim original receipt")
        for proof in atomic_proofs:
            id_ = proof["legacy_atomic_id"]
            if id_ in actual or id_ not in old_atomic_done or id_ in original_folded:
                raise ValueError("duplicate or missing original atomic task")
            actual.add(id_)
            old = old_atomic_done[id_]
            if (proof.get("url") != old.get("evidence")
                    or proof.get("type") != "merged_pr"
                    or task.get("issue") != old["issue"]
                    or task["id"][-len(id_):] != id_):
                raise ValueError("original atomic evidence provenance lost")
    if actual != set(receipt_ids):
        raise ValueError("atomic subtask evidence missing")
    parent_s04 = next((t for t in tasks.values() if t.get("original_unit") == "S04"), None)
    if parent_s04 is None or set(parent_s04.get("folded_atomic_subtasks", [])) != original_folded:
        raise ValueError("overlapping S04 work must be folded into its verified parent")
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
        "transferred_distinct_atomic": len(actual),
        "folded_duplicate_atomic": len(original_folded),
        "archived_release_units": 61, "archived_atomic_tasks": 73,
    }


def render(data: dict) -> str:
    """Render the one active progress view with granular task and outcome scores."""
    by_id = {t["id"]: t for t in data["tasks"]}
    total = len(by_id)
    done = sum(t["state"] == "verified" for t in by_id.values())
    m_done = sum(m["state"] == "verified" for m in data["milestones"])
    milestones = sorted(data["milestones"], key=lambda m: (m["priority"], m["id"]))
    lines = [
        "# Prehnite | Product progress", "",
        f"**Engineering tasks verified: {done}/{total} ({100 * done / total:.1f}%).**  ",
        f"**Outcome milestones accepted: {m_done}/{len(milestones)} "
        f"({100 * m_done / len(milestones):.1f}%).**", "",
        "Engineering task completion includes original reviewed implementation receipts. "
        "Outcome acceptance additionally requires real laptop tests, usable images, "
        "and human review. Neither percentage alone is a product-quality certificate.", "",
        "## Prioritized workstreams", "",
        "| Priority | Workstream | Work evidenced | Completion | Outcome | Next missing task |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for m in milestones:
        gate = [by_id[t] for t in m["gate_tasks"]]
        count = sum(t["state"] == "verified" for t in gate)
        next_task = next((t["id"] for t in gate if t["state"] != "verified"), "All gates evidenced")
        state = "Accepted" if m["state"] == "verified" else (
            "Blocked" if m["state"] == "blocked" else "Open"
        )
        lines.append(
            f"| P{m['priority']} | {m['id']}: {m['workstream']} | "
            f"{count}/{len(gate)} | {100 * count / len(gate):.1f}% | "
            f"{state} | {next_task} |"
        )
    lines += [
        "", "## What is needed next", "",
        "Listed by priority, not by number of commits or the size of a previous release.",
        ""
    ]
    for m in milestones:
        if m["state"] == "verified":
            continue
        pending = [by_id[t] for t in m["gate_tasks"] if by_id[t]["state"] != "verified"]
        lines.append(
            f"- **P{m['priority']} · {m['id']} · {m['title']}**: "
            f"{m['next_action']}. "
            f"Next: {pending[0]['id']} ({pending[0]['kind']}); "
            f"{len(pending)} outstanding."
        )
    lines += ["", "## Detailed task evidence", "",
              "Each row is one work item counted once. Imported technical achievements "
              "are scoped to the originally verified implementation, never to new "
              "physical or human acceptance.", ""]
    for m in sorted(data["milestones"], key=lambda v: (v["phase"], v["id"])):
        gates = [by_id[t] for t in m["gate_tasks"]]
        count = sum(t["state"] == "verified" for t in gates)
        lines += [
            f"### {m['id']} · {m['title']} ({count}/{len(gates)}; "
            f"{100 * count / len(gates):.1f}%)", "",
            "| Task | Kind | State | Evidence / required outcome |",
            "| --- | --- | --- | --- |"
        ]
        for t in gates:
            if t.get("original_unit"):
                proof = "Previously verified source unit " + t["original_unit"]
            else:
                proof = t["acceptance"]
            proof = proof.replace("|", "/").replace("\n", " ")
            if t["state"] == "verified":
                proof += ": " + ", ".join(
                    f"[evidence]({e['url']})" for e in t["evidence"]
                )
            lines.append(
                f"| {t['id']} | {t['kind']} | "
                f"{t['state'].replace('_', ' ')} | {proof} |"
            )
        lines.append("")
    lines += [
        "## Evidence and permission rules", "",
        "A research review, merged implementation, hardware experiment, and human "
        "quality decision are different types of evidence. An unapproved CUDA run, "
        "unverified API billing, and a synthetic image cannot complete those gates.", "",
        "[Canonical machine-readable roadmap](../../progress/roadmap.json) · "
        "[Milestone acceptance definitions](../PRODUCT_MILESTONES.md).", ""
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
