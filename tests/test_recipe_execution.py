"""Recipe-to-engine boundaries: synthetic local files only, no GPU, APIs or weights."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from prehnite.engine import Engine
from prehnite.recipe_execution import MicroExecution
from prehnite.recipes import load_recipe, recipe_sha256
from prehnite.schema import Manifest, Profile
from prehnite.store import Journal


ROOT = Path(__file__).resolve().parents[1]


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def config(tmp_path, monkeypatch):
    workflows = tmp_path / "graphs"
    weights = tmp_path / "models"
    workflows.mkdir()
    weights.mkdir()
    checkpoint = b"synthetic hash fixture; not an actual model"
    (weights / "synthetic.safetensors").write_bytes(checkpoint)
    graph = json.dumps({
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": "synthetic.safetensors"}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "object"}},
    })
    for filename in ("generate.json", "cutout.json"):
        (workflows / filename).write_text(graph, encoding="utf-8")
    recipe_file = ROOT / "recipes/prehnite-micro/0.1.0-preview.1.json"
    digest = recipe_sha256(load_recipe(recipe_file))
    stages = {}
    for stage_id, filename in (("generate", "generate.json"),
                               ("cutout", "cutout.json")):
        stages[stage_id] = {
            "workflow": filename,
            "workflow_sha256": hash_bytes(graph.encode()),
            "checkpoint": "synthetic.safetensors",
            "checkpoint_sha256": hash_bytes(checkpoint),
            "model_revision": "synthetic-fixture-v1",
            "model_terms_url": "https://example.org/test-fixture-terms",
            "acknowledged_terms_for_local_use": True,
        }
    binding_file = tmp_path / "bindings.json"
    binding_file.write_text(json.dumps({
        "schema_version": 1, "recipe_sha256": digest, "stages": stages,
    }), encoding="utf-8")
    monkeypatch.setenv("PREHNITE_WORKFLOWS", str(workflows))
    profile = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "comfyui", "model": "user-workflow",
                       "options": {"workflow": "generate.json",
                                   "prompt_node": "2", "seed_node": "1",
                                   "size_node": "1", "output_node": "2"}},
        "segmentation": {"provider": "comfyui", "model": "user-segmentation",
                         "options": {"workflow": "cutout.json",
                                     "input_node": "1", "target_node": "3",
                                     "output_node": "2"}},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "reject"},
        "costs": {"allow_paid": False, "allow_cloud_uploads": False,
                  "max_usd": 0},
    })
    manifest = Manifest.model_validate({
        "id": "micro-fixture",
        "assets": [{"id": "one", "prompt": "fixture",
                    "targets": ["subject"],
                    "output": {"image": "one.png",
                               "cutouts": {"subject": "subject.png"}}}],
    })
    execution = MicroExecution(recipe_file, binding_file, workflows, weights)
    return manifest, profile, execution, workflows, weights


def test_preflight_verifies_stage_profile_and_source_id(config):
    _, profile, execution, _, _ = config
    evidence = execution.verify(profile)
    assert evidence["recipe_id"] == "prehnite-micro"
    assert evidence["profile_connection"] == "local_comfyui_only"
    assert evidence["runtime_verified"] is False
    assert evidence["hardware_verified"] is False
    assert evidence["automatic_spending_enabled"] is False


def test_engine_journal_is_pinned_before_first_stage_and_idempotent(config, tmp_path):
    manifest, profile, execution, _, _ = config
    engine = Engine(manifest, profile, tmp_path, recipe_execution=execution)
    receipt = engine.journal.fact("recipe_run_identity")
    assert receipt["recipe_id"] == "prehnite-micro"
    assert receipt["configuration_sha256"]
    assert receipt["resolved_inputs_sha256"]
    assert engine.journal.tasks() == []
    engine.journal.close()
    resumed = Engine(manifest, profile, tmp_path, recipe_execution=execution)
    assert resumed.journal.fact("recipe_run_identity") == receipt
    resumed.journal.close()


def test_recipe_batch_refuses_unbound_resume(config, tmp_path):
    manifest, profile, execution, _, _ = config
    engine = Engine(manifest, profile, tmp_path, recipe_execution=execution)
    engine.journal.close()
    with pytest.raises(ValueError, match="unbound resume"):
        Engine(manifest, profile, tmp_path)


def test_existing_legacy_batch_refuses_retroactive_recipe_identity(config, tmp_path):
    manifest, profile, execution, _, _ = config
    legacy = Engine(manifest, profile, tmp_path)
    legacy.journal.close()
    with pytest.raises(ValueError, match="existing legacy batch"):
        Engine(manifest, profile, tmp_path, recipe_execution=execution)
    j = Journal(tmp_path, manifest.id)
    assert j.fact("recipe_run_identity") is None
    j.close()


def test_changed_checkpoint_bytes_block_resume_before_provider_invocation(config, tmp_path):
    manifest, profile, execution, _, weights = config
    engine = Engine(manifest, profile, tmp_path, recipe_execution=execution)
    engine.journal.close()
    (weights / "synthetic.safetensors").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Checkpoint SHA256 mismatch"):
        Engine(manifest, profile, tmp_path, recipe_execution=execution)
    j = Journal(tmp_path, manifest.id)
    assert not j.tasks()
    j.close()


def test_changed_profile_rejected_without_tampering_stored_identity(config, tmp_path):
    manifest, profile, execution, _, _ = config
    engine = Engine(manifest, profile, tmp_path, recipe_execution=execution)
    initial = engine.journal.fact("recipe_run_identity")
    engine.journal.close()
    other = profile.model_copy(deep=True)
    other.policy.maximum_attempts = 5
    with pytest.raises(ValueError, match="identity mismatch"):
        Engine(manifest, other, tmp_path, recipe_execution=execution)
    j = Journal(tmp_path, manifest.id)
    assert j.fact("recipe_run_identity") == initial
    j.close()


def test_active_workflow_directory_must_be_verified(config, tmp_path, monkeypatch):
    _, profile, execution, _, _ = config
    monkeypatch.setenv("PREHNITE_WORKFLOWS", str(tmp_path))
    with pytest.raises(ValueError, match="PREHNITE_WORKFLOWS"):
        execution.verify(profile)


def test_unreferenced_checkpoint_not_authorized(config):
    _, profile, execution, workflows, _ = config
    altered = json.dumps({"1": {"class_type": "CheckpointLoaderSimple",
                                "inputs": {"ckpt_name": "not-matching.safetensors"}}})
    (workflows / "cutout.json").write_text(altered, encoding="utf-8")
    # The binding digest catches the altered bytes first.
    with pytest.raises(ValueError, match="Workflow SHA256 mismatch"):
        execution.verify(profile)


@pytest.mark.parametrize("mutation", [
    lambda p: setattr(p.costs, "allow_paid", True),
    lambda p: setattr(p.costs, "allow_cloud_uploads", True),
    lambda p: setattr(p.cache, "enabled", True),
    lambda p: setattr(p, "variants", ["enhanced_2k"]),
    lambda p: setattr(p.generation, "model", "other-workflow"),
    lambda p: p.generation.options.update(workflow="other.json"),
    lambda p: p.segmentation.options.pop("output_node"),
])
def test_mismatched_or_paid_profile_is_refused(config, mutation):
    _, profile, execution, _, _ = config
    other = profile.model_copy(deep=True)
    mutation(other)
    with pytest.raises((ValueError, AttributeError)):
        execution.verify(other)


def test_engine_rechecks_recipe_before_run_after_initialization(config, tmp_path):
    manifest, profile, execution, _, weights = config
    engine = Engine(manifest, profile, tmp_path, recipe_execution=execution)
    (weights / "synthetic.safetensors").write_bytes(b"modified-after-initialization")
    with pytest.raises(ValueError, match="Checkpoint SHA256 mismatch"):
        engine.run()
    assert engine.journal.tasks() == []
    engine.journal.close()


def test_mcp_route_refuses_recipe_bound_execution(config, tmp_path):
    manifest, profile, execution, _, _ = config
    with pytest.raises(ValueError, match="MCP execution is not implemented"):
        Engine(manifest, profile, tmp_path, job_token="fake", recipe_execution=execution)


def test_recipe_verifies_explicit_target_field_without_reupload(config):
    _, profile, execution, _, _ = config
    baseline = execution.verify(profile)
    assert baseline["runtime_verified"] is False
    bad = profile.model_copy(deep=True)
    bad.segmentation.options["target_input"] = "prompt"
    with pytest.raises(ValueError, match="no configured 'prompt' input"):
        execution.verify(bad)
    wrong_node = profile.model_copy(deep=True)
    wrong_node.segmentation.options["target_node"] = "999"
    with pytest.raises(ValueError, match="real graph node"):
        execution.verify(wrong_node)
    invalid = profile.model_copy(deep=True)
    invalid.segmentation.options["target_input"] = "filename_prefix"
    with pytest.raises(ValueError, match="target_input must be"):
        execution.verify(invalid)
