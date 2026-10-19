"""Prehnite evidence ledger: deterministic offline progress report and SVG.

Done means a scoped unit has evidence; it does not measure visual quality.
"""
import argparse
import json
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = ("done", "active", "blocked", "planned")
COLORS = {"done": "#277e74", "active": "#c28b4a", "blocked": "#b8534e", "planned": "#dce0dd"}


def units(data):
    return [u for m in data["milestones"] for u in m["units"]]


def validate(data):
    if data["schema_version"] != 1:
        raise ValueError("Unknown ledger schema")
    all_ = units(data)
    by_id = {u["id"]: u for u in all_}
    if len(by_id) != len(all_):
        raise ValueError("Duplicate unit IDs")
    mids = [m["id"] for m in data["milestones"]]
    if len(set(mids)) != len(mids):
        raise ValueError("Duplicate milestones")
    for u in all_:
        if not re.fullmatch(r"[A-Z][A-Z0-9]*[0-9]{2}", u["id"]):
            raise ValueError("Invalid ID")
        if u["state"] not in STATES or u["owner"] not in data["lanes"]:
            raise ValueError("Invalid state or owner lane")
        if not isinstance(u["issue"], int) or u["issue"] < 1:
            raise ValueError("Missing GitHub issue/PR number")
        if u["state"] == "done":
            if not u.get("evidence", "").startswith("https://github.com/interzettel/prehnite/"):
                raise ValueError("Completed unit missing a verifiable evidence link")
        for dep in u.get("dependsOn", []):
            if dep not in by_id:
                raise ValueError(f"Unknown prerequisite {dep}")
            if u["state"] == "done" and by_id[dep]["state"] != "done":
                raise ValueError(f"Premature completion: {u['id']}")
    visited, stack = set(), set()
    def visit(key):
        if key in stack:
            raise ValueError("Dependency cycle")
        if key in visited:
            return
        stack.add(key)
        for dep in by_id[key].get("dependsOn", []):
            visit(dep)
        stack.remove(key)
        visited.add(key)
    for key in by_id:
        visit(key)
    for m in data["milestones"]:
        if not m["gate"] or not set(m["gate"]).issubset({u["id"] for u in m["units"]}):
            raise ValueError("Invalid milestone gate")


def stats(values):
    counts = {s: sum(u["state"] == s for u in values) for s in STATES}
    counts["total"] = len(values)
    counts["pct"] = 100 * counts["done"] / len(values) if values else 0
    return counts


def render_svg(data):
    validate(data)
    groups = data["milestones"]
    all_ = units(data)
    overall = stats(all_)
    height = 180 + len(groups) * 112 + 65
    x = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-label="Prehnite evidence-backed milestone progress">',
        f'<rect width="1200" height="{height}" fill="#f6f7f4"/>',
        '<g font-family="system-ui,Segoe UI,sans-serif">',
        '<text x="35" y="48" font-size="27" font-weight="700" fill="#182a27">PREHNITE / DEVELOPMENT PROGRESS</text>',
        f'<text x="35" y="79" font-size="16" fill="#5c6c65">{overall["done"]} / {overall["total"]} scoped units done · {overall["pct"]:.1f}%</text>',
        f'<text x="1160" y="49" text-anchor="end" font-size="17" fill="#277e74">{sum(all(next(u for u in m["units"] if u["id"] == gate)["state"] == "done" for gate in m["gate"]) for m in groups)}/{len(groups)} milestone gates</text>',
        '<text x="35" y="106" font-size="13" fill="#5c6c65">Unweighted work units · evidence required for completion · not a product quality score</text>',
    ]
    lx = 35
    for state, label in (("done", "Done"), ("active", "Active"), ("blocked", "Blocked"), ("planned", "Planned")):
        x += [f'<rect x="{lx}" y="126" width="13" height="13" rx="2" fill="{COLORS[state]}"/>',
              f'<text x="{lx+21}" y="138" font-size="13" fill="#283832">{label} {overall[state]}</text>']
        lx += 188
    for i, m in enumerate(groups):
        y = 171 + 112 * i
        values = m["units"]
        s = stats(values)
        reached = all(next(u for u in values if u["id"] == key)["state"] == "done" for key in m["gate"])
        x += [
            f'<rect x="35" y="{y}" width="1130" height="103" rx="10" fill="#fff" stroke="#d8ddd7"/>',
            f'<text x="55" y="{y+25}" font-size="17" font-weight="650" fill="#1d302b">{escape(m["id"]+" · "+m["name"])}</text>',
            f'<text x="1140" y="{y+25}" font-size="16" text-anchor="end" font-weight="650" fill="#277e74">{s["done"]}/{s["total"]} · {s["pct"]:.1f}%</text>',
            f'<text x="55" y="{y+48}" font-size="12" fill="#65756e">{escape(m["goal"])}</text>',
        ]
        n = len(values)
        cw = (1085 - (n-1)*3) // n
        for j, u in enumerate(values):
            px = 55 + j * (cw+3)
            tooltip = escape(f'{u["id"]}: {u["name"]} [{u["state"]}] issue/PR #{u["issue"]}')
            x.append(f'<g><title>{tooltip}</title><rect x="{px}" y="{y+65}" width="{cw}" height="16" rx="2" fill="{COLORS[u["state"]]}"/></g>')
        gate_label = "Gate reached" if reached else "Open gate: "+", ".join(k for k in m["gate"] if next(u for u in values if u["id"] == k)["state"] != "done")
        x.append(f'<text x="1140" y="{y+95}" text-anchor="end" font-size="11" fill="#6b7972">{escape(gate_label)}</text>')
    x += [
        f'<text x="35" y="{height-32}" font-size="12" fill="#52665e">Details: docs/progress/STATUS.md · Canonical data: progress/ledger.json · {escape(data["updated"])}</text>',
        '</g>', '</svg>',
    ]
    return "\n".join(x)+"\n"


