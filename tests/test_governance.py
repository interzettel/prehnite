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
    # The test must not assume the live sprint already fills its WIP slots.
    for item in data["cards"]:
        if item["lane"] == "In progress":
            item["lane"] = "Backlog"
    for n in range(data["limits"]["max_in_progress"] + 1):
        extra = dict(data["cards"][0])
        extra["number"] = 99980 + n
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


@pytest.mark.parametrize("version", [
    "0.1.0a2.dev0", "0.1.0a2", "0.1.0b3.dev1", "0.1.0rc1",
    "0.1.0.dev0", "0.1.0",
])
def test_governance_accepts_canonical_pre_release_development(version, monkeypatch, tmp_path):
    governance = load_script("check_governance")
    path = tmp_path / "_version.py"
    path.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    monkeypatch.setattr(governance, "VERSION_PATH", path)
    assert governance.source_version() == version


@pytest.mark.parametrize("version", ["0.1.0a.dev0", "0.1", "0.1.0-foo", "0.1.0a2.dev",
                                      "0.1.0a2+custom", "0.1.0a2.post3"])
def test_governance_rejects_invalid_release_label(version, monkeypatch, tmp_path):
    governance = load_script("check_governance")
    path = tmp_path / "_version.py"
    path.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    monkeypatch.setattr(governance, "VERSION_PATH", path)
    with pytest.raises(ValueError, match="PEP 440"):
        governance.source_version()
