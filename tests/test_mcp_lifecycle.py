"""Offline lifecycle regressions for #38: no MCP extras, APIs or credentials."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml
from PIL import Image

from prehnite.engine import Engine
from prehnite.manifest import load_manifest, load_profile
from prehnite.mcp_jobs import JobManager
from prehnite.providers import Result
from prehnite.store import JobStopped, Journal


def setup(home: Path, *, assets: int = 2) -> JobManager:
    manager = JobManager(home)
    manifest = {
        "id": "mcp-fixture",
        "assets": [
            {"id": f"item-{i}", "prompt": "synthetic test", "aspect_ratio": "3:4",
             "target_size": [192, 256], "output": {"image": f"photo-{i}.png"}}
            for i in range(assets)
        ],
    }
    profile = {
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
    }
    (manager.requests / "fixture.yaml").write_text(yaml.safe_dump(manifest), encoding="utf8")
    (manager.profiles / "demo.yaml").write_text(yaml.safe_dump(profile), encoding="utf8")
    return manager


def fake_launch(monkeypatch):
    calls = []
    class FakeProcess:
        def __init__(self, command, **kwargs):
            calls.append(command)
            assert kwargs["stdin"] == subprocess.DEVNULL
            assert kwargs["stderr"] == subprocess.STDOUT
            assert "shell" not in kwargs
    monkeypatch.setattr("prehnite.mcp_jobs.subprocess.Popen", FakeProcess)
    return calls


def token(manager: JobManager) -> str:
    j = Journal(manager.workspace, "mcp-fixture")
    try:
        return j.job_record()["token"]
    finally:
        j.close()


def simulate_worker(manager: JobManager, token_value: str):
    manifest = load_manifest(manager.requests / "fixture.yaml")
    profile = load_profile(manager.profiles / "demo.yaml")
    return Engine(manifest, profile, manager.workspace, manager.inputs, job_token=token_value)


def test_duplicate_submission_and_reconnect_do_not_rely_on_pid(monkeypatch, tmp_path):
    manager = setup(tmp_path)
    calls = fake_launch(monkeypatch)
    started = manager.submit("fixture.yaml", "demo.yaml")
    assert started == {"job_id": "mcp-fixture", "status": "launching"}
    assert manager.submit("fixture.yaml", "demo.yaml")["status"] == "already_starting"
    (manager.workspace / "prehnite-mcp-fixture.pid").write_text(str(os.getpid()))
    monkeypatch.setattr(os, "kill", lambda *args: pytest.fail("PID probe forbidden"))
    reconnected = JobManager(tmp_path)
    assert reconnected.status("mcp-fixture")["status"] == "launching"
    assert len(calls) == 1
    assert calls[0][-2] == "--job-token"
    assert reconnected.status("mcp-fixture")["required_assets"] == 2  # persisted at launch


def test_pause_before_start_then_explicit_resume(monkeypatch, tmp_path):
    manager = setup(tmp_path)
    calls = fake_launch(monkeypatch)
    manager.submit("fixture.yaml", "demo.yaml")
    first_token = token(manager)
    pause_reply = manager.control("mcp-fixture", "pause")
    assert pause_reply["status"] == "pause_requested"
    assert pause_reply["accepted"] is True
    assert pause_reply["already_requested"] is False
    assert manager.control("mcp-fixture", "pause")["already_requested"] is True
    engine = simulate_worker(manager, first_token)
    try:
        assert engine.run()["job_status"] == "paused"
    finally:
        engine.journal.close()
    status = JobManager(tmp_path).status("mcp-fixture")
    assert status["status"] == "paused"
    assert status["accepted_assets"] == 0
    assert manager.submit("fixture.yaml", "demo.yaml")["status"] == "paused"
    assert manager.resume("mcp-fixture")["status"] == "launching"
    second_token = token(manager)
    assert second_token != first_token
    with pytest.raises(ValueError, match="launch identity"):
        simulate_worker(manager, first_token)
    live = simulate_worker(manager, second_token)
    try:
        assert len(live.run()["asset_results"]) == 2
    finally:
        live.journal.close()
    assert manager.status("mcp-fixture")["status"] == "completed"
    assert manager.status("mcp-fixture")["accepted_assets"] == 2
    assert len(calls) == 2


def test_pause_during_stage_keeps_completed_stage_for_resume(monkeypatch, tmp_path):
    manager = setup(tmp_path)
    fake_launch(monkeypatch)
    manager.submit("fixture.yaml", "demo.yaml")
    first = token(manager)
    seen = []
    class Demo:
        def generate(self, prompt, ratio, tier, seed, destination, endpoint,
                     on_submit, resume):
            seen.append(seed)
            Image.new("RGB", (192, 256), "orange").save(destination)
            if len(seen) == 1:
                assert manager.control("mcp-fixture", "pause")["status"] == "pause_requested"
            return Result(destination)
    monkeypatch.setattr("prehnite.engine.get_provider", lambda ep: Demo())
    engine = simulate_worker(manager, first)
    try:
        assert engine.run()["job_status"] == "paused"
        assert engine.journal.get("item-0:a1:native_4k:generate")["status"] == "completed"
    finally:
        engine.journal.close()
    assert manager.status("mcp-fixture")["status"] == "paused"
    manager.resume("mcp-fixture")
    engine2 = simulate_worker(manager, token(manager))
    try:
        report = engine2.run()
        assert len(report["asset_results"]) == 2
    finally:
        engine2.journal.close()
    assert len(seen) == 2  # already completed provider stage not repeated
    assert manager.status("mcp-fixture")["accepted_assets"] == 2


def test_cancel_during_stage_does_not_kill_provider_or_continue(monkeypatch, tmp_path):
    manager = setup(tmp_path)
    fake_launch(monkeypatch)
    manager.submit("fixture.yaml", "demo.yaml")
    seen = []
    class Demo:
        def generate(self, prompt, ratio, tier, seed, destination, endpoint,
                     on_submit, resume):
            seen.append(seed)
            first = manager.control("mcp-fixture", "cancel")
            second = manager.control("mcp-fixture", "cancel")
            assert first["accepted"] and first["status"] == "cancel_requested"
            assert not first["already_requested"]
            assert second["accepted"] and second["already_requested"]
            with pytest.raises(RuntimeError, match="Worker active"):
                manager.export("mcp-fixture")
            Image.new("RGB", (192, 256), "red").save(destination)
            return Result(destination)
    monkeypatch.setattr("prehnite.engine.get_provider", lambda ep: Demo())
    engine = simulate_worker(manager, token(manager))
    try:
        assert engine.run()["job_status"] == "cancelled"
    finally:
        engine.journal.close()
    assert len(seen) == 1
    assert manager.control("mcp-fixture", "cancel")["status"] == "cancelled"
    assert manager.resume("mcp-fixture")["resume_allowed"] is False
    assert manager.status("mcp-fixture")["status"] == "cancelled"
    assert manager.export("mcp-fixture")["archive"].endswith(".zip")


def test_launch_token_change_does_not_let_stale_worker_overwrite(monkeypatch, tmp_path):
    manager = setup(tmp_path)
    fake_launch(monkeypatch)
    manager.submit("fixture.yaml", "demo.yaml")
    old_token = token(manager)
    journal = Journal(manager.workspace, "mcp-fixture")
    try:
        journal.db.execute("UPDATE job_control SET launched_at=0 WHERE singleton=1")
        journal.db.commit()
    finally:
        journal.close()
    assert manager.status("mcp-fixture")["status"] == "interrupted"
    assert manager.resume("mcp-fixture")["status"] == "launching"
    with pytest.raises(ValueError, match="launch identity"):
        simulate_worker(manager, old_token)
    assert manager.status("mcp-fixture")["status"] == "launching"


def test_atomic_launch_under_multiple_concurrent_clients(monkeypatch, tmp_path):
    manager = setup(tmp_path)
    calls = fake_launch(monkeypatch)
    def submit(_):
        return JobManager(tmp_path).submit("fixture.yaml", "demo.yaml")["status"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(submit, range(8)))
    assert statuses.count("launching") == 1
    assert statuses.count("already_starting") == 7
    assert len(calls) == 1


def test_input_validation_and_no_arbitrary_path_or_shell(monkeypatch, tmp_path):
    manager = setup(tmp_path)
    fake_launch(monkeypatch)
    for bad in ("../fixture.yaml", "/etc/passwd", ".hidden", "a\\b", ""):
        with pytest.raises(ValueError):
            manager.submit(bad, "demo.yaml")
    try:
        (manager.requests / "outside.yaml").symlink_to(tmp_path / "elsewhere")
    except (OSError, NotImplementedError):
        # Non-elevated Windows accounts may not be allowed to create symlinks.
        pass
    else:
        with pytest.raises(ValueError):
            manager.submit("outside.yaml", "demo.yaml")
    with pytest.raises(ValueError):
        manager.status("../mcp-fixture")


def test_real_detached_cli_worker_survives_manager_reconnect(tmp_path):
    manager = setup(tmp_path, assets=1)
    assert manager.submit("fixture.yaml", "demo.yaml")["status"] == "launching"
    del manager
    new_client = JobManager(tmp_path)
    deadline = time.monotonic() + 25
    state = ""
    while time.monotonic() < deadline:
        state = new_client.status("mcp-fixture")["status"]
        if state in ("completed", "failed", "interrupted", "cancelled"):
            break
        time.sleep(0.05)
    assert state == "completed", (state, (new_client.workspace /
        "batches/mcp-fixture/worker.log").read_text(errors="replace"))
    assert new_client.status("mcp-fixture")["accepted_assets"] == 1
    assert Path(new_client.export("mcp-fixture")["archive"]).is_file()


def test_mutated_staged_configuration_is_rejected_before_worker_writes(monkeypatch, tmp_path):
    manager = setup(tmp_path)
    fake_launch(monkeypatch)
    manager.submit("fixture.yaml", "demo.yaml")
    launched_token = token(manager)
    changed = yaml.safe_load((manager.profiles / "demo.yaml").read_text())
    changed["policy"]["maximum_attempts"] = 3
    (manager.profiles / "demo.yaml").write_text(yaml.safe_dump(changed), encoding="utf8")
    with pytest.raises(ValueError, match="configuration changed since preflight"):
        simulate_worker(manager, launched_token)
    j = Journal(manager.workspace, "mcp-fixture")
    try:
        assert j.fact("configuration_sha256") is None
        assert j.fact("manifest") is None
        assert j.job_record()["status"] == "launching"
    finally:
        j.close()


def test_active_subprocess_survives_client_reconnect_and_honors_cancel(monkeypatch, tmp_path):
    real_popen = subprocess.Popen
    manager = setup(tmp_path, assets=1)
    fake_launch(monkeypatch)
    manager.submit("fixture.yaml", "demo.yaml")
    launch_token = token(manager)
    ready = tmp_path / "worker-ready"
    # Genuine independent process and genuine run.lock, no model/provider call.
    script = """
