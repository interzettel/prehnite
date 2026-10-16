"""Crash-injection contract for paid request recovery.

All remote activity here is a local fake. The worker dies with os._exit()
after SQLite commits, so Python cleanup/finally blocks cannot hide faults.
No fal or Anthropic key, import, HTTP, money, or live provider is involved.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from prehnite.engine import Engine
from prehnite.providers import Result
from prehnite.schema import Endpoint, Manifest, Profile

BATCH = "crash-matrix"

# Keep this script short and self-contained: it is executed in a fresh Python
# interpreter rather than in a pytest child sharing parent module state.
WORKER = r"""
import os
import sys
import time
from pathlib import Path
from PIL import Image
from prehnite.engine import Engine
from prehnite.schema import Endpoint, Manifest, Profile
from prehnite.providers import Result

workspace = Path(sys.argv[1])
phase = sys.argv[2]
manifest = Manifest.model_validate({
    "id": "crash-matrix",
    "assets": [{"id":"one", "prompt":"fixture", "target_size":[192,256],
                "aspect_ratio":"3:4", "output":{"image":"one.png"}}]})
profile = Profile.model_validate({
    "variants": ["native_4k"],
    "generation": {"provider":"demo", "model":"synthetic"},
    "upscale": {"provider":"disabled"},
    "policy":{"uncertain":"accept_unverified"},
    "costs": {"allow_paid":True, "allow_cloud_uploads":True,
              "max_usd":0.05, "estimates_usd":{"generation:2k":0.025}},
})
engine = Engine(manifest, profile, workspace)
output = engine.journal.root / "fake.png"
if phase == "abandoned_lock":
    with engine.journal.exclusive():
        (workspace / "lock-ready").write_text("locked")
        os._exit(74)
if phase == "live_lock":
    with engine.journal.exclusive():
        (workspace / "lock-ready").write_text("locked")
        while True:
            time.sleep(0.1)

def invoke(on_submit, resume_id):
    assert resume_id is None
    if phase == "before_dispatch":
        os._exit(70)
    # Filesystem witness substitutes for a real remote billing ledger.
    with (workspace / "remote-submissions").open("a") as f:
        f.write("submit\n")
    if phase == "after_dispatch_before_id":
        os._exit(71)
    on_submit("fake-remote-request-id")
    if phase == "after_id_commit":
        os._exit(72)
    Image.new("RGB", (192,256), "blue").save(output)
    if phase == "after_result_before_completion":
        os._exit(73)
    return Result(output, "fake-remote-request-id")

engine.stage("one:generate", "generation",
             Endpoint(provider="fal", model="synthetic-remote"),
             output, invoke, "generation:2k")
raise AssertionError("Worker must exit at an injected fault")
"""


def job():
    manifest = Manifest.model_validate({
        "id": BATCH,
        "assets": [{"id": "one", "prompt": "fixture",
                    "aspect_ratio": "3:4", "target_size": [192, 256],
                    "output": {"image": "one.png"}}],
    })
    profile = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "policy": {"uncertain": "accept_unverified"},
        "costs": {"allow_paid": True, "allow_cloud_uploads": True,
                  "max_usd": 0.05, "estimates_usd": {"generation:2k": 0.025}},
    })
    return manifest, profile


def start_worker(workspace: Path, phase: str, *, asynchronous: bool = False):
    proc = subprocess.Popen(
        [sys.executable, "-c", WORKER, str(workspace), phase],
        cwd=str(Path(__file__).resolve().parents[1]),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if asynchronous:
        return proc
    try:
        stdout, stderr = proc.communicate(timeout=18)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        pytest.fail(f"Worker hung at {phase}")
    assert not stdout, stdout.decode("utf-8", errors="replace")
    assert not stderr, stderr.decode("utf-8", errors="replace")
    return proc.returncode


@pytest.mark.parametrize(
    ("phase", "exitcode", "status", "request_id", "submits"),
    [
        ("before_dispatch", 70, "submitting", None, 0),
        ("after_dispatch_before_id", 71, "submitting", None, 1),
        ("after_id_commit", 72, "submitted", "fake-remote-request-id", 1),
        ("after_result_before_completion", 73, "submitted", "fake-remote-request-id", 1),
    ],
)
def test_process_crash_points_are_durable_and_do_not_rebill(
    tmp_path, phase, exitcode, status, request_id, submits
):
    assert start_worker(tmp_path, phase) == exitcode
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        record = engine.journal.get("one:generate")
        assert record["status"] == status
        assert record["request_id"] == request_id
        assert engine.journal.reserved() == pytest.approx(0.025)
        witness = tmp_path / "remote-submissions"
        assert (len(witness.read_text().splitlines()) if witness.exists() else 0) == submits

        observed = []
        output = engine.journal.root / "fake.png"
        def recover(on_submit, resume_id):
            observed.append(resume_id)
            # The only safe action after saving a remote ID is lookup of
            # the existing request. A new submit is forbidden.
            assert resume_id == "fake-remote-request-id"
            from PIL import Image
            Image.new("RGB", (192, 256), "blue").save(output)
            return Result(output, resume_id, {"recovered": True})

        if request_id is None:
            with pytest.raises(RuntimeError, match="no recoverable provider ID"):
                engine.stage("one:generate", "generation",
                             Endpoint(provider="fal", model="synthetic-remote"),
                             output, recover, "generation:2k")
            assert not observed
        else:
            engine.stage("one:generate", "generation",
                         Endpoint(provider="fal", model="synthetic-remote"),
                         output, recover, "generation:2k")
            assert observed == ["fake-remote-request-id"]
            assert engine.journal.get("one:generate")["status"] == "completed"
            # A completed stage is reused locally; not even a get() is made.
            engine.stage("one:generate", "generation",
                         Endpoint(provider="fal", model="synthetic-remote"),
                         output, recover, "generation:2k")
            assert len(observed) == 1

        assert engine.journal.reserved() == pytest.approx(0.025)
        assert (len(witness.read_text().splitlines()) if witness.exists() else 0) == submits
    finally:
        engine.journal.close()


def test_lock_is_released_even_after_ungraceful_process_exit(tmp_path):
    assert start_worker(tmp_path, "abandoned_lock") == 74
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        with engine.journal.exclusive():
            assert (tmp_path / "lock-ready").read_text() == "locked"
    finally:
        engine.journal.close()


def test_another_process_cannot_use_the_same_batch_during_active_lock(tmp_path):
    child = start_worker(tmp_path, "live_lock", asynchronous=True)
    marker = tmp_path / "lock-ready"
    deadline = time.monotonic() + 12
    try:
        while not marker.exists() and time.monotonic() < deadline:
            if child.poll() is not None:
                pytest.fail(f"Lock worker died early: {child.stderr.read()!r}")
            time.sleep(0.025)
        assert marker.exists(), "Lock worker never acquired its lock"
        manifest, profile = job()
        engine = Engine(manifest, profile, tmp_path)
        try:
            with pytest.raises(RuntimeError, match="already has a running worker"):
                with engine.journal.exclusive():
                    pytest.fail("Two workers obtained the same exclusive batch lock")
        finally:
            engine.journal.close()
    finally:
        child.kill()
        child.communicate(timeout=8)

    # A killed process releases the kernel lock even if the lock file remains.
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        with engine.journal.exclusive():
            pass
    finally:
        engine.journal.close()
