"""Manifest loading, static validation and safe input resolution."""
from pathlib import Path

import yaml

from .schema import Manifest, Profile


def load_manifest(path: str | Path) -> Manifest:
    return Manifest.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def load_profile(path: str | Path) -> Profile:
    return Profile.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def resolve_input(input_root: Path, relative: str) -> Path:
    root = input_root.resolve()
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise ValueError("Input escapes approved input root")
    if not result.is_file():
        raise FileNotFoundError(result)
    return result


def validate_job(manifest: Manifest, profile: Profile, input_root: Path,
                 dependency_root: Path | None = None) -> None:
    supported = {
        "generation": {"demo", "fal", "comfyui", "disabled"},
        "upscale": {"demo", "fal", "comfyui", "disabled"},
        "segmentation": {"demo", "fal", "comfyui", "disabled"},
        "judge": {"demo", "anthropic", "disabled"},
    }
    for name, allowed in supported.items():
        if getattr(profile, name).provider not in allowed:
            raise ValueError(f"Unsupported {name} provider: {getattr(profile, name).provider}")
    if manifest.handoff is not None:
        from .handoff import verify_handoff
        # Full review/source byte preflight happens BEFORE Engine creates a journal.
        verify_handoff(manifest, profile, input_root, dependency_root)
    elif not profile.variants:
        raise ValueError("Empty variants require an explicit reviewed-source handoff")
    elif dependency_root is not None:
        raise ValueError("Dependency root is only valid for a reviewed-source handoff")
    # Native 1K is a true local-size tier, not a small render relabeled or
    # silently enlarged to 4K. Enforce both configured provider and output size.
    if "native_1k" in profile.variants:
        from .registry import MICRO_1K_DIMENSIONS
        if profile.generation.provider != "comfyui":
            raise ValueError("native_1k supports only local ComfyUI generation")
        for asset in manifest.assets:
            if asset.prompt and asset.target_size != MICRO_1K_DIMENSIONS[asset.aspect_ratio]:
                raise ValueError("native_1k requires exact native 1K target_size; no upscaling")
    for a in manifest.assets:
        if a.source:
            resolve_input(input_root, a.source)
        elif profile.generation.provider == "disabled":
            raise ValueError("Generator disabled, but manifest contains prompts")
        if a.targets and profile.segmentation.provider == "disabled":
            raise ValueError("Targets requested but segmentation disabled")
    paid_stages = ("generation", "upscale", "segmentation", "judge")
    if not profile.costs.allow_paid:
        for stage in paid_stages:
            if getattr(profile, stage).provider in ("fal", "anthropic"):
                raise ValueError("Paid providers require allow_paid=true")
    else:
        from .costing import estimate_costs
        estimate = estimate_costs(manifest, profile)
        if estimate["missing_price_estimates"]:
            raise ValueError(
                "Missing price estimates for paid calls: "
                + ", ".join(estimate["missing_price_estimates"])
            )
        if estimate["calls_by_billable_operation"] and profile.costs.max_usd <= 0:
            raise ValueError("Paid batch requires a positive max_usd budget")
    if profile.judge.provider == "anthropic" and not profile.costs.allow_cloud_uploads:
        raise ValueError("Cloud judge needs upload permission")
    if not profile.costs.allow_cloud_uploads:
        for stage in ("upscale", "segmentation"):
            if getattr(profile, stage).provider == "fal":
                raise ValueError("Cloud uploads require allow_cloud_uploads=true")
    # Keep this last so missing quotes and explicit consent failures retain
    # their actionable errors; all checks still happen before any remote call.
    from .registry import validate_workflow_capabilities
    validate_workflow_capabilities(manifest, profile)
