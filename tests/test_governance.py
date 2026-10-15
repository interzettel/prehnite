"""Checks for version drift and Kanban integrity, without GitHub network access."""
import importlib.metadata
import importlib.util
import json
from pathlib import Path

import pytest
import prehnite

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_single_source_version():
    governance = load_script("check_governance")
    assert governance.check() == prehnite.__version__
    assert governance.source_version() == importlib.metadata.version("prehnite")


def test_sprint_snapshot_is_reproducible():
    board_script = load_script("board")
    payload = json.loads((ROOT / "project/board.json").read_text(encoding="utf-8"))
    assert board_script.render(payload) == (ROOT / "docs/SPRINT.md").read_text(encoding="utf-8")


def test_kanban_limit_enforced():
    board_script = load_script("board")
    data = json.loads((ROOT / "project/board.json").read_text(encoding="utf-8"))
    extra = dict(data["cards"][0])
    extra["number"] = 99998
    extra["lane"] = "In progress"
    data["cards"].append(extra)
    with pytest.raises(ValueError, match="WIP limit"):
        board_script.validate_board(data)


def test_kanban_duplicate_detected():
    board_script = load_script("board")
    data = json.loads((ROOT / "project/board.json").read_text(encoding="utf-8"))
    data["cards"].append(dict(data["cards"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        board_script.validate_board(data)
