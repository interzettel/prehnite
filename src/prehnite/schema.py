"""Strict, documented configuration and manifest contracts."""
from __future__ import annotations

import math
import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def relative_name(value: str) -> str:
    """Validate an archive-relative POSIX path before touching any filesystem."""
    if not value or "\\" in value or "\x00" in value or ":" in value:
        raise ValueError("Path must be a relative POSIX path without drive or NUL")
    p = PurePosixPath(value)
    if p.is_absolute() or value.startswith(("/", "./")) or any(
        part in ("", ".", "..") for part in value.split("/")
    ):
        raise ValueError("Path traversal / non-canonical output path")
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"COM{i}" for i in range(1, 10))
    reserved.update(f"LPT{i}" for i in range(1, 10))
    for part in p.parts:
        if (part.rstrip(" .") != part or part.split(".")[0].upper() in reserved
                or any(ord(char) < 32 for char in part)):
            raise ValueError("Unsafe or Windows-reserved path component")
    return str(p)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Output(Strict):
    image: str
    cutouts: dict[str, str] = Field(default_factory=dict)

    @field_validator("image")
    @classmethod
    def image_path(cls, value: str) -> str:
        path = relative_name(value)
        if not path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            raise ValueError("Image exports must be PNG, JPEG or WebP")
        return path

    @field_validator("cutouts")
    @classmethod
    def cutout_paths(cls, value: dict[str, str]) -> dict[str, str]:
        return {key: relative_name(path) for key, path in value.items()}


class Asset(Strict):
    id: str
    prompt: str | None = None
    source: str | None = None
    aspect_ratio: Literal["9:16", "3:4", "4:3", "16:9", "1:1"] = "3:4"
    target_size: tuple[int, int] = (3024, 4032)
    seed: int | None = None
    targets: list[str] = Field(default_factory=list)
    # Explicit, per-target owner declaration; never infer opacity from pixels.
    cutout_materials: dict[str, Literal["opaque", "unknown", "hair", "glass", "fabric", "translucent"]] = Field(default_factory=dict)
    output: Output

    @field_validator("id")
    @classmethod
    def check_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value):
            raise ValueError("ID must contain only letters, digits, underscores, dots, hyphens")
        return value

    @field_validator("source")
    @classmethod
    def check_source(cls, value: str | None) -> str | None:
        return relative_name(value) if value else value

    @model_validator(mode="after")
    def validate_asset(self) -> "Asset":
        if bool(self.prompt) == bool(self.source):
            raise ValueError("Provide exactly one of prompt or source")
        w, h = self.target_size
        if w < 64 or h < 64 or w * h > 24_000_000:
            raise ValueError("Invalid output size")
        a, b = (int(x) for x in self.aspect_ratio.split(":"))
        if abs(w / h - a / b) > 0.015:
            raise ValueError("Target size must match aspect ratio")
        if any(not t.strip() for t in self.targets):
            raise ValueError("Cutout targets must be non-empty")
        if set(self.output.cutouts) != set(self.targets):
            raise ValueError("Every target must have an output cutout path")
        if not set(self.cutout_materials).issubset(set(self.targets)):
            raise ValueError("Cutout material declaration refers to unknown target")
        if any(not p.lower().endswith(".png") for p in self.output.cutouts.values()):
            raise ValueError("Cutouts must be PNG files")
        return self


class Manifest(Strict):
    id: str
    assets: list[Asset] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def check_id(cls, value: str) -> str:
        return Asset.check_id(value)

    @model_validator(mode="after")
    def unique_destinations(self) -> "Manifest":
        ids = [a.id for a in self.assets]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate asset IDs")
        paths = [a.output.image for a in self.assets]
        paths += [p for a in self.assets for p in a.output.cutouts.values()]
        if len(paths) != len(set(path.casefold() for path in paths)):
            raise ValueError("Duplicate destination paths")
        return self


class Endpoint(Strict):
    provider: Literal["demo", "fal", "anthropic", "comfyui", "disabled"] = "demo"
    model: str = ""
    options: dict[str, str | int | float | bool] = Field(default_factory=dict)


class QualityPolicy(Strict):
    minimum_score: float = Field(default=0.75, ge=0, le=1)
    maximum_attempts: int = Field(default=2, ge=1, le=10)
    uncertain: Literal["reject", "accept_unverified"] = "reject"
    cutout_minimum_coverage: float = Field(default=0.002, ge=0, le=1)
    # Explicit, safe opt-in. A local repair is a review candidate, never accepted.
    local_repair_mode: Literal["disabled", "stage_for_review"] = "disabled"


class CostPolicy(Strict):
    allow_paid: bool = False
    allow_cloud_uploads: bool = False
    max_usd: float = Field(default=0.0, ge=0, allow_inf_nan=False)

    @field_validator("estimates_usd")
    @classmethod
    def validate_estimates(cls, estimates: dict[str, float]) -> dict[str, float]:
        if any(not math.isfinite(value) or value <= 0 for value in estimates.values()):
            raise ValueError("Billable estimates must be finite and strictly positive")
        return estimates
    # Fixed estimates; update with actual provider pricing before paid runs.
    estimates_usd: dict[str, float] = Field(default_factory=dict)


class CachePolicy(Strict):
    """Opt-in local cross-batch cache; namespace is an ownership boundary."""
    enabled: bool = False
    namespace: str = ""
    allow_paid: bool = False
    model_revisions: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_cache(self) -> "CachePolicy":
        if self.enabled and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}",
                                              self.namespace):
            raise ValueError("Enabled cache needs an explicit namespace (1-64 safe characters)")
        if self.allow_paid and not self.enabled:
            raise ValueError("allow_paid cache requires cache.enabled")
        for stage, revision in self.model_revisions.items():
            if stage not in ("generation", "upscaling", "segmentation"):
                raise ValueError("Unknown cache model revision stage")
            if not isinstance(revision, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", revision):
                raise ValueError("Cache model revision must be an immutable safe label")
        return self


class Profile(Strict):
    variants: list[Literal["enhanced_2k", "native_4k", "native_1k"]] = Field(
        default_factory=lambda: ["enhanced_2k", "native_4k"]
    )
    generation: Endpoint = Field(default_factory=Endpoint)
    upscale: Endpoint = Field(default_factory=Endpoint)
    segmentation: Endpoint = Field(default_factory=lambda: Endpoint(provider="disabled"))
    judge: Endpoint = Field(default_factory=lambda: Endpoint(provider="disabled"))
    policy: QualityPolicy = Field(default_factory=QualityPolicy)
    costs: CostPolicy = Field(default_factory=CostPolicy)
    cache: CachePolicy = Field(default_factory=CachePolicy)

    @model_validator(mode="after")
    def valid_profile(self) -> "Profile":
        if not self.variants or len(set(self.variants)) != len(self.variants):
            raise ValueError("Variants must be non-empty and unique")
        if self.generation.provider == "disabled" and self.variants:
            # Existing-image manifests may bypass generation.
            pass
        if "enhanced_2k" in self.variants and self.upscale.provider == "disabled":
            raise ValueError("enhanced_2k requires an upscale provider")
        if self.segmentation.provider != "disabled" and not self.segmentation.model:
            raise ValueError("Choose an explicit segmentation model")
        if self.judge.provider not in ("disabled", "demo") and not self.judge.model:
            raise ValueError("Choose an explicit judge model")
        return self
