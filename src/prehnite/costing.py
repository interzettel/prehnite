"""Conservative request-count estimator; NOT a provider billing quote."""
from __future__ import annotations

from .schema import Manifest, Profile


def estimate_costs(manifest: Manifest, profile: Profile) -> dict:
    counts: dict[str, int] = {}
    maximum = profile.policy.maximum_attempts
    for asset in manifest.assets:
        if asset.prompt:
            for _ in range(maximum):
                for variant in profile.variants:
                    if profile.generation.provider == "fal":
                        tier = "2k" if variant == "enhanced_2k" else "4k"
                        key = "generation:" + tier
                        counts[key] = counts.get(key, 0) + 1
                    if variant == "enhanced_2k" and profile.upscale.provider == "fal":
                        counts["upscale"] = counts.get("upscale", 0) + 1
                if profile.judge.provider == "anthropic":
                    counts["judge"] = counts.get("judge", 0) + 2
        if asset.source and profile.judge.provider == "anthropic":
            counts["judge"] = counts.get("judge", 0) + 1
        # A successful image is segmented once per named object. Cutout
        # refinement can trigger two judge calls, without regenerating its mask.
        if profile.segmentation.provider == "fal":
            counts["segmentation"] = counts.get("segmentation", 0) + len(asset.targets)
        if profile.judge.provider == "anthropic":
            counts["judge"] = counts.get("judge", 0) + 2 * len(asset.targets)
    unavailable = [key for key in counts if key not in profile.costs.estimates_usd]
    estimates = {
        key: round(count * profile.costs.estimates_usd.get(key, 0), 5)
        for key, count in counts.items()
    }
    total = round(sum(estimates.values()), 5)
    return {
        "batch_id": manifest.id,
        "asset_count": len(manifest.assets),
        "assumed_max_generation_attempts": maximum,
        "calls_by_billable_operation": counts,
        "estimated_costs_usd": estimates,
        "estimated_upper_scenario_usd": total,
        "configured_batch_limit_usd": profile.costs.max_usd,
        "missing_price_estimates": unavailable,
        "may_hit_budget_limit": total > profile.costs.max_usd if profile.costs.allow_paid else False,
        "warning": (
            "User-maintained fixed prices, not live rates. This is a scenario "
            "estimate, NOT a guaranteed billing ceiling; provider charges "
            "and uncertain submissions require reconciliation."
        ),
    }
