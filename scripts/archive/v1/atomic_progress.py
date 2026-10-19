"""Deterministic, evidence-only progress for PR-sized atomic work."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import date
from html import escape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATES = ("done", "in_review", "active", "blocked", "planned")
COLORS = {"done":"#075231","in_review":"#E5955B","active":"#DAA76E",
          "blocked":"#A63D35","planned":"#D5DCD5"}
PULL = re.compile(r"https://github[.]com/interzettel/prehnite/pull/[1-9][0-9]*\Z")
TASK_ID = re.compile(r"([A-Z][A-Z0-9]*[0-9]{2})-A[0-9]{2}\Z")

def load():
    return (json.loads((ROOT/"progress/ledger.json").read_text(encoding="utf-8")),
            json.loads((ROOT/"progress/atomic.json").read_text(encoding="utf-8")))

def validate(ledger, atomics):
    if atomics.get("schema_version") != 1 or atomics.get("parent_ledger") != "progress/ledger.json":
        raise ValueError("Unknown atomic schema or parent ledger")
    if atomics.get("baseline_date") != "2026-10-17":
        raise ValueError("Baseline cannot be silently reset")
    now = date.fromisoformat(atomics["updated"])
    if now < date.fromisoformat(atomics["baseline_date"]):
        raise ValueError("Invalid update date")
    parents = {u["id"]:u for m in ledger["milestones"] for u in m["units"]}
    if len(parents) != 61:
        raise ValueError("Original 61-unit release scope changed")
    baseline = atomics.get("baseline_open_parent_ids")
    if (not isinstance(baseline,list) or baseline != sorted(set(baseline))
            or len(baseline) != 19 or set(baseline)-parents.keys()):
        raise ValueError("Invalid or changed 19-parent baseline")
    tasks = atomics.get("tasks")
    if not isinstance(tasks,list) or len(tasks) != atomics.get("baseline_task_count"):
        raise ValueError("Frozen atomic denominator drift")
    seen, counts = {},Counter()
    for t in tasks:
        if not isinstance(t,dict):
            raise ValueError("Invalid task object")
        key = t.get("id")
        match = TASK_ID.fullmatch(key) if isinstance(key,str) else None
        if not match or key in seen or t.get("parent") != match.group(1) or t["parent"] not in baseline:
            raise ValueError("Duplicate, invalid or orphan atomic ID")
        parent = parents[t["parent"]]
        if t.get("issue") != parent["issue"] or t.get("owner") != parent["owner"]:
            raise ValueError("Atomic issue or owner does not match parent")
        if not isinstance(t.get("title"),str) or not 15 <= len(t["title"]) <= 120:
            raise ValueError("Task title must fit one PR")
        if not isinstance(t.get("acceptance"),str) or not 25 <= len(t["acceptance"]) <= 280:
            raise ValueError("Missing bounded testable acceptance")
        status=t.get("state")
        if status not in STATES:
            raise ValueError("Unknown task state")
        if status=="done":
            if (not isinstance(t.get("evidence"),str) or not PULL.fullmatch(t["evidence"])
                    or any(k in t for k in ("review_url","blocker"))):
                raise ValueError("Done task lacks valid merged PR evidence")
            if (not isinstance(t.get("verified_at"),str)
                    or date.fromisoformat(t["verified_at"])>now):
                raise ValueError("Invalid verification date")
        elif status=="in_review":
            if (not isinstance(t.get("review_url"),str) or not PULL.fullmatch(t["review_url"])
                    or any(k in t for k in ("evidence","verified_at","blocker"))):
                raise ValueError("In review is not done")
        elif status=="blocked":
            if (not isinstance(t.get("blocker"),str) or len(t["blocker"])<20
                    or any(k in t for k in ("evidence","verified_at","review_url"))):
                raise ValueError("Blocked task needs explicit owner/unblocking action")
        elif any(k in t for k in ("evidence","verified_at","review_url","blocker")):
            raise ValueError("Unverified task cannot carry completion evidence")
        if (not isinstance(t.get("dependsOn"),list)
                or len(t["dependsOn"])!=len(set(t["dependsOn"]))):
            raise ValueError("Invalid atomic dependency list")
        seen[key]=t
        counts[t["parent"]]+=1
    if set(counts)!=set(baseline) or min(counts.values())<2:
        raise ValueError("Every parent must retain at least two atomic tasks")
    if any(parents[p]["state"]=="done" and any(t["state"]!="done" for t in tasks if t["parent"]==p)
           for p in baseline):
        raise ValueError("Cannot close parent while atomic acceptance is incomplete")
    visited, stack=set(),set()
    def visit(key):
        if key in stack: raise ValueError("Atomic dependency cycle")
        if key in visited: return
        stack.add(key)
        for dep in seen[key]["dependsOn"]:
            if dep not in seen or dep==key:
                raise ValueError("Unknown/self atomic dependency")
            if seen[key]["state"]=="done" and seen[dep]["state"]!="done":
                raise ValueError("Premature atomic completion")
            visit(dep)
        stack.remove(key); visited.add(key)
    for key in seen: visit(key)

def counts(ledger, atomic):
    validate(ledger,atomic)
    legacy=[u for m in ledger["milestones"] for u in m["units"]]
    c=Counter(t["state"] for t in atomic["tasks"])
    return {"parent_done":sum(x["state"]=="done" for x in legacy),
            "parent_total":len(legacy),"task_total":len(atomic["tasks"]),
            **{state:c[state] for state in STATES}}

def pct(n,total):
    return f"{100*n/total:.2f}%" if total else "0.00%"

def render_md(ledger,atomic):
    c=counts(ledger,atomic)
    parent={u["id"]:u for m in ledger["milestones"] for u in m["units"]}
    groups=defaultdict(list)
    for t in atomic["tasks"]: groups[t["parent"]].append(t)
    L=[
        "# Prehnite — atomic delivery tracker","",
        "> Generated by scripts/atomic_progress.py from progress/atomic.json. These task counts are verified delivery evidence, NOT effort estimates, release readiness or image quality.","",
        f"**Release roadmap:** {c['parent_done']}/{c['parent_total']} ({pct(c['parent_done'],c['parent_total'])}) — [61-unit ledger](STATUS.md).  ",
        f"**Atomic delivery in the frozen unfinished scope:** {c['done']}/{c['task_total']} ({pct(c['done'],c['task_total'])}) · in review {c['in_review']} · active {c['active']} · blocked {c['blocked']} · planned {c['planned']}.","",
        "![Independent release and atomic progress](atomic.svg)","",
        f"**Scope baseline:** {atomic['baseline_date']} · **Last registry update:** {atomic['updated']} · **Frozen scope:** {atomic['baseline_task_count']} tasks under 19 unfinished release units.","",
        "The atomic percentage measures ONLY scoped tasks under units unfinished at the baseline. It is not an overall project completion score. One merged PR can prove multiple distinct acceptance checks but does not automatically complete its parent. In-review PRs and GitHub Project cards never earn done credit.","",
        "## Breakdown by parent roadmap unit","",
        "| Unit | Atomic evidence | Review | Blocked | Planned/active | Parent state |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for p in atomic["baseline_open_parent_ids"]:
        z=Counter(x["state"] for x in groups[p]); length=len(groups[p])
        L.append(f"| {p} — {parent[p]['name']} | {z['done']}/{length} ({pct(z['done'],length)}) | {z['in_review']} | {z['blocked']} | {z['planned']+z['active']} | {parent[p]['state']} |")
    L+=["","## Recently verified atomic tasks","","| Date | Task | Merged evidence |","| --- | --- | --- |"]
    recent=sorted((t for t in atomic["tasks"] if t["state"]=="done"),key=lambda t:(t["verified_at"],t["id"]),reverse=True)
    for t in recent[:10]:
        L.append(f"| {t['verified_at']} | {t['id']} — {t['title']} | [PR]({t['evidence']}) |")
    L+=["","## Agent-ready tasks and acceptance criteria",""]
    for p in atomic["baseline_open_parent_ids"]:
        L += [f"### {p} — {parent[p]['name']}","","| Task | State | Acceptance criterion | Issue, blocker or evidence |","| --- | --- | --- | --- |"]
        for t in groups[p]:
            link=(f"[Merged PR]({t['evidence']})" if t["state"]=="done"
                else f"[PR in review]({t['review_url']})" if t["state"]=="in_review"
                else t["blocker"] if t["state"]=="blocked"
                else f"[Issue #{t['issue']}](https://github.com/interzettel/prehnite/issues/{t['issue']})")
            L.append(f"| {t['id']} — {t['title']} | {t['state']} | {t['acceptance']} | {link} |")
        L.append("")
    L += ["## Agent workflow","",
        "1. Claim exactly one atomic ID on A2A issue #9 and its linked parent issue. Follow the acceptance criterion with one bounded PR.",
        "2. Mark in_review and link the open PR; this does not earn progress.",
        "3. Only after green CI, review and MERGE mark done with the merged PR URL and verified_at date.",
        "4. Run python scripts/atomic_progress.py --write, and commit register, generated Markdown and SVG in the same PR.",
        "5. Advance the separate 61-unit ledger only when the full parent criteria and dependency gates are complete; run python scripts/progress.py --write separately.",
        "6. The original 73-task denominator is frozen. Any new work scope needs an explicit reviewed version/baseline migration, never silent removal of incomplete tasks.","",
        "Native GitHub Projects v2 syncing remains a separate issue #44; a Kanban card is not verified task evidence.",""]
    return "\n".join(L)

def render_svg(ledger,atomic):
    c=counts(ledger,atomic)
    parent={u["id"]:u for m in ledger["milestones"] for u in m["units"]}
    groups=defaultdict(list)
    for t in atomic["tasks"]: groups[t["parent"]].append(t)
    h=360+39*len(atomic["baseline_open_parent_ids"])
    a=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="{h}" viewBox="0 0 1100 {h}" role="img" aria-labelledby="title desc">',
       '<title id="title">Prehnite roadmap and atomic delivery progress</title>',
       '<desc id="desc">Separate verified 61-unit release roadmap and verified tasks under the frozen 19 unfinished-unit baseline. The second percentage is not total project completeness.</desc>',
       f'<rect width="1100" height="{h}" fill="#F6EFE2"/>',
       '<g font-family="system-ui,Segoe UI,Arial,sans-serif">',
       '<text x="32" y="43" font-size="27" font-weight="700" fill="#075231">PREHNITE / DELIVERY EVIDENCE</text>',
       '<text x="32" y="70" font-size="14" fill="#384F45">Two independent meters: merged proof only, not visual acceptance or estimated effort.</text>']
    for label,done,total,y in (("Release roadmap / original 61 units",c["parent_done"],c["parent_total"],105),
                               ("Atomic delivery / initially unfinished 19 units",c["done"],c["task_total"],190)):
        a.extend([
            f'<text x="32" y="{y}" font-size="16" font-weight="600" fill="#075231">{escape(label)}</text>',
            f'<text x="1060" y="{y}" font-size="18" font-weight="700" text-anchor="end" fill="#075231">{done}/{total} · {pct(done,total)}</text>',
            f'<rect x="32" y="{y+13}" width="810" height="18" rx="5" fill="#D5DCD5"/>',
            f'<rect x="32" y="{y+13}" width="{810*done/total:.1f}" height="18" rx="5" fill="#075231"/>'])
    a += ['<text x="32" y="249" font-size="13" fill="#53675A">Second measure covers only frozen open-unit tasks, never an overall completion estimate.</text>',
          f'<text x="32" y="273" font-size="13" fill="#53675A">Review {c["in_review"]} · Active {c["active"]} · Blocked {c["blocked"]} · Planned {c["planned"]} · baseline {escape(atomic["baseline_date"])}</text>',
          '<text x="32" y="305" font-size="16" font-weight="600" fill="#075231">PR-SIZED TASKS BY UNFINISHED UNIT</text>']
    for index,p in enumerate(atomic["baseline_open_parent_ids"]):
        y=333+index*39;group=groups[p]; n=len(group); segment=415/n
        z=sum(t["state"]=="done" for t in group)
        a.extend([f'<text x="32" y="{y}" font-size="14" font-weight="700" fill="#075231">{escape(p)}</text>',
                  f'<text x="120" y="{y}" font-size="12" fill="#384F45">{escape(parent[p]["name"][:43])}</text>'])
        for i,t in enumerate(group):
            a.append(f'<g><title>{escape(t["id"]+" / "+t["state"]+" / "+t["title"])}</title><rect x="{565+i*segment:.2f}" y="{y-14}" width="{segment-3:.2f}" height="17" rx="2" fill="{COLORS[t["state"]]}"/></g>')
        a.append(f'<text x="1060" y="{y}" font-size="13" text-anchor="end" fill="#075231">{z}/{n}</text>')
    a += [f'<text x="32" y="{h-20}" font-size="12" fill="#53675A">Green done · Orange review · Amber active · Coral blocked · Grey planned · registry {escape(atomic["updated"])}</text>',
          '</g></svg>',""]
    return "\n".join(a)

def outputs(ledger,atomic):
    return {ROOT/"docs/progress/ATOMIC.md":render_md(ledger,atomic),
            ROOT/"docs/progress/atomic.svg":render_svg(ledger,atomic)}

def main():
    parser=argparse.ArgumentParser()
    g=parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--write",action="store_true")
    g.add_argument("--check",action="store_true")
    args=parser.parse_args()
    ledger,atomic=load()
    artifacts=outputs(ledger,atomic)
    if args.write:
        for path,data in artifacts.items():
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(data,encoding="utf-8")
        print("Atomic tracker regenerated; original 61-unit ledger untouched.")
    else:
        for path,data in artifacts.items():
            if not path.is_file() or path.read_text(encoding="utf-8")!=data:
                raise SystemExit(f"Stale atomic progress: {path}. Run python scripts/atomic_progress.py --write")
        print("Atomic progress and sealed scope verified.")

if __name__=="__main__":
    main()