def render_markdown(data):
    validate(data)
    all_ = units(data)
    s = stats(all_)
    groups = data["milestones"]
    reached = sum(all(next(u for u in m["units"] if u["id"] == gate)["state"] == "done" for gate in m["gate"]) for m in groups)
    lines = [
        "# Prehnite — evidence-based delivery progress", "",
        "> Generated from §progress/ledger.json§ by §scripts/progress.py§. A unit counts only when done with evidence; percentages are not estimates of engineering time or visual quality.", "",
        f"**{s['done']} / {s['total']} units done ({s['pct']:.1f}%)** · {s['active']} active · {s['blocked']} blocked · {s['planned']} planned.",
        f"**Milestone gates reached:** {reached} / {len(groups)}.", "",
        "![Milestone progress chart](progress.svg)", "",
        "## Milestone roadmap", "",
        "| Milestone | Done | Active | Blocked | Planned | Gate |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for m in groups:
        x = stats(m["units"])
        open_gate = [g for g in m["gate"] if next(u for u in m["units"] if u["id"] == g)["state"] != "done"]
        gate = "Reached" if not open_gate else "Open: "+", ".join(open_gate)
        lines.append(f"| {m['id']} · {m['name']} | {x['done']}/{x['total']} ({x['pct']:.1f}%) | {x['active']} | {x['blocked']} | {x['planned']} | {gate} |")
    lines += ["", "## Work units", ""]
    for m in groups:
        lines += [f"### {m['id']} · {m['name']}", "",
                  "| ID | Work package | State | Lane | Depends on | Issue/evidence |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for u in m["units"]:
            deps = ", ".join(u["dependsOn"]) or "—"
            url = u.get("evidence", f"https://github.com/interzettel/prehnite/issues/{u['issue']}")
            link = f"[Evidence]({url})" if u["state"] == "done" else f"[#{u['issue']}]({url})"
            lines.append(f"| §{u['id']}§ | {u['name']} | {u['state']} | {u['owner']} | {deps} | {link} |")
        lines.append("")
    lines += ["## Counting rule", "", data["counting_rule"], "",
              "Done requires inspectable linked evidence and completed dependencies; milestone attainment requires every named gate. The separate [technical readiness report](../PROGRESS.md) evaluates release risks. Native [GitHub Project #1](https://github.com/orgs/interzettel/projects/1) tracks workflow, not quality. Agents hand off in [issue #9](https://github.com/interzettel/prehnite/issues/9).", ""]
    return "\n".join(lines).replace("§", chr(96))


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.loads((ROOT/"progress/ledger.json").read_text(encoding="utf-8"))
    outputs = {
        ROOT/"docs/progress/progress.svg": render_svg(data),
        ROOT/"docs/progress/STATUS.md": render_markdown(data),
    }
    if args.write:
        for file, content in outputs.items():
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content, encoding="utf-8")
        print("Progress outputs updated")
    else:
        for file, content in outputs.items():
            if not file.is_file() or file.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Stale progress output {file}; run python scripts/progress.py --write")
        print("Evidence ledger and generated reports verified")


if __name__ == "__main__":
    main()
