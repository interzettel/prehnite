"""Ensure installed metadata and source versions cannot silently diverge."""
from __future__ import annotations

import ast
import importlib.metadata
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT / "src" / "prehnite" / "_version.py"


def source_version() -> str:
    module = ast.parse(VERSION_PATH.read_text(encoding="utf-8"))
    versions = [
        item.value.value
        for item in module.body
        if isinstance(item, ast.Assign)
        and len(item.targets) == 1
        and isinstance(item.targets[0], ast.Name)
        and item.targets[0].id == "__version__"
        and isinstance(item.value, ast.Constant)
        and isinstance(item.value.value, str)
    ]
    if len(versions) != 1:
        raise ValueError("Canonical version file must contain one literal __version__")
    value = versions[0]
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc|\.dev)\d+)?", value):
        raise ValueError("Version must follow the project's PEP 440 subset")
    return value


def check() -> str:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    if "version" in project or "version" not in project.get("dynamic", []):
        raise ValueError("pyproject.toml must not duplicate the authoritative version")
    configured = pyproject["tool"]["hatch"]["version"]["path"]
    if configured != "src/prehnite/_version.py":
        raise ValueError("Hatch must use the canonical version module")
    version = source_version()

    import prehnite

    if prehnite.__version__ != version:
        raise ValueError("Runtime package version differs from canonical version")
    distribution = importlib.metadata.version("prehnite")
    if distribution != version:
        raise ValueError(f"Installed package metadata {distribution!r} != {version!r}")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if "## [Unreleased]" not in changelog:
        raise ValueError("Changelog requires an Unreleased section")
    for doc in ("docs/AGILE.md", "docs/SPRINT.md", "docs/VERSIONING.md",
                "docs/RELEASING.md", ".github/PULL_REQUEST_TEMPLATE.md"):
        if not (ROOT / doc).is_file():
            raise ValueError(f"Missing governance document: {doc}")
    return version


if __name__ == "__main__":
    try:
        version = check()
    except (KeyError, ValueError, OSError) as error:
        print(f"Governance check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Governance OK: canonical/installed/runtime version {version}")
