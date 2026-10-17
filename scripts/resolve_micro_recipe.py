"""Offline-only local model input resolver CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prehnite.recipe_resolver import load_local_bindings, resolve_local_micro
from prehnite.recipes import load_recipe


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--recipe", required=True, type=Path)
    p.add_argument("--bindings", required=True, type=Path)
    p.add_argument("--workflows", required=True, type=Path)
    p.add_argument("--checkpoints", required=True, type=Path)
    args = p.parse_args()
    report = resolve_local_micro(load_recipe(args.recipe),
                                 load_local_bindings(args.bindings),
                                 args.workflows, args.checkpoints)
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
