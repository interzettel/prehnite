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


def validate_job(manifest: Manifest, profile: Profile, input_root: Path) -> None:
    supported = {
        "generation": {"demo", "fal", "comfyui", "disabled"},
        "upscale": {"demo", "fal", "comfyui", "disabled"},
        "segmentation": {"demo", "fal", "comfyui", "disabled"},
        "judge": {"demo", "anthropic", "disabled"},
    }
    for name, allowed in supported.items():
        if getattr(profile, name).provider not in allowed:
            raise ValueError(f"Unsupported {name} provider: {getattr(profile, name).provider}")
    for a in manifest.assets:
        if a.source:
            resolve_input(input_root, a.source)
        elif profile.generation.provider == "disabled":
            raise ValueError("Generator disabled, but manifest contains prompts")
        if a.targets and profile.segmentation.provider == "disabled":
            raise ValueError("Targets requested but segmentation disabled")
    if not profile.costs.allow_paid:
        for stage in ("generation", "upscale", "segmentation", "judge"):
            if getattr(profile, stage).provider in ("fal", "anthropic"):
                raise ValueError("fal stages require allow_paid=true")
    if profile.judge.provider == "anthropic" and not profile.costs.allow_cloud_uploads:
        raise ValueError("Cloud judge needs upload permission")
    if not profile.costs.allow_cloud_uploads:
        for stage in ("upscale", "segmentation"):
            if getattr(profile, stage).provider == "fal":
                raise ValueError("Cloud uploads require allow_cloud_uploads=true")
