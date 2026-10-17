"""Release publishing privileges must never leak back into ordinary CI."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def load(name):
    return yaml.load((ROOT / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_ci_still_builds_distribution_but_cannot_publish():
    ci = load("ci.yml")
    assert "push" in ci["on"] and "pull_request" in ci["on"]
    assert "release-dist-audit" in ci["jobs"]
    assert "publish-pypi" not in ci["jobs"]
    assert "release-verify" not in ci["jobs"]
    text = (ROOT / "ci.yml").read_text(encoding="utf-8")
    assert "id-token: write" not in text
    assert "gh-action-pypi-publish" not in text


def test_publish_is_only_manual_on_main_after_successful_ci_and_review():
    release = load("publish.yml")
    assert set(release["on"]) == {"workflow_dispatch"}
    assert set(release["jobs"]) == {"verify", "publish"}
    verify = release["jobs"]["verify"]
    publish = release["jobs"]["publish"]
    assert verify["permissions"]["contents"] == "read"
    assert verify["permissions"]["actions"] == "read"
    assert "id-token" not in verify["permissions"]
    assert publish["permissions"]["id-token"] == "write"
    assert publish["environment"]["name"] == "pypi"
    assert "verify" in publish["needs"]
    for job in (verify, publish):
        assert "refs/heads/main" in job["if"]
        assert "workflow_dispatch" in job["if"]
    steps = verify["steps"] + publish["steps"]
    shell_steps = "\n".join(str(s.get("run", "")) for s in steps)
    assert "PUBLISH PREHNITE TO PYPI" in shell_steps
    assert "0.1.0a1" in shell_steps
    assert "release_ci_gate.py" in shell_steps
    assert "check_release_artifacts.py" in shell_steps
    action_steps = [s.get("uses", "") for s in steps]
    assert any(s.startswith("pypa/gh-action-pypi-publish@") for s in action_steps)
    assert not any(s.endswith("@release/v1") for s in action_steps)
    assert "gh release create" in shell_steps
