"""Strict local micro recipe-to-engine bridge: no downloads or hosted inference.

The existing ComfyUI provider still owns actual execution. This module verifies
that an operator's pinned local recipe refers to exactly the same configured
ComfyUI stages before allowing a run, and rechecks local bytes on each resume.
Static ComfyUI node checks are not execution/hardware/license certification.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .recipe_resolver import LocalBindings, load_local_bindings, resolve_local_micro, _local_file
from .recipes import Recipe, load_recipe
from .schema import Profile


@dataclass(frozen=True)
class MicroExecution:
    """Caller-owned paths; only hash receipts, never private paths, reach SQLite."""
    recipe_path: Path
    bindings_path: Path
    workflows_root: Path
    checkpoints_root: Path

    def verify(self, profile: Profile) -> dict:
        recipe = load_recipe(self.recipe_path)
        bindings = load_local_bindings(self.bindings_path)
        resolved = resolve_local_micro(recipe, bindings, self.workflows_root,
                                       self.checkpoints_root)
        verify_micro_profile(recipe, bindings, self.workflows_root, profile)
        return {
            "schema_version": 1,
            "recipe_id": resolved["recipe_id"],
            "recipe_version": resolved["recipe_version"],
            "recipe_sha256": resolved["recipe_sha256"],
            "resolved_inputs_sha256": resolved["resolved_inputs_sha256"],
            "profile_connection": "local_comfyui_only",
            "hardware_verified": False,
            "runtime_verified": False,
            "external_rights_approved": False,
            "automatic_spending_enabled": False,
        }

def verify_micro_profile(recipe: Recipe, bindings: LocalBindings,
                         workflows_root: Path, profile: Profile) -> None:
    """Check an existing micro profile against exact workflow files; no writes."""
    if (profile.costs.allow_paid or profile.costs.allow_cloud_uploads
            or profile.costs.max_usd != 0 or profile.costs.estimates_usd):
        raise ValueError("Local micro recipe cannot authorize cloud uploads or spending")
    if profile.cache.enabled or profile.cache.allow_paid:
        raise ValueError("Recipe-bound runs disable cross-batch cache until keyed by recipe")
    variants_by_recipe = {
        "0.1.0-preview.1": ["native_4k"],
        "0.1.0-preview.2": ["native_1k"],
    }
    required_variants = variants_by_recipe.get(recipe.version)
    if required_variants is None or profile.variants != required_variants:
        raise ValueError("Micro recipe version requires matching native variant (no upscale stage)")
    graph_map = {"generate": ("generation", "generate"),
                 "cutout": ("segmentation", "segment")}
    if [stage.id for stage in recipe.stages] != ["generate", "cutout", "quality"]:
        raise ValueError("Micro runtime requires generate -> cutout -> quality recipe")
    if [(stage.operation, stage.depends_on) for stage in recipe.stages] != [
            ("generate", []), ("segment", ["generate"]),
            ("judge", ["generate", "cutout"])]:
        raise ValueError("Micro runtime cannot execute the proposed dependency DAG")
    if not (profile.judge.provider == "demo"
            and profile.judge.model == "technical"):
        raise ValueError("Recipe quality stage requires demo technical judge")
    if profile.upscale.provider != "disabled":
        raise ValueError("Micro runtime requires upscale to be disabled")
    root = workflows_root.resolve(strict=True)
    active_workflows = Path(os.environ.get("PREHNITE_WORKFLOWS", "./workflows")).resolve()
    if active_workflows != root:
        raise ValueError("PREHNITE_WORKFLOWS must exactly match verified workflow root")
    for stage in recipe.stages:
        if stage.id not in graph_map:
            continue
        endpoint_name, operation = graph_map[stage.id]
        endpoint = getattr(profile, endpoint_name)
        if (stage.operation != operation or endpoint.provider != stage.model.provider
                or endpoint.model != stage.model.model or endpoint.provider != "comfyui"):
            raise ValueError(f"Configured {endpoint_name} disagrees with recipe model")
        binding = bindings.stages[stage.id]
        if "/" in binding.workflow or "\\" in binding.workflow:
            raise ValueError("ComfyUI adapter supports only root-level workflow filenames")
        if endpoint.options.get("workflow") != binding.workflow:
            raise ValueError(f"Configured {endpoint_name} graph is not the verified graph")
        if not endpoint.options.get("output_node"):
            raise ValueError(f"Configured {endpoint_name} needs explicit output_node")
        # A graph must actually mention the operator's selected local
        # checkpoint by its exact ComfyUI loader value, not just contain
        # arbitrary user-supplied checkpoint hashes in a separate file.
        graph_path = _local_file(workflows_root, binding.workflow)
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        references = {
            value for node in graph.values() for value in node["inputs"].values()
            if isinstance(value, str)
        }
        if binding.checkpoint not in references:
            raise ValueError(f"Stage {stage.id} graph has no pinned checkpoint reference")

