"""Versioned, offline-only model recipes: contracts, not runnable workflows.

No weight downloads, GPU detection, inference calls, or third-party license
grants. A recipe is pinned to an immutable canonical JSON SHA256 for future
journal-bound replay. Execution requires separate, explicit implementation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .registry import MODELS

_RECIPE_ID = re.compile(r"^prehnite-[a-z][a-z0-9-]{1,49}$")
_STAGE_ID = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
_SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[a-z][a-z0-9.-]*))?$"
)
_REVISION = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/@+-]{1,126}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OPERATIONS = {"generate": "image", "upscale": "image",
               "segment": "alpha_mask", "matte": "alpha_mask",
               "judge": "verdict"}
_MAX_BYTES = 128 * 1024


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ModelPin(Strict):
    provider: Literal["demo", "comfyui", "fal", "anthropic"]
    model: str = Field(min_length=1, max_length=128)
    source_url: str | None = None
    revision: str | None = None
    weight_sha256: str | None = None
    pin_status: Literal["unresolved", "locally_hashed"] = "unresolved"
    license_review: Literal["required", "bundled_demo_code_only"] = "required"

    @model_validator(mode="after")
    def validate_model(self) -> "ModelPin":
        if self.provider != "demo" and self.license_review != "required":
            raise ValueError("External model rights cannot inherit the Prehnite code license")
        if self.provider == "demo":
            if self.pin_status != "unresolved" or self.weight_sha256:
                raise ValueError("Bundled demo code has no downloadable model weights")
        if self.pin_status == "locally_hashed":
            if (not self.revision or _REVISION.fullmatch(self.revision) is None
                    or not self.weight_sha256
                    or _SHA256.fullmatch(self.weight_sha256) is None
                    or self.provider not in ("comfyui",)):
                raise ValueError("Local weight pin requires a revision and 64-byte hex digest")
        elif self.weight_sha256 or self.revision:
            raise ValueError("Unresolved model cannot assert a revision or weight hash")
        if self.source_url is not None:
            from urllib.parse import urlsplit
            url = urlsplit(self.source_url)
            if (url.scheme != "https" or not url.hostname
                    or url.username or url.password or url.fragment
                    or url.hostname.lower() in ("localhost", "127.0.0.1")
                    or len(self.source_url) > 600):
                raise ValueError("Model source must be a plain HTTPS reference")
        return self


class RecipeStage(Strict):
    id: str
    operation: Literal["generate", "upscale", "segment", "matte", "judge"]
    execution: Literal["local", "hosted"]
    model: ModelPin
    depends_on: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_stage(self) -> "RecipeStage":
        if _STAGE_ID.fullmatch(self.id) is None:
            raise ValueError("Invalid stage ID")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("Duplicate stage dependencies")
        if self.id in self.depends_on:
            raise ValueError("Self-referential stage")
        if self.execution == "hosted" and self.model.provider not in ("fal", "anthropic"):
            raise ValueError("Hosted stage must use explicitly supported hosted provider")
        if self.execution == "local" and self.model.provider not in ("demo", "comfyui"):
            raise ValueError("Local stage cannot pretend hosted model weights are installable")
        return self


class RecipePolicy(Strict):
    auto_download_weights: Literal[False] = False
    bundle_model_weights: Literal[False] = False
    allow_paid: Literal[False] = False
    allow_cloud_uploads: Literal[False] = False
    max_usd: Literal[0] = 0
    provider_retries_enabled: Literal[False] = False


class Recipe(Strict):
    schema_version: Literal[1]
    id: str
    version: str
    kind: Literal["micro", "macro"]
    release_status: Literal["blueprint_only"]
    hardware_status: Literal["unverified"]
    capability_status: Literal["registry_declared_only"]
    policy: RecipePolicy
    stages: list[RecipeStage] = Field(min_length=2, max_length=20)
    description: str = Field(min_length=30, max_length=500)

    @model_validator(mode="after")
    def validate_recipe(self) -> "Recipe":
        if _RECIPE_ID.fullmatch(self.id) is None:
            raise ValueError("Recipe ID must be a stable prehnite- namespace")
        if self.id != f"prehnite-{self.kind}":
            raise ValueError("Recipe ID and micro/macro kind disagree")
        if _SEMVER.fullmatch(self.version) is None:
            raise ValueError("Recipe requires a canonical semantic version")
        names = [stage.id for stage in self.stages]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate stage IDs")
        graph = {stage.id: stage for stage in self.stages}
        matches = {(m.provider, m.model, m.capability): m for m in MODELS}
        for stage in self.stages:
            if any(dep not in graph for dep in stage.depends_on):
                raise ValueError(f"Unknown dependency for {stage.id}")
            if self.kind == "micro" and stage.execution != "local":
                raise ValueError("Micro recipes must remain local-first with no hosted stages")
            catalog = matches.get(
                (stage.model.provider, stage.model.model, stage.operation)
            )
            if catalog is None or catalog.adapter_status == "not_implemented":
                raise ValueError(f"Unknown or nonimplemented model capability: {stage.id}")
            if stage.operation == "generate":
                if stage.depends_on:
                    raise ValueError("Generation is a root stage")
            else:
                if not stage.depends_on:
                    raise ValueError("Non-generation stages require explicit parent")
                preceding = [graph[dep].operation for dep in stage.depends_on]
                if stage.operation in ("upscale", "segment", "matte"):
                    if not any(_OPERATIONS[x] == "image" for x in preceding):
                        raise ValueError("Image processing stage needs an RGB image input")
                if stage.operation == "judge":
                    if not any(_OPERATIONS[x] == "image" for x in preceding):
                        raise ValueError("Quality judge needs an image input")
        if sum(s.operation == "generate" for s in self.stages) != 1:
            raise ValueError("Recipe must have exactly one generation root")
        if not any(s.operation == "segment" for s in self.stages):
            raise ValueError("Recipe must include at least one cutout/segmentation stage")
        visit_state: dict[str, int] = {}

        def visit(stage_id: str) -> None:
            status = visit_state.get(stage_id, 0)
            if status == 1:
                raise ValueError("Stage graph contains a cycle")
            if status == 2:
                return
            visit_state[stage_id] = 1
            for dependency in graph[stage_id].depends_on:
                visit(dependency)
            visit_state[stage_id] = 2

        for stage_id in names:
            visit(stage_id)
        return self


def load_recipe(path: Path) -> Recipe:
    """Strict JSON only; reject duplicate keys, symlinks, large/unknown files."""
    if path.is_symlink() or path.suffix.lower() != ".json" or not path.is_file():
        raise ValueError("Recipe must be a regular local JSON file")
    if path.stat().st_size <= 0 or path.stat().st_size > _MAX_BYTES:
        raise ValueError("Invalid recipe file size")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        document = json.loads(path.read_text(encoding="utf-8"),
                              object_pairs_hook=reject_duplicates,
                              parse_constant=lambda value: (_ for _ in ()).throw(
                                  ValueError(f"Invalid JSON constant: {value}")
                              ))
    except UnicodeError as exc:
        raise ValueError("Recipe must use UTF-8") from exc
    return Recipe.model_validate(document)


def recipe_sha256(recipe: Recipe) -> str:
    """Canonical content identity for future immutable per-batch references."""
    data = recipe.model_dump(mode="json")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def describe_recipe(recipe: Recipe) -> dict:
    """Plan evidence only. Not a hardware, legal, or production approval."""
    return {
        "recipe": recipe.id, "version": recipe.version,
        "sha256": recipe_sha256(recipe),
        "stages": [stage.id for stage in recipe.stages],
        "stage_count": len(recipe.stages),
        "contains_hosted_models": any(x.execution == "hosted" for x in recipe.stages),
        "has_unresolved_model_pins": any(x.model.pin_status == "unresolved"
                                         and x.model.provider != "demo"
                                         for x in recipe.stages),
        "executable": False,
        "hardware_verified": False,
        "weights_included": False,
        "automatic_spending_enabled": False,
        "external_model_rights_approved": False,
        "status": "blueprint_only",
    }
