"""Local micro resolver test-only bytes: no checkpoint distribution or GPU access."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from prehnite.recipe_resolver import (LocalBindings, load_local_bindings,
                                      resolve_local_micro)
from prehnite.recipes import load_recipe, recipe_sha256

ROOT = Path(__file__).resolve().parents[1]
MICRO = ROOT / "recipes/prehnite-micro/0.1.0-preview.1.json"
MACRO = ROOT / "recipes/prehnite-macro/0.1.0-preview.1.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def inputs(tmp_path):
    workflows, weights = tmp_path / "workflows", tmp_path / "models"
    workflows.mkdir()
    weights.mkdir()
    graph = json.dumps({"1": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}}})
    (workflows / "api.json").write_text(graph, encoding="utf-8")
    (weights / "demo.safetensors").write_bytes(b"synthetic-fixture-bytes-no-real-weights")
    recipe = load_recipe(MICRO)
    stage = {
        "workflow": "api.json", "workflow_sha256": sha(graph.encode("utf-8")),
        "checkpoint": "demo.safetensors",
        "checkpoint_sha256": sha(b"synthetic-fixture-bytes-no-real-weights"),
        "model_revision": "operator-provided-v1",
        "model_terms_url": "https://example.org/local-model-terms",
        "acknowledged_terms_for_local_use": True,
    }
    doc = {"schema_version": 1, "recipe_sha256": recipe_sha256(recipe),
           "stages": {"generate": deepcopy(stage), "cutout": deepcopy(stage)}}
    return recipe, doc, workflows, weights


def verified(inputs):
    recipe, doc, workflows, weights = inputs
    return resolve_local_micro(recipe, LocalBindings.model_validate(doc), workflows, weights)


def test_resolve_exact_local_bytes_with_explicit_unverified_runtime(inputs):
    receipt = verified(inputs)
    assert len(receipt["external_stage_inputs"]) == 2
    assert receipt["status"] == "offline_files_verified"
    assert len(receipt["resolved_inputs_sha256"]) == 64
    assert receipt["recipe_sha256"] == recipe_sha256(inputs[0])
    assert receipt["local_model_executable"] is False
    assert receipt["recipe_journal_pinning_implemented"] is False
    assert receipt["third_party_license_approved"] is False
    assert receipt["provider_calls_or_downloads"] is False
    assert all(stage["operator_acknowledged_terms"] for stage in receipt["external_stage_inputs"])


def test_repeat_fingerprint_is_stable_and_model_revisions_change_identity(inputs):
    first = verified(inputs)["resolved_inputs_sha256"]
    assert first == verified(inputs)["resolved_inputs_sha256"]
    recipe, doc, workflows, weights = inputs
    doc["stages"]["generate"]["model_revision"] = "different-revision"
    second = resolve_local_micro(recipe, LocalBindings.model_validate(doc),
                                 workflows, weights)["resolved_inputs_sha256"]
    assert first != second


def test_rejects_wrong_recipe_sha_before_inspecting_model_files(inputs):
    recipe, doc, workflows, weights = inputs
    doc["recipe_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Recipe fingerprint changed"):
        resolve_local_micro(recipe, LocalBindings.model_validate(doc),
                            workflows, weights)


def test_rejects_missing_extra_and_unacknowledged_external_stages(inputs):
    recipe, doc, workflows, weights = inputs
    del doc["stages"]["cutout"]
    with pytest.raises(ValueError, match="every and only"):
        resolve_local_micro(recipe, LocalBindings.model_validate(doc), workflows, weights)
    doc["stages"]["cutout"] = deepcopy(doc["stages"]["generate"])
    doc["stages"]["cutout"]["acknowledged_terms_for_local_use"] = False
    with pytest.raises((ValueError, ValidationError)):
        LocalBindings.model_validate(doc)
    doc["stages"]["cutout"]["acknowledged_terms_for_local_use"] = True
    doc["stages"]["ghost"] = deepcopy(doc["stages"]["generate"])
    with pytest.raises(ValueError, match="every and only"):
        resolve_local_micro(recipe, LocalBindings.model_validate(doc), workflows, weights)


def test_wrong_checkpoint_bytes_fail_closed(inputs):
    recipe, doc, workflows, weights = inputs
    (weights / "demo.safetensors").write_bytes(b"modified")
    with pytest.raises(ValueError, match="Checkpoint SHA256 mismatch"):
        resolve_local_micro(recipe, LocalBindings.model_validate(doc), workflows, weights)


def test_wrong_graph_bytes_fail_closed(inputs):
    recipe, doc, workflows, weights = inputs
    (workflows / "api.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Workflow SHA256 mismatch"):
        resolve_local_micro(recipe, LocalBindings.model_validate(doc), workflows, weights)


def test_comfyui_graph_shape_is_not_assumed(inputs):
    recipe, doc, workflows, weights = inputs
    broken = '{"abc": {"inputs": {}}}'
    (workflows / "api.json").write_text(broken, encoding="utf-8")
    for stage in doc["stages"].values():
        stage["workflow_sha256"] = sha(broken.encode("utf-8"))
    with pytest.raises(ValueError, match="ComfyUI API graph"):
        resolve_local_micro(recipe, LocalBindings.model_validate(doc), workflows, weights)


@pytest.mark.parametrize("bad", ["../escape.safetensors", "/tmp/absolute.safetensors",
                                  "sub/../../evil.safetensors", ".hidden.safetensors",
                                  "CON.safetensors", "x\\bad.safetensors"])
def test_unsafe_relative_paths_refused(inputs, bad):
    doc = inputs[1]
    doc["stages"]["generate"]["checkpoint"] = bad
    with pytest.raises((ValueError, ValidationError)):
        LocalBindings.model_validate(doc)


def test_symlinks_refused_even_if_inside_approved_roots(inputs):
    recipe, doc, workflows, weights = inputs
    try:
        (weights / "linked.safetensors").symlink_to(weights / "demo.safetensors")
    except (OSError, NotImplementedError):
        pytest.skip("OS policy disallows unprivileged symlinks")
    doc["stages"]["generate"]["checkpoint"] = "linked.safetensors"
    with pytest.raises(ValueError, match="Symlinked"):
        resolve_local_micro(recipe, LocalBindings.model_validate(doc), workflows, weights)


def test_external_rights_not_inherited_and_terms_must_be_public_https(inputs):
    doc = inputs[1]
    doc["stages"]["generate"]["model_terms_url"] = "http://localhost/terms?token=secret"
    with pytest.raises((ValueError, ValidationError)):
        LocalBindings.model_validate(doc)


def test_macro_refused_even_with_binding_for_similarly_named_stages(inputs):
    _, doc, workflows, weights = inputs
    with pytest.raises(ValueError, match="only micro"):
        resolve_local_micro(load_recipe(MACRO), LocalBindings.model_validate(doc),
                            workflows, weights)


def test_duplicate_binding_keys_rejected_before_parsing(inputs, tmp_path):
    path = tmp_path / "bindings.json"
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        load_local_bindings(path)


def test_no_files_written_by_resolver(inputs):
    recipe, doc, workflows, weights = inputs
    before = {str(p): (p.stat().st_size, p.stat().st_mtime_ns)
              for root in (workflows, weights) for p in root.iterdir()}
    verified(inputs)
    after = {str(p): (p.stat().st_size, p.stat().st_mtime_ns)
             for root in (workflows, weights) for p in root.iterdir()}
    assert before == after
