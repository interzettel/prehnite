"""Read-only verification for a versioned Prehnite model blueprint.

python scripts/recipe_plan.py --recipe recipes/prehnite-micro/0.1.0-preview.1.json
Prints contract fingerprint and explicit 'executable: false'. Never contacts
providers, downloads weights, or executes any workflow stage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prehnite.recipes import describe_recipe, load_recipe


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--recipe", required=True, type=Path)
    args = p.parse_args()
    description = describe_recipe(load_recipe(args.recipe))
    print(json.dumps(description, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