import sys, time
from pathlib import Path
from prehnite.store import Journal, JobStopped
workspace, token, ready = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
journal = Journal(workspace, "mcp-fixture")
try:
    with journal.exclusive():
        journal.job_start(token)
        ready.write_text("ready")
        while True:
            try:
                journal.job_checkpoint(token)
            except JobStopped as stopped:
                journal.job_finish(token, stopped.status)
                break
            time.sleep(0.025)
finally:
    journal.close()
"""
    process = real_popen(
        [sys.executable, "-c", script, str(manager.workspace), launch_token, str(ready)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 12
        while not ready.is_file() and time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(f"Worker exited early: {process.stderr.read()!r}")
            time.sleep(0.03)
        assert ready.is_file(), "Independent worker never acquired its run lock"
        reconnected = JobManager(tmp_path)
        assert reconnected.status("mcp-fixture")["worker_active"]
        assert reconnected.status("mcp-fixture")["status"] == "running"
        assert reconnected.submit("fixture.yaml", "demo.yaml")["status"] == "already_running"
        assert reconnected.control("mcp-fixture", "cancel")["status"] == "cancel_requested"
        stdout, stderr = process.communicate(timeout=12)
        assert process.returncode == 0, (stdout, stderr)
        assert reconnected.status("mcp-fixture")["status"] == "cancelled"
        assert not reconnected.status("mcp-fixture")["worker_active"]
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
