"""Read-only local ComfyUI mapping: no execution or graph value disclosure."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from prehnite.cli import app
from prehnite.pilot_inspect import inspect_generation_pilot

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/manifest-8g-sdxl-pilot.yaml"
PROFILE = ROOT / "examples/profile-8g-sdxl-pilot.yaml"


@pytest.fixture
def work(tmp_path):
    graphs = tmp_path / "private-workflows"
    graphs.mkdir()
    private_secret = "PRIVATE_PROMPT_DO_NOT_EXPOSE"
    original = {
        "3": {"class_type": "KSampler", "inputs": {"seed": 888, "steps": 20}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": 256, "height": 512, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": private_secret}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["3", 0], "filename_prefix": "PRIVATE_FILE"}},
        "10": {"class_type": "CheckpointLoaderSimple",
               "inputs": {"ckpt_name": "PRIVATE_MODEL.safetensors"}},
    }
    (graphs / "generation_api.json").write_text(json.dumps(original), encoding="utf-8")
    return graphs, original


def test_explicit_existing_graph_mappings_are_reported_not_executed(work, monkeypatch):
    graphs, original = work

    def forbid_network(*args, **kwargs):
        raise AssertionError("inspector must never initialize http client")

    monkeypatch.setattr("httpx.Client", forbid_network)
    result = inspect_generation_pilot(MANIFEST, PROFILE, graphs)
    assert result["status"] == "static_mapping_valid"
    assert result["asset_count"] == 10
    assert result["mapped_node_ids"] == {
        "prompt_node": "6", "seed_node": "3",
        "size_node": "5", "output_node": "9",
    }
    assert result["candidate_node_ids"]["output_node"] == [
        {"id": "9", "class_type": "SaveImage"}
    ]
    assert result["workflow_sha256"] and len(result["workflow_sha256"]) == 64
    assert result["gpu_operations"] == result["provider_calls"] == 0
    assert result["execution_ready"] is False
    assert result["model_rights_checked"] is False
    assert "PRIVATE_PROMPT_DO_NOT_EXPOSE" not in json.dumps(result)
    assert "PRIVATE_FILE" not in json.dumps(result)
    assert "PRIVATE_MODEL" not in json.dumps(result)
    assert original["6"]["inputs"]["text"] == "PRIVATE_PROMPT_DO_NOT_EXPOSE"


def test_cli_prints_json_and_maintains_honest_exit_status(work):
    graphs, _ = work
    runner = CliRunner()
    args = ["pilot-inspect", str(MANIFEST), "--profile", str(PROFILE),
            "--workflows", str(graphs)]
    completed = runner.invoke(app, args)
    assert completed.exit_code == 0, completed.output
    assert json.loads(completed.output)["status"] == "static_mapping_valid"
    assert "make the images" not in completed.output


def test_wrong_node_mapping_fails_with_candidates_and_no_execution(work, tmp_path):
    graphs, _ = work
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    profile["generation"]["options"]["size_node"] = "3"
    modified = tmp_path / "wrong-profile.yaml"
    modified.write_text(yaml.safe_dump(profile), encoding="utf-8")
    result = inspect_generation_pilot(MANIFEST, modified, graphs)
    assert result["status"] == "blocked"
    assert result["candidate_node_ids"]["size_node"][0]["id"] == "5"
    assert "size_node: mapped node lacks required inputs" in result["errors"]
    args = ["pilot-inspect", str(MANIFEST), "--profile", str(modified),
            "--workflows", str(graphs)]
    command = CliRunner().invoke(app, args)
    assert command.exit_code == 1
    assert json.loads(command.output)["execution_ready"] is False


def test_wrong_output_node_and_ambiguous_prompt_nodes_are_honestly_reported(work, tmp_path):
    graphs, original = work
    original["11"] = {"class_type": "CLIPTextEncode",
                      "inputs": {"text": "hidden second prompt"}}
    (graphs / "generation_api.json").write_text(json.dumps(original), encoding="utf-8")
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    profile["generation"]["options"]["output_node"] = "6"
    modified = tmp_path / "bad-output.yaml"
    modified.write_text(yaml.safe_dump(profile), encoding="utf-8")
    result = inspect_generation_pilot(MANIFEST, modified, graphs)
    assert result["status"] == "blocked"
    assert len(result["candidate_node_ids"]["prompt_node"]) == 2
    assert "output_node: mapped node is not a SaveImage node" in result["errors"]
    assert "hidden second prompt" not in json.dumps(result)


@pytest.mark.parametrize("bad_name", ["../steal.json", "/tmp/steal.json",
                                      ".private.json", "subfolder/file.json"])
def test_rejects_unsafe_workflow_names(work, tmp_path, bad_name):
    graphs, _ = work
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    profile["generation"]["options"]["workflow"] = bad_name
    modified = tmp_path / "unsafe.yaml"
    modified.write_text(yaml.safe_dump(profile), encoding="utf-8")
    with pytest.raises(ValueError):
        inspect_generation_pilot(MANIFEST, modified, graphs)


def test_refuses_non_api_and_oversize_graphs(work):
    graphs, _ = work
    path = graphs / "generation_api.json"
    path.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="API node shape"):
        inspect_generation_pilot(MANIFEST, PROFILE, graphs)
    path.write_bytes(b" " * (2 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="exceeds 2 MiB"):
        inspect_generation_pilot(MANIFEST, PROFILE, graphs)


def test_no_api_or_paid_provider_can_be_mistaken_for_local_pilot(work, tmp_path):
    graphs, _ = work
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    profile["costs"]["allow_paid"] = True
    modified = tmp_path / "billable.yaml"
    modified.write_text(yaml.safe_dump(profile), encoding="utf-8")
    with pytest.raises(ValueError, match="single-attempt, local-only profile"):
        inspect_generation_pilot(MANIFEST, modified, graphs)
