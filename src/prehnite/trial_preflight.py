"""Preflight a strictly bounded local or fal trial without invoking either provider.

This is not a real-time price quote or model-rights certificate.
"""
from __future__ import annotations

from .costing import estimate_costs
from .manifest import validate_job
from .schema import Manifest, Profile


def trial_plan(manifest: Manifest, profile: Profile, *, mode: str,
               max_test_usd: float, input_root) -> dict:
    if mode not in ("local", "fal"):
        raise ValueError("Trial mode must be local or fal")
    if not (0 <= max_test_usd <= 100):
        raise ValueError("Trial budget limit must be within [0, 100] USD")
    validate_job(manifest, profile, input_root)
    if len(manifest.assets) != 1:
        raise ValueError("First trial must contain exactly one asset")
    if profile.policy.maximum_attempts != 1:
        raise ValueError("First trial requires maximum_attempts=1")
    if len(profile.variants) != 1:
        raise ValueError("First trial requires exactly one image variant")
    estimate = estimate_costs(manifest, profile)
    if mode == "local":
        if (profile.generation.provider != "comfyui" or
                profile.segmentation.provider != "comfyui" or
                profile.judge.provider not in ("demo", "disabled") or
                profile.upscale.provider != "disabled"):
            raise ValueError("Local trial needs two ComfyUI stages and no hosted judge/upscale")
        if profile.costs.allow_paid or profile.costs.allow_cloud_uploads or profile.costs.max_usd:
            raise ValueError("Local trial must have all paid/cloud policy disabled")
        if max_test_usd != 0:
            raise ValueError("Local trial has an explicit zero-dollar cap")
        if not manifest.assets[0].targets:
            raise ValueError("First local trial requires a cutout target")
    if mode == "fal":
        if (profile.generation.provider != "fal" or
                profile.judge.provider not in ("demo", "disabled") or
                profile.upscale.provider not in ("disabled", "fal") or
                profile.segmentation.provider not in ("disabled", "fal")):
            raise ValueError("fal trial requires explicitly supported fal/demo-only stages")
        if not profile.costs.allow_paid or max_test_usd <= 0:
            raise ValueError("fal trial requires positive explicit cost authorization")
        if profile.costs.max_usd > max_test_usd:
            raise ValueError("Profile's configured budget exceeds the trial budget cap")
        if profile.costs.max_usd < estimate["estimated_upper_scenario_usd"]:
            raise ValueError("Trial scenario estimate exceeds the profile spend limit")
        if estimate["missing_price_estimates"]:
            raise ValueError("Trial has unresolved user-supplied price estimates")
        if profile.segmentation.provider == "fal" and not profile.costs.allow_cloud_uploads:
            raise ValueError("fal segmentation requires explicit upload consent")
        if manifest.assets[0].source and not profile.costs.allow_cloud_uploads:
            raise ValueError("Source image upload is not authorized")
    return {
        "schema_version": 1,
        "mode": mode,
        "status": "static_ready_no_provider_calls",
        "batch_id": manifest.id,
        "asset_count": 1,
        "maximum_attempts": 1,
        "variants": profile.variants,
        "provider_calls_made": 0,
        "amount_spent_usd": 0,
        "scenario": estimate,
        "maximum_operator_trial_budget_usd": max_test_usd,
        "prices_verified_live": False,
        "licenses_independently_verified": False,
        "image_quality_verified": False,
        "confirmation": "No provider calls were made. Operator must separately run the batch.",
    }
