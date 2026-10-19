"""Compatibility entrypoint for the canonical v2 roadmap validator.

Only progress/roadmap.json counts towards current product completion.
"""
from __future__ import annotations

import json
from roadmap import load, validate


if __name__ == "__main__":
    print(json.dumps(validate(load()), indent=2, sort_keys=True))
