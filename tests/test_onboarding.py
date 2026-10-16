"""Clean first-run and local health diagnostics without provider requests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from prehnite.cli import app
from prehnite.manifest import load_manifest, load_profile, validate_job
from prehnite.onboarding import doctor_report, init_example

runner = CliRunner()


def test_init_creates_valid_free_manifest_and_profile(tmp_path):
    workspace = tmp_path / "new workspace"
    result = runner.invoke(app, ["init", "--destination", str(workspace),
                                 "--batch-id", "hello-world"])
    assert result.exit_code == 0, result.output
    manifest = load_manifest(workspace/"manifest.yaml")
    profile = load_profile(workspace/"profile.yaml")
    validate_job(manifest, profile, tmp_path)
    assert manifest.id == "hello-world"
    assert profile.generation.provider == "demo"
    assert profile.costs.allow_paid is False
    assert profile.costs.max_usd == 0
    assert not profile.costs.allow_cloud_uploads
    assert len(manifest.assets) == 1
    assert 'prehnite run "' in result.output


def test_generated_project_runs_entirely_offline(tmp_path):
    from prehnite.engine import Engine
    output = tmp_path/"starter"
    mfile, pfile = init_example(output)
    engine = Engine(load_manifest(mfile), load_profile(pfile), tmp_path/"state")
    try:
        result = engine.run()
        assert result["asset_results"]["example-001"]["status"] == "accepted"
        assert result["cost_estimated_or_reserved_usd"] == 0
    finally:
        engine.journal.close()


def test_init_never_overwrites_existing_files(tmp_path):
    directory = tmp_path/"existing"
    directory.mkdir()
    existing = directory/"profile.yaml"
    existing.write_text("PRIVATE USER PROFILE", encoding="utf-8")
    result = runner.invoke(app, ["init", "--destination", str(directory)])
    assert result.exit_code != 0
    assert existing.read_text() == "PRIVATE USER PROFILE"
    assert not (directory/"manifest.yaml").exists()


def test_init_rerun_is_safe_and_non_destructive(tmp_path):
    output = tmp_path/"new"
    init_example(output)
    old = [(output/name).read_bytes() for name in ("manifest.yaml", "profile.yaml")]
    with pytest.raises(FileExistsError):
        init_example(output)
    assert [(output/name).read_bytes() for name in ("manifest.yaml", "profile.yaml")] == old


def test_invalid_batch_id_refused_without_writes(tmp_path):
    output = tmp_path/"project"
    result = runner.invoke(app, ["init", "--destination", str(output),
                                 "--batch-id", "../secret"])
    assert result.exit_code != 0
    assert not output.exists()


def test_partial_init_write_rolls_back_only_new_files(tmp_path, monkeypatch):
    directory = tmp_path/"rollback"
    original_open = Path.open

    def failing_open(path, mode="r", *args, **kwargs):
        if Path(path).name == "profile.yaml" and mode == "x":
            raise OSError("simulated disk write failure")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)
    with pytest.raises(OSError, match="disk write"):
        init_example(directory)
    assert not (directory/"manifest.yaml").exists()
    assert not (directory/"profile.yaml").exists()


def test_doctor_never_probes_network_by_default(tmp_path, monkeypatch):
    def fail_client(*args, **kwargs):
        pytest.fail("Doctor must never contact local or cloud services by default")
    monkeypatch.setattr("prehnite.onboarding.httpx.Client", fail_client)
    monkeypatch.setenv("FAL_KEY", "DO_NOT_PRINT_THIS_FAKE_SECRET")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "DO_NOT_PRINT_THIS_SECOND_SECRET")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "DO_NOT_PRINT_THIS" not in result.output
    obj = json.loads(result.output)
    assert obj["credentials"]["fal_key_present"] is True
    assert obj["credentials"]["anthropic_key_present"] is True
    assert obj["credentials"]["validation"] == "presence_only_not_authentication"
    assert obj["local_comfyui"]["connection"] == "not_checked"
    assert obj["cloud_inference_performed"] is False
    assert obj["gpu_benchmark_performed"] is False


def test_doctor_can_opt_in_to_localhost_comfyui_only(monkeypatch):
    visited = []

    class LocalResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {"system": {"os": "Linux"}, "devices": []}
    class LocalClient:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
            assert kwargs["timeout"] == 2
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def get(self, url):
            visited.append(url)
            return LocalResponse()

    monkeypatch.setattr("prehnite.onboarding.httpx.Client", LocalClient)
    assert doctor_report()["local_comfyui"]["connection"] == "not_checked"
    assert visited == []
    result = runner.invoke(app, ["doctor", "--check-comfyui",
                                 "--comfyui-url", "http://127.0.0.1:8188"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["local_comfyui"]["connection"] == "reachable"
    assert visited == ["http://127.0.0.1:8188/system_stats"]


@pytest.mark.parametrize("address", [
    "http://evil.example:8188", "https://127.0.0.1:8188",
    "http://localhost.evil.example:8188", "file:///etc/passwd"
])
def test_doctor_rejects_nonlocal_server_even_when_requested(monkeypatch, address):
    monkeypatch.setattr("prehnite.onboarding.httpx.Client",
                        lambda **kwargs: pytest.fail("Untrusted connection"))
    result = runner.invoke(app, ["doctor", "--check-comfyui",
                                 "--comfyui-url", address])
    assert result.exit_code != 0


def test_doctor_marks_malformed_local_response_as_not_healthy(monkeypatch):
    class NotComfy:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, url): return self
        def raise_for_status(self): return None
        def json(self): return {"unexpected": "HTML proxy"}
    monkeypatch.setattr("prehnite.onboarding.httpx.Client", NotComfy)
    result = doctor_report(check_comfyui=True)
    assert result["local_comfyui"]["connection"] == "unexpected_response"
    assert result["local_comfyui"]["model_execution"] == "not_tested"
