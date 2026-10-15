from prehnite.schema import Manifest, Profile
from prehnite.costing import estimate_costs


def test_cost_counts_and_upper_scenario():
    manifest = Manifest.model_validate({"id": "costpilot", "assets": [
        {"id": "a", "prompt": "test", "aspect_ratio": "3:4",
         "target_size": [192, 256], "output": {"image": "a.jpg"}}
    ]})
    profile = Profile.model_validate({
        "generation": {"provider": "fal", "model": "example"},
        "upscale": {"provider": "fal", "model": "example"},
        "judge": {"provider": "anthropic", "model": "example"},
        "policy": {"maximum_attempts": 2},
        "costs": {"allow_paid": True, "allow_cloud_uploads": True,
                  "max_usd": 1, "estimates_usd": {
                      "generation:2k": 0.02, "generation:4k": 0.04,
                      "upscale": 0.01, "judge": 0.01}}
    })
    out = estimate_costs(manifest, profile)
    assert out["calls_by_billable_operation"] == {
        "generation:2k": 2, "generation:4k": 2, "upscale": 2, "judge": 4
    }
    assert out["estimated_upper_scenario_usd"] == 0.18
    assert not out["missing_price_estimates"]
