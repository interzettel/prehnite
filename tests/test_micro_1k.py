"""True local 1K must never be relabeled, silently upscaled or billed."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from prehnite.comfy import Comfy, MICRO_1K_DIMENSIONS
from prehnite.engine import Engine
from prehnite.manifest import load_manifest, load_profile, validate_job
from prehnite.providers import fal_generation_inputs
from prehnite.recipe_execution import MicroExecution
from prehnite.recipes import load_recipe, recipe_sha256
from prehnite.recipe_resolver import LocalBindings, resolve_local_micro
from prehnite.schema import Endpoint, Manifest, Profile
from prehnite.trial_preflight import trial_plan
from prehnite.recipe_resolver import _sha256_file

ROOT = Path(__file__).resolve().parents[1]


def local():
    return (load_manifest(ROOT / "examples/manifest-first-local-1k.yaml"),
            load_profile(ROOT / "examples/profile-first-local-1k.yaml"))


def test_all_native_1k_dimensions_bounded_and_exact():
    assert MICRO_1K_DIMENSIONS == {
        "9:16": (576, 1024), "3:4": (768, 1024), "4:3": (1024, 768),
        "16:9": (1024, 576), "1:1": (1024, 1024),
    }
    assert max(w * h for w, h in MICRO_1K_DIMENSIONS.values()) <= 1024 * 1024


def test_local_one_asset_preflight_is_zero_spend(tmp_path):
    manifest, profile = local()
    result = trial_plan(manifest, profile, mode="local",
                        max_test_usd=0, input_root=tmp_path)
    assert result["asset_count"] == 1
    assert result["variants"] == ["native_1k"]
    assert result["provider_calls_made"] == 0
    assert result["amount_spent_usd"] == 0


def test_manifest_refuses_4k_target_disguised_as_1k(tmp_path):
    manifest, profile = local()
    manifest.assets[0].target_size = (3072, 4096)
    with pytest.raises(ValueError, match="exact native 1K"):
        validate_job(manifest, profile, tmp_path)


def test_1k_fal_and_demo_providers_not_allowed(tmp_path):
    manifest, profile = local()
    for provider in ("fal", "demo"):
        changed = profile.model_copy(deep=True)
        changed.generation.provider = provider
        with pytest.raises(ValueError, match="only local ComfyUI"):
            validate_job(manifest, changed, tmp_path)
    with pytest.raises(ValueError, match="resolution tier"):
        fal_generation_inputs(Endpoint(provider="fal", model="blackforestlabs/flux-3/klein/text-to-image"),
                              "a lamp", "3:4", "1k", 7)


def test_comfyui_1k_updates_real_node_dimensions_without_network(tmp_path, monkeypatch):
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    graph = {
        "3": {"class_type": "KSampler", "inputs": {"seed": 7}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 12, "height": 12}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["5", 0]}},
    }
    (workflows / "generation_api.json").write_text(json.dumps(graph))
    monkeypatch.setenv("PREHNITE_WORKFLOWS", str(workflows))
    captures = []
    def fake_render(self, actual, endpoint, output, on_submit=None, resume_id=None):
        captures.append(actual)
        return "offline graph shape only"
    monkeypatch.setattr(Comfy, "_render", fake_render)
    endpoint = Endpoint(provider="comfyui", model="user-workflow", options={
        "workflow": "generation_api.json", "prompt_node": "6", "seed_node": "3",
        "size_node": "5", "output_node": "9",
    })
    Comfy().generate("studio lamp", "3:4", "1k", 42, tmp_path / "test.png", endpoint)
    assert captures[0]["5"]["inputs"] == {"width": 768, "height": 1024}
    assert captures[0]["3"]["inputs"]["seed"] == 42


def test_engine_refuses_fake_native_1k_after_provider_stage(tmp_path, monkeypatch):
    manifest, profile = local()
    runner = Engine(manifest, profile, tmp_path, inputs=tmp_path)
    def stage(*args, **kwargs):
        output = args[3]
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (384, 512), "blue").save(output)
    monkeypatch.setattr(runner, "stage", stage)
    with pytest.raises(ValueError, match="no implicit resize"):
        runner.generate(manifest.assets[0], "native_1k", 1, tmp_path / "out")
    assert not (tmp_path / "out" / "final.png").exists()
    runner.journal.close()


def test_old_and_new_recipes_are_distinct_and_backward_compatible():
    old = load_recipe(ROOT / "recipes/prehnite-micro/0.1.0-preview.1.json")
    new = load_recipe(ROOT / "recipes/prehnite-micro/0.1.0-preview.2.json")
    assert old.version == "0.1.0-preview.1"
    assert new.version == "0.1.0-preview.2"
    assert old.id == new.id == "prehnite-micro"
    assert recipe_sha256(old) != recipe_sha256(new)
    assert old.policy.allow_paid is new.policy.allow_paid is False
