"""Reproducible offline Kanban snapshot generator. No GitHub API or SaaS needed."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANES = ("Backlog", "Ready", "In progress", "In review", "Blocked", "Done")


def validate_board(board: dict) -> None:
    if board.get("schema_version") != 1:
        raise ValueError("Unsupported board schema")
    if not board.get("iteration", {}).get("id"):
        raise ValueError("Missing iteration identifier")
    seen: set[tuple[str, int]] = set()
    for card in board["cards"]:
        key = (card["type"], card["number"])
        if card["type"] not in ("issue", "pr") or type(card["number"]) is not int:
            raise ValueError("Invalid work item reference")
        if key in seen:
            raise ValueError("Duplicate issue or PR card")
        seen.add(key)
        if card["lane"] not in LANES:
            raise ValueError("Unknown Kanban lane")
        if card["priority"] not in ("P0", "P1", "P2", "P3"):
            raise ValueError("Unknown priority")
    for lane, limit in (("In progress", "max_in_progress"), ("In review", "max_in_review")):
        count = sum(card["lane"] == lane for card in board["cards"])
        if count > board["limits"][limit]:
            raise ValueError(f"WIP limit exceeded in {lane}: {count}")


def render(board: dict) -> str:
    validate_board(board)
    iteration = board["iteration"]
    rows = [
        "# Prehnite — agile iteration board",
        "",
        "> Generated from [`project/board.json`](../project/board.json); use `python scripts/board.py --write` to refresh. GitHub issues and PRs are the authoritative live evidence. This is an offline planning snapshot, **not** a native GitHub Projects board.",
        "",
        f"**Iteration:** {iteration['id']} — {iteration['name']}  ",
        f"**Planning window:** {iteration['start']} → {iteration['review_target']} (review, **not** release deadline)  ",
        f"**Goal:** {iteration['goal']}",
        "",
        "## Flow overview",
        "",
        "| Lane | Cards |",
        "| --- | ---: |",
    ]
    for lane in LANES:
        rows.append(f"| {lane} | {sum(c['lane'] == lane for c in board['cards'])} |")
    rows += [
        "",
        f"**WIP limits:** In progress ≤ {board['limits']['max_in_progress']}; In review ≤ {board['limits']['max_in_review']}. Counts are issue/PR cards, not unique completed engineering features or a percentage.",
        "",
    ]
    for lane in LANES:
        cards = [c for c in board["cards"] if c["lane"] == lane]
        rows += [
            f"## {lane}",
            "",
            "| Priority | Work item | Stream | Handoff / blocker |",
            "| --- | --- | --- | --- |",
        ]
        for c in cards:
            kind = "PR" if c["type"] == "pr" else "Issue"
            path = "pull" if c["type"] == "pr" else "issues"
            url = f"https://github.com/interzettel/prehnite/{path}/{c['number']}"
            note = c["note"].replace("|", "/")
            rows.append(f"| {c['priority']} | [{kind} #{c['number']} — {c['title']}]({url}) | {c['stream']} | {note} |")
        if not cards:
            rows.append("| — | No cards currently | — | — |")
        rows.append("")
    rows += [
        "## How to update this board",
        "",
        "1. Update the relevant issue/PR and post an A2A handoff on [#9](https://github.com/interzettel/prehnite/issues/9).",
        "2. Move the card's `lane` (or add a new card) in `project/board.json`; keep tickets unique by `(type, number)`.",
        "3. Run `python scripts/board.py --write` then `python scripts/board.py --check`, commit both files in the same PR.",
        "4. CI verifies that status snapshot matches the machine-readable board and WIP caps.",
        "5. Track **release evidence** separately in `docs/PROGRESS.md` (introduced by PR #10); this board tracks workflow, not model performance.",
        "",
        "**Release policy:** No tags, releases or uploads have been authorized. See [versioning](VERSIONING.md), [changelog](../CHANGELOG.md) and [release process](RELEASING.md).",
        "",
    ]
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or regenerate offline issue-backed Kanban")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        board = json.loads((ROOT / "project" / "board.json").read_text(encoding="utf-8"))
        result = render(board)
        target = ROOT / "docs" / "SPRINT.md"
        if args.write:
            target.write_text(result, encoding="utf-8")
            print("Updated docs/SPRINT.md")
            return 0
        if not target.is_file() or target.read_text(encoding="utf-8") != result:
            print("Stale board snapshot: run python scripts/board.py --write", file=sys.stderr)
            return 1
        print("Board snapshot and WIP limits verified")
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Invalid board: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
