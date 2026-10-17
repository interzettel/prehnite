"""Single-asset price/permission planning never calls a provider or writes data."""
from pathlib import Path
import pytest

from prehnite.schema import Profile, Manifest
from prehnite.trial_preflight import trial_plan


def asset(cutout=False):
    return {"id": "one", "prompt": "A lamp on paper", "aspect_ratio": "3:4",
            "target_size": [1536, 2048], "seed": 41,
            "targets": ["lamp"] if cutout else [],
            "output": {"image": "one.png",
                       "cutouts": {"lamp": "lamp.png"} if cutout else {}}}


def profile(mode, cutout=False):
    doc = {
        "variants": ["native_4k"],
        "generation": {"provider": "fal" if mode == "fal" else "comfyui",
                       "model": "blackforestlabs/flux-3/klein/text-to-image"
                       if mode == "fal" else "user-workflow",
                       "options": {} if mode == "fal" else {"workflow": "generate.json"}},
        "segmentation": {"provider": "fal" if mode == "fal" else "comfyui",
                         "model": "fal-ai/sam-3-1/image"
                         if mode == "fal" else "user-segmentation",
                         "options": {} if mode == "fal" else {"workflow": "cutout.json"}}
                        if cutout else {"provider": "disabled"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"maximum_attempts": 1, "uncertain": "reject"},
        "costs": {
            "allow_paid": mode == "fal", "allow_cloud_uploads": mode == "fal",
            "max_usd": 0.10 if mode == "fal" else 0,
            "estimates_usd": {"generation:4k": 0.036, "segmentation": 0.02}
                             if mode == "fal" else {},
        },
    }
    return Profile.model_validate(doc)


def test_paid_fal_trial_is_plan_only_and_under_owner_cap(tmp_path):
    manifest = Manifest.model_validate({"id": "fal-test", "assets": [asset()]})
    report = trial_plan(manifest, profile("fal"), mode="fal",
                        max_test_usd=0.10, input_root=tmp_path)
    assert report["mode"] == "fal"
    assert report["scenario"]["estimated_upper_scenario_usd"] == 0.036
    assert report["scenario"]["calls_by_billable_operation"] == {"generation:4k": 1}
    assert report["provider_calls_made"] == report["amount_spent_usd"] == 0
    assert report["prices_verified_live"] is False


def test_fal_generation_and_segmentation_counts_are_explicit(tmp_path):
    manifest = Manifest.model_validate({"id": "fal-matte", "assets": [asset(True)]})
    report = trial_plan(manifest, profile("fal", True), mode="fal",
                        max_test_usd=0.10, input_root=tmp_path)
    assert report["scenario"]["calls_by_billable_operation"]["segmentation"] == 1
    assert report["scenario"]["estimated_upper_scenario_usd"] == 0.056


def test_local_first_trial_requires_cutout_and_has_zero_spend(tmp_path):
    manifest = Manifest.model_validate({"id": "local", "assets": [asset(True)]})
    report = trial_plan(manifest, profile("local", True), mode="local",
                        max_test_usd=0, input_root=tmp_path)
    assert report["maximum_operator_trial_budget_usd"] == 0
    assert report["provider_calls_made"] == 0


@pytest.mark.parametrize("change,cap,message", [
    ({"costs": {"max_usd": 1}}, 0.10, "budget"),
    ({"policy": {"maximum_attempts": 2}}, 0.10, "maximum_attempts"),
    ({"variants": ["enhanced_2k", "native_4k"]}, 0.10, "one image variant"),
])
def test_paid_trial_refuses_unbounded_or_repeated_execution(tmp_path, change, cap, message):
    manifest = Manifest.model_validate({"id": "fal-test", "assets": [asset()]})
    configured = profile("fal").model_dump(mode="json")
    for key, values in change.items():
        if isinstance(values, dict):
            configured[key].update(values)
        else:
            configured[key] = values
    if len(configured["variants"]) > 1:
        configured["upscale"] = {"provider": "fal", "model": "fal-ai/esrgan"}
        configured["costs"]["estimates_usd"]["generation:2k"] = 0.014
        configured["costs"]["estimates_usd"]["upscale"] = 0.015
    with pytest.raises(ValueError, match=message):
        trial_plan(manifest, Profile.model_validate(configured), mode="fal",
                   max_test_usd=cap, input_root=tmp_path)


def test_multiple_asset_trial_refused(tmp_path):
    second = asset()
    second["id"] = "two"
    second["output"]["image"] = "two.png"
    manifest = Manifest.model_validate({"id": "too-many", "assets": [asset(), second]})
    with pytest.raises(ValueError, match="exactly one"):
        trial_plan(manifest, profile("fal"), mode="fal", max_test_usd=0.10,
                   input_root=tmp_path)


def test_missing_price_estimate_refused_by_existing_job_validator(tmp_path):
    p = profile("fal")
    p.costs.estimates_usd.clear()
    m = Manifest.model_validate({"id": "missing", "assets": [asset()]})
    with pytest.raises(ValueError, match="Missing price estimates"):
        trial_plan(m, p, mode="fal", max_test_usd=0.10, input_root=tmp_path)


def test_fal_trial_never_accepts_zero_cap(tmp_path):
    m = Manifest.model_validate({"id": "fal", "assets": [asset()]})
    with pytest.raises(ValueError, match="positive explicit cost"):
        trial_plan(m, profile("fal"), mode="fal", max_test_usd=0, input_root=tmp_path)
