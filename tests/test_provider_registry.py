"""Offline, zero-inference compatibility and fail-fast model preflight."""
from __future__ import annotations

import json

import pytest
from PIL import Image

from prehnite.cli import app
from prehnite.engine import Engine
from prehnite.manifest import validate_job
from prehnite.registry import (
    ASPECTS, ESRGAN_MODELS, list_models, validate_capability,
    validate_workflow_capabilities,
)
from prehnite.schema import Endpoint, Manifest, Profile


def manifest(*, source=False, targets=False, ratio="3:4"):
    width, height = {"3:4": (192, 256), "9:16": (144, 256),
                     "1:1": (256, 256)}[ratio]
    asset = {"id": "first", "aspect_ratio": ratio, "target_size": [width, height],
             "output": {"image": "photos/first.jpg"}}
    if source:
        asset["source"] = "existing.png"
    else:
        asset["prompt"] = "A small desk lamp"
    if targets:
        asset["targets"] = ["lamp"]
        asset["output"]["cutouts"] = {"lamp": "cutouts/lamp.png"}
    return Manifest.model_validate({"id": "registry-demo", "assets": [asset]})


def profile(*, generation="blackforestlabs/flux-3/klein/text-to-image",
            upscale="fal-ai/esrgan", options=None, variants=None,
            segmentation="disabled", allow_cloud=True,
            prices=True):
    return Profile.model_validate({
        "variants": variants or ["native_4k"],
        "generation": {"provider": "fal", "model": generation,
                       "options": options or {}},
        "upscale": {"provider": "fal" if upscale != "disabled" else "disabled",
                    "model": upscale if upscale != "disabled" else ""},
        "segmentation": {"provider": "fal" if segmentation != "disabled" else "disabled",
                         "model": segmentation if segmentation != "disabled" else ""},
        "judge": {"provider": "disabled"},
        "costs": {"allow_paid": True, "allow_cloud_uploads": allow_cloud,
                  "max_usd": 1.0,
                  "estimates_usd": ({"generation:2k": 0.05,
                                    "generation:4k": 0.05,
                                    "upscale": 0.02, "segmentation": 0.03}
                                   if prices else {})},
    })


def test_models_catalogue_is_machine_readable_and_does_not_invent_prices():
    models = list_models()
    json.dumps(models)
    assert models and all("licensing" in row and "price_status" in row
                          and "schema_url" in row for row in models)
    fal = [row for row in models if row["provider"] == "fal"]
    assert len({(row["provider"], row["model"], row["capability"])
                for row in models}) == len(models)
    assert all(row["price_status"] == "user_estimate_required" for row in fal)
    assert all("usd" not in row and "price_usd" not in row for row in fal)
    assert next(row for row in fal if row["model"] == "fal-ai/birefnet/v2")[
        "adapter_status"] == "not_implemented"
    assert next(row for row in fal if row["model"].endswith("/klein/text-to-image"))[
        "max_output_side"] == 4096


@pytest.mark.parametrize("endpoint,operation,keyword", [
    ("fal-ai/nonexistent", "generate", "Unsupported generate"),
    ("fal-ai/esrgan", "generate", "Unsupported generate"),
    ("blackforestlabs/flux-3/text-to-image", "upscale", "Unsupported upscale"),
    ("fal-ai/birefnet/v2", "matte", "Unsupported matte"),
    ("fal-ai/sam-3-1/image", "upscale", "Unsupported upscale"),
])
def test_wrong_model_or_operation_rejected_with_available_alternatives(
    endpoint, operation, keyword
):
    with pytest.raises(ValueError, match=keyword) as err:
        validate_capability(Endpoint(provider="fal", model=endpoint),
                            operation, allow_cloud_uploads=True)
    assert "available:" in str(err.value)


@pytest.mark.parametrize("tier,ratio", [
    ("8k", "3:4"), ("2k", "7:5"), ("hd", "1:1"), ("4k", "11:3")
])
def test_invalid_resolution_and_aspect_rejected_early(tier, ratio):
    with pytest.raises(ValueError, match="does not support"):
        validate_capability(
            Endpoint(provider="fal",
                     model="blackforestlabs/flux-3/klein/text-to-image"),
            "generate", tier=tier, ratio=ratio)


def test_every_manifest_aspect_supported_for_explicit_flux_tiers():
    for ratio in ASPECTS:
        for tier in ("2k", "4k"):
            validate_capability(
                Endpoint(provider="fal",
                         model="blackforestlabs/flux-3/klein/text-to-image"),
                "generate", ratio=ratio, tier=tier)


