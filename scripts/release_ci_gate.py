#!/usr/bin/env python3
"""Select a successful same-commit main-branch CI push run for an approved alpha.

Uses only the GitHub Actions read token. No release mutation or inference.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from urllib.request import Request, urlopen


def select_verified_ci_run(runs: list[dict], commit: str) -> int:
    """Never accept a passing PR merge ref, different commit, or workflow."""
    eligible = [
        run for run in runs
        if run.get("head_sha") == commit
        and run.get("head_branch") == "main"
        and run.get("event") == "push"
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and run.get("name") == "CI"
        and isinstance(run.get("id"), int)
    ]
    if not eligible:
        raise ValueError("No completed successful main push CI run exists at the selected exact SHA")
    return max(run["id"] for run in eligible)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    args = parser.parse_args()

    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        raise SystemExit("GITHUB_SHA must be an exact 40-character commit digest")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        raise SystemExit("Invalid GitHub repository identity")
    if args.repository != "interzettel/prehnite":
        raise SystemExit("Publishing gate is restricted to the registered repository")
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        raise SystemExit("Missing read-only GitHub Actions token")
    url = (f"https://api.github.com/repos/{args.repository}/actions/workflows/ci.yml/runs"
           "?event=push&branch=main&per_page=100")
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    run_id = select_verified_ci_run(payload["workflow_runs"], args.sha)
    print(run_id)


if __name__ == "__main__":
    main()
