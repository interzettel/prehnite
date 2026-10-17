"""Offline multi-file model inputs: closed graph inventory, no runtime rights claim."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prehnite.model_setup import prepare_micro_bindings
from prehnite.recipe_execution import MicroExecution
from prehnite.recipe_resolver import load_local_bindings, resolve_local_micro
from prehnite.recipes import load_recipe
from prehnite.schema import Profile

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "recipes/prehnite-micro/0.1.0-preview.2.json"


@pytest.fixture
def multi(tmp_path, monkeypatch):
    graphs = tmp_path / "graphs"
    weights = tmp_path / "models"
    graphs.mkdir()
    weights.mkdir()
    for sub in ("diffusion_models", "text_encoders", "vae", "segmentation"):
        (weights / sub).mkdir()
    raw = {
        "diffusion_models/flux3.safetensors": b"synthetic transformer only",
        "text_encoders/encoder.safetensors": b"synthetic text encoder only",
        "vae/ae.safetensors": b"synthetic vae only",
        "segmentation/sam.safetensors": b"synthetic segmenter only",
    }
    for name, value in raw.items():
        (weights / name).write_bytes(value)
    graph = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux3.safetensors"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name": "encoder.safetensors"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "lamp"}},
        "5": {"class_type": "KSampler", "inputs": {"seed": 42}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1024}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}},
    }
    cut = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sam.safetensors"}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
        "10": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
        "11": {"class_type": "TextNode", "inputs": {"text": "lamp"}},
    }
    (graphs / "gen.json").write_text(json.dumps(graph))
    (graphs / "cut.json").write_text(json.dumps(cut))
    monkeypatch.setenv("PREHNITE_WORKFLOWS", str(graphs))
    supplement = tmp_path / "supplement.json"
    selection = {
        "schema_version": 1,
        "stages": {
            "generate": [
                {"role": "text_encoder", "filename": "text_encoders/encoder.safetensors",
                 "graph_reference": "encoder.safetensors",
                 "model_revision": "encoder-v1",
                 "model_terms_url": "https://example.org/encoder"},
                {"role": "vae", "filename": "vae/ae.safetensors",
                 "graph_reference": "ae.safetensors",
                 "model_revision": "vae-v1",
                 "model_terms_url": "https://example.org/vae"},
            ],
            "cutout": [],
        },
    }
    supplement.write_text(json.dumps(selection))
    profile = Profile.model_validate({
        "variants": ["native_1k"],
        "generation": {"provider": "comfyui", "model": "user-workflow",
                       "options": {"workflow": "gen.json", "output_node": "9",
                                   "prompt_node": "4", "seed_node": "5", "size_node": "6"}},
        "segmentation": {"provider": "comfyui", "model": "user-segmentation",
                         "options": {"workflow": "cut.json", "output_node": "2",
                                     "input_node": "10", "target_node": "11"}},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "costs": {"allow_paid": False, "allow_cloud_uploads": False, "max_usd": 0},
    })
    kwargs = {
        "recipe_path": RECIPE,
        "workflows_root": graphs,
        "checkpoints_root": weights,
        "generation_graph": "gen.json",
        "generation_checkpoint": "diffusion_models/flux3.safetensors",
        "generation_checkpoint_graph_ref": "flux3.safetensors",
        "generation_revision": "transformer-v1",
        "generation_terms_url": "https://example.org/transformer",
        "cutout_graph": "cut.json",
        "cutout_checkpoint": "segmentation/sam.safetensors",
        "cutout_checkpoint_graph_ref": "sam.safetensors",
        "cutout_revision": "segmenter-v1",
        "cutout_terms_url": "https://example.org/sam",
        "acknowledged_terms": True,
        "destination": tmp_path / "bindings.json",
        "additional_models": supplement,
        "profile": profile,
    }
    return kwargs, selection


def test_v2_pins_every_explicit_model_file_and_runs_no_model(multi):
    params, _ = multi
    receipt = prepare_micro_bindings(**params)
    assert receipt["schema_version"] == 2
    assert receipt["supplemental_model_file_count"] == 2
    assert receipt["provider_calls"] == receipt["downloads"] == receipt["paid_usd"] == 0
    assert receipt["graph_file_reference_coverage"] == "checked_for_known_weight_extensions"
    bound = load_local_bindings(params["destination"])
    assert len(bound.stages["generate"].additional_files) == 2
    resolved = resolve_local_micro(load_recipe(RECIPE), bound,
                                   params["workflows_root"], params["checkpoints_root"])
    assert resolved["resolved_inputs_sha256"] == receipt["resolved_inputs_sha256"]
    assert resolved["external_stage_inputs"][0]["graph_declared_file_references_matched"] is True
    assert len(resolved["external_stage_inputs"][0]["extra_model_files"]) == 2
    assert all("filename" not in f for f in resolved["external_stage_inputs"][0]["extra_model_files"])
    bridge = MicroExecution(RECIPE, params["destination"], params["workflows_root"],
                            params["checkpoints_root"])
    assert bridge.verify(params["profile"])["resolved_inputs_sha256"] == receipt["resolved_inputs_sha256"]
    with pytest.raises(FileExistsError):
        prepare_micro_bindings(**params)


def test_modified_auxiliary_weights_refuse_resume(multi):
    params, _ = multi
    prepare_micro_bindings(**params)
    (params["checkpoints_root"] / "text_encoders/encoder.safetensors").write_bytes(b"modified")
    with pytest.raises(ValueError, match="Supplemental model SHA256 mismatch"):
        MicroExecution(RECIPE, params["destination"], params["workflows_root"],
                       params["checkpoints_root"]).verify(params["profile"])


def test_graph_undeclared_weight_refused_before_writing(multi):
    params, _ = multi
    p = params["workflows_root"] / "gen.json"
    graph = json.loads(p.read_text())
    graph["8"] = {"class_type": "AdditionalModelLoader",
                  "inputs": {"model_name": "upsampler.safetensors"}}
    p.write_text(json.dumps(graph))
    with pytest.raises(ValueError, match="graph model references"):
        prepare_micro_bindings(**params)
    assert not params["destination"].exists()


def test_existing_primary_alias_or_auxiliary_absence_fails_closed(multi):
    params, _ = multi
    del params["generation_checkpoint_graph_ref"]
    with pytest.raises(ValueError, match="graph model references"):
        prepare_micro_bindings(**params)


def test_missing_aux_file_or_bad_role_fails_closed(multi):
    params, selection = multi
    path = params["additional_models"]
    selection["stages"]["generate"][0]["filename"] = "text_encoders/not-there.safetensors"
    path.write_text(json.dumps(selection))
    with pytest.raises((FileNotFoundError, ValueError)):
        prepare_micro_bindings(**params)
    assert not params["destination"].exists()


def test_untrusted_symlink_and_path_traversal_refused(multi):
    params, selection = multi
    selection["stages"]["generate"][0]["filename"] = "../outside.safetensors"
    params["additional_models"].write_text(json.dumps(selection))
    with pytest.raises(ValueError, match="noncanonical|Path traversal"):
        prepare_micro_bindings(**params)


def test_v1_never_claims_multifile_coverage(multi):
    params, _ = multi
    params["additional_models"] = None
    params["generation_checkpoint_graph_ref"] = None
    params["cutout_checkpoint_graph_ref"] = None
    with pytest.raises(ValueError, match="pinned checkpoint reference"):
        prepare_micro_bindings(**params)


def test_v2_requires_explicit_extra_file(multi):
    params, selection = multi
    selection["stages"] = {"generate": [], "cutout": []}
    params["additional_models"].write_text(json.dumps(selection))
    with pytest.raises(ValueError, match="cannot be empty"):
        prepare_micro_bindings(**params)


def test_unknown_graph_file_not_auto_downloaded(multi):
    params, selection = multi
    selection["stages"]["generate"][0]["filename"] = "text_encoders/missing.safetensors"
    params["additional_models"].write_text(json.dumps(selection))
    with pytest.raises((OSError, ValueError)):
        prepare_micro_bindings(**params)
    assert not params["destination"].exists()
