"""Offline only: model setup never downloads, infers, spends or overwrites."""
import hashlib
import json
from pathlib import Path

import pytest

from prehnite.model_setup import prepare_micro_bindings
from prehnite.recipe_resolver import load_local_bindings, resolve_local_micro
from prehnite.recipes import load_recipe
from prehnite.schema import Profile
from prehnite.recipe_execution import MicroExecution

ROOT = Path(__file__).resolve().parents[1]
MICRO = ROOT / "recipes/prehnite-micro/0.1.0-preview.1.json"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    graphs = tmp_path / "graphs"
    weights = tmp_path / "weights"
    graphs.mkdir()
    weights.mkdir()
    graph = json.dumps({
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "fixture.safetensors"}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    })
    (graphs / "gen.json").write_text(graph, encoding="utf-8")
    (graphs / "cut.json").write_text(graph, encoding="utf-8")
    (weights / "fixture.safetensors").write_bytes(b"not-real-model-weights")
    monkeypatch.setenv("PREHNITE_WORKFLOWS", str(graphs))
    output = tmp_path / "private-bindings.json"
    kwargs = {
        "recipe_path": MICRO,
        "workflows_root": graphs,
        "checkpoints_root": weights,
        "generation_graph": "gen.json",
        "generation_checkpoint": "fixture.safetensors",
        "generation_revision": "owner-source-revision-v1",
        "generation_terms_url": "https://example.org/generation-license",
        "cutout_graph": "cut.json",
        "cutout_checkpoint": "fixture.safetensors",
        "cutout_revision": "owner-segmentation-revision-v1",
        "cutout_terms_url": "https://example.org/cutout-license",
        "acknowledged_terms": True,
        "destination": output,
    }
    return kwargs


def local_profile():
    return Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "comfyui", "model": "user-workflow",
                       "options": {"workflow": "gen.json", "output_node": "2"}},
        "segmentation": {"provider": "comfyui", "model": "user-segmentation",
                         "options": {"workflow": "cut.json", "output_node": "2"}},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "costs": {"allow_paid": False, "allow_cloud_uploads": False,
                  "max_usd": 0, "estimates_usd": {}},
    })


def test_create_once_and_unchanged_files(setup):
    graphs, weights = setup["workflows_root"], setup["checkpoints_root"]
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in
              [graphs/"gen.json", graphs/"cut.json", weights/"fixture.safetensors"]}
    receipt = prepare_micro_bindings(**setup, profile=local_profile())
    assert receipt["provider_calls"] == receipt["downloads"] == receipt["paid_usd"] == 0
    assert receipt["rights_independently_verified"] is False
    assert receipt["runtime_verified"] is False
    bindings = load_local_bindings(setup["destination"])
    resolved = resolve_local_micro(load_recipe(MICRO), bindings, graphs, weights)
    assert resolved["resolved_inputs_sha256"] == receipt["resolved_inputs_sha256"]
    assert bindings.stages["cutout"].checkpoint_sha256 == hashlib.sha256(
        b"not-real-model-weights").hexdigest()
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}
    with pytest.raises(FileExistsError):
        prepare_micro_bindings(**setup, profile=local_profile())


def test_setup_required_consent_prevents_any_write(setup):
    setup["acknowledged_terms"] = False
    with pytest.raises(ValueError, match="acknowledge-model-terms"):
        prepare_micro_bindings(**setup)
    assert not setup["destination"].exists()


def test_invalid_graph_refuses_before_writing(setup):
    (setup["workflows_root"]/"cut.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="ComfyUI API graph"):
        prepare_micro_bindings(**setup, profile=local_profile())
    assert not setup["destination"].exists()


def test_wrong_checkpoint_reference_refuses_with_profile(setup):
    p = setup["workflows_root"]/"cut.json"
    p.write_text(p.read_text().replace("fixture.safetensors", "not-found.safetensors"))
    with pytest.raises(ValueError, match="pinned checkpoint reference"):
        prepare_micro_bindings(**setup, profile=local_profile())
    assert not setup["destination"].exists()


def test_rejects_unsafe_checkpoint_and_terms(setup):
    setup["generation_checkpoint"] = "../fixture.safetensors"
    with pytest.raises(ValueError, match="Path traversal|non-canonical"):
        prepare_micro_bindings(**setup)
    assert not setup["destination"].exists()


def test_refuses_output_inside_checkpoint_root(setup):
    setup["destination"] = setup["checkpoints_root"] / "bindings.json"
    with pytest.raises(ValueError, match="cannot overlap"):
        prepare_micro_bindings(**setup)


def test_create_only_refuses_preexisting_symlink(setup):
    setup["destination"].write_text("do-not-overwrite")
    with pytest.raises(FileExistsError):
        prepare_micro_bindings(**setup)
    assert setup["destination"].read_text() == "do-not-overwrite"


def test_paid_profile_refused_before_writing(setup):
    profile = local_profile()
    profile.costs.allow_paid = True
    with pytest.raises(ValueError, match="Local micro recipe cannot authorize"):
        prepare_micro_bindings(**setup, profile=profile)
    assert not setup["destination"].exists()
