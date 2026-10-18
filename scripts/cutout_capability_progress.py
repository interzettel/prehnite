"""Evidence-linked cutout capability tracker; independent of release gates."""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "progress" / "cutout_capability.json"
OUTPUT = ROOT / "docs" / "progress" / "CUTOUT_CAPABILITY.md"
STATES = {"done", "blocked", "planned"}
KINDS = {
    "operator_report": "Private operator report",
    "independent_visual": "Independent artifact review",
    "merged_pr": "Merged public PR",
    "merged_test": "Merged regression test",
}
LINK = re.compile(r"https://github[.]com/interzettel/prehnite/(pull/[1-9][0-9]*|blob/main/[A-Za-z0-9_./-]+)\Z")


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def validate(data: dict) -> None:
    if data.get("schema_version") != 1 or data.get("scope_id") != "cutout-capability-2026-10-18":
        raise ValueError("Unknown or changed capability scope")
    if data.get("baseline_date") != "2026-10-18" or data.get("fixed_milestone_count") != 13:
        raise ValueError("Frozen baseline or denominator changed")
    if date.fromisoformat(data["updated"]) < date.fromisoformat(data["baseline_date"]):
        raise ValueError("Update predates baseline")
    if data.get("groups") != ["Local proof", "Merged software", "Real-world validation"]:
        raise ValueError("Capability groups changed")
    items = data.get("milestones")
    if not isinstance(items, list) or len(items) != 13:
        raise ValueError("Capability scope drift")
    if [m.get("id") for m in items] != [
        "LP01", "LP02", "LP03", "LP04", "SW01", "SW02", "SW03", "SW04",
        "VL01", "VL02", "VL03", "VL04", "VL05"
    ]:
        raise ValueError("Capability milestone IDs changed")
    for item in items:
        if item.get("group") not in data["groups"]:
            raise ValueError("Invalid group")
        if item.get("state") not in STATES or not all(
            isinstance(item.get(field), str) and 20 <= len(item[field]) <= 250
            and "|" not in item[field] for field in ("title", "acceptance")
        ):
            raise ValueError("Invalid state or acceptance")
        if item["state"] == "done":
            if not isinstance(item.get("evidence"), str) or not LINK.fullmatch(item["evidence"]):
                raise ValueError("Completed milestone requires linked evidence")
            if item.get("evidence_kind") not in KINDS or "blocker" in item:
                raise ValueError("Invalid completion evidence")
        else:
            if "evidence" in item or "evidence_kind" in item:
                raise ValueError("Incomplete milestone cannot claim evidence")
            if item["state"] == "blocked" and (
                not isinstance(item.get("blocker"), str) or len(item["blocker"]) < 20
            ):
                raise ValueError("Blocked milestone needs a concrete reason")
            if item["state"] == "planned" and "blocker" in item:
                raise ValueError("Planned milestone cannot claim blocker")


def headline(data: dict) -> str:
    validate(data)
    n = sum(item["state"] == "done" for item in data["milestones"])
    total = len(data["milestones"])
    return f"Focused cutout capability: {n}/{total} ({100 * n / total:.1f}%)"


def render(data: dict) -> str:
    validate(data)
    counts = Counter(item["state"] for item in data["milestones"])
    lines = [
        "# Prehnite — cutout capability progress",
        "",
        "> Fixed 2026-10-18 scope: local proof to reusable public source to real-world validation. This is NOT the release-roadmap percentage or a product-quality score.",
        "",
        f"**{headline(data)}** · {counts['blocked']} blocked · {counts['planned']} planned.",
        "",
        "**Separate release criteria:** [42/61 original delivery units](STATUS.md) and [14/73 atomic unfinished-scope tasks](ATOMIC.md) remain independently governed. No credits are transferred between trackers.",
        "",
        "**Evidence standard:** a done outcome links to a merged PR, merged test, or a dated index of explicitly labeled private operator/independent visual evidence. Source implementation does not imply a second real-object acceptance.",
        "",
        f"**Counting policy:** {data['counting_rule']}",
        "",
    ]
    for group in data["groups"]:
        rows = [item for item in data["milestones"] if item["group"] == group]
        passed = sum(row["state"] == "done" for row in rows)
        lines += [
            f"## {group} — {passed}/{len(rows)}", "",
            "| ID | Outcome | State | Required acceptance | Evidence or blocker |",
            "| --- | --- | --- | --- | --- |",
        ]
        for item in rows:
            if item["state"] == "done":
                support = f"[{KINDS[item['evidence_kind']]}]({item['evidence']})"
            elif item["state"] == "blocked":
                support = item["blocker"]
            else:
                support = "Not yet demonstrated"
            lines.append(
                f"| {item['id']} | {item['title']} | {item['state']} | "
                f"{item['acceptance']} | {support} |"
            )
        lines.append("")
    lines += [
        "## Interpretation",
        "",
        "This percentage measures a fixed cutout workstream, not how much of Prehnite is finished. The public CLI and QA contracts are merged; the next rights-cleared non-lamp image, resource-safe execution, bound execution receipt, Engine integration and diverse quality benchmark remain incomplete. Never promote them based on a synthetic test or one lamp.",
        "",
        "Source: [progress/cutout_capability.json](../../progress/cutout_capability.json). Regenerate with python scripts/cutout_capability_progress.py --write and verify with --check.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = load()
    doc = render(data)
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(doc, encoding="utf-8")
        print("Capability report updated. Reconcile README and docs/PROGRESS headlines.")
    else:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != doc:
            raise SystemExit("Cutout capability report is stale; use --write.")
        for summary in (ROOT / "README.md", ROOT / "docs" / "PROGRESS.md"):
            if headline(data) not in summary.read_text(encoding="utf-8"):
                raise SystemExit(f"Capability headline is stale: {summary}")
        print("Capability scope, report, and displayed headlines verified")


if __name__ == "__main__":
    main()