@pytest.mark.parametrize("options,why", [
    ({"unexpected_field": "value"}, "does not support options"),
    ({"enable_prompt_expansion": "yes"}, "must be a boolean"),
])
def test_model_options_must_match_documented_input_schema(options, why):
    with pytest.raises(ValueError, match=why):
        validate_capability(
            Endpoint(provider="fal",
                     model="blackforestlabs/flux-3/text-to-image",
                     options=options), "generate", ratio="3:4", tier="2k")


@pytest.mark.parametrize("options,why", [
    ({"scale": 4}, "supports only scale=2"),
    ({"scale": True}, "supports only scale=2"),
    ({"model": "invented_checkpoint"}, "Unsupported ESRGAN model"),
    ({"tile": 512}, "does not support options"),
])
def test_esrgan_unsupported_settings_fail_before_source_upload(options, why):
    with pytest.raises(ValueError, match=why):
        validate_capability(
            Endpoint(provider="fal", model="fal-ai/esrgan", options=options),
            "upscale", allow_cloud_uploads=True)


def test_supported_esrgan_model_variants_are_accepted():
    for model in ESRGAN_MODELS:
        validate_capability(
            Endpoint(provider="fal", model="fal-ai/esrgan",
                     options={"scale": 2, "model": model}),
            "upscale", allow_cloud_uploads=True)


def test_price_estimate_is_not_confused_with_live_invoice():
    from prehnite.costing import estimate_costs
    out = estimate_costs(manifest(), profile())
    assert out["price_provenance"] == "user_configured_unverified_not_live"
    assert out["model_rates_are_live"] is False
    assert "cost_is_actual_invoice" not in out


def test_unsupported_paid_generation_fails_without_creating_journal(tmp_path):
    bad = profile(generation="some-unregistered-expensive-model")
    workspace = tmp_path / "workspace"
    with pytest.raises(ValueError, match="Unsupported generate"):
        Engine(manifest(), bad, workspace)
    assert not workspace.exists()


def test_unsupported_upscaler_is_checked_only_if_variant_uses_it(tmp_path):
    invalid = profile(upscale="unknown-upscaler", variants=["native_4k"])
    validate_job(manifest(), invalid, tmp_path)
    updated = profile(upscale="unknown-upscaler",
                      variants=["enhanced_2k", "native_4k"])
    with pytest.raises(ValueError, match="Unsupported upscale"):
        validate_job(manifest(), updated, tmp_path)


def test_requested_segmentation_rejected_when_mismatched_provider(tmp_path):
    bad = profile(segmentation="blackforestlabs/flux-3/text-to-image")
    with pytest.raises(ValueError, match="Unsupported segment"):
        validate_job(manifest(targets=True), bad, tmp_path)


def test_cloud_upload_consent_is_required_if_image_leaves_machine(tmp_path):
    p = profile(segmentation="fal-ai/sam-3-1/image", allow_cloud=False)
    with pytest.raises(ValueError, match="Cloud uploads"):
        validate_job(manifest(targets=True), p, tmp_path)


def test_missing_user_price_is_rejected_before_model_work(tmp_path):
    p = profile(prices=False)
    with pytest.raises(ValueError, match="Missing price estimates"):
        validate_job(manifest(), p, tmp_path)


def test_existing_source_skips_unused_generation_provider(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    Image.new("RGB", (192, 256), "purple").save(inputs / "existing.png")
    p = profile(generation="unknown-model", variants=["native_4k"],
                upscale="disabled")
    validate_job(manifest(source=True), p, inputs)


def test_comfyui_allows_private_graph_labels_but_requires_workflow():
    ep = Endpoint(provider="comfyui", model="my-local-quantized-model",
                  options={"workflow": "custom_api.json", "base_url": "http://127.0.0.1:8188"})
    validate_capability(ep, "generate", ratio="9:16", tier="2k")
    with pytest.raises(ValueError, match="options.workflow"):
        validate_capability(Endpoint(provider="comfyui", model="local"),
                            "generate", ratio="3:4", tier="4k")


def test_demo_still_runs_without_paid_provider_or_model_registry_lock(tmp_path):
    m = manifest()
    p = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
    })
    e = Engine(m, p, tmp_path)
    try:
        assert e.run()["asset_results"]["first"]["status"] == "accepted"
    finally:
        e.journal.close()
