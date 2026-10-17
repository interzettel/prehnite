"""Release CI gate fails closed on wrong SHA, PR checks or partial CI."""
import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location(
    "release_ci_gate", Path(__file__).resolve().parents[1] / "scripts/release_ci_gate.py"
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def run(**overrides):
    item = {
        "id": 4242,
        "name": "CI",
        "head_sha": "a" * 40,
        "head_branch": "main",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
    }
    item.update(overrides)
    return item


def test_only_exact_successful_main_push_accepted():
    assert gate.select_verified_ci_run([run(id=1), run(id=7)], "a" * 40) == 7


@pytest.mark.parametrize("change", [
    {"head_sha": "b" * 40},
    {"head_branch": "feat/release"},
    {"event": "pull_request"},
    {"event": "workflow_dispatch"},
    {"name": "Unrelated"},
    {"status": "in_progress"},
    {"conclusion": "failure"},
    {"conclusion": "skipped"},
])
def test_unsafe_ci_claim_fails(change):
    with pytest.raises(ValueError):
        gate.select_verified_ci_run([run(**change)], "a" * 40)


def test_no_results_fails():
    with pytest.raises(ValueError):
        gate.select_verified_ci_run([], "a" * 40)
