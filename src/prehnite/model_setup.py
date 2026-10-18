"""Explicit, offline setup for operator-supplied local micro models and graphs.

This is not a downloader or a rights adjudicator. No HTTP calls, inference,
weight redistribution or ComfyUI runtime operations occur here.
"""
from __future__ import annotations

import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field

from .recipe_resolver import (
    LocalBindings, LocalStage, LocalModelFile, _json_document, _local_file, _sha256_file,
    _validate_graph, resolve_local_micro,
)
from .recipes import load_recipe, recipe_sha256
from .schema import Profile
from .comfy import segmentation_target_input


def _check_graph_node_mappings(profile: Profile, workflows_root: Path,
                               generation_graph: str, cutout_graph: str) -> None:
    """Ensure user-entered node IDs match ComfyUI's adapter input contract.

    Static validation can catch a broken export before the first GPU request,
    but cannot certify third-party node compatibility or loaded weights.
    """
    required = {
        "generation": (generation_graph, {
            "prompt_node": ("text",),
            "seed_node": (str(profile.generation.options.get("seed_input", "seed")),),
            "size_node": ("width", "height"),
        }),
        "segmentation": (cutout_graph, {
            "input_node": ("image",),
            "target_node": (segmentation_target_input(profile.segmentation),),
        }),
    }
    for name, (filename, checks) in required.items():
        endpoint = getattr(profile, name)
        graph = json.loads(_local_file(workflows_root, filename).read_text(encoding="utf-8"))
        for option, inputs in checks.items():
            node_id = endpoint.options.get(option)
            if not isinstance(node_id, (str, int)) or str(node_id) not in graph:
                raise ValueError(f"{name}.{option} requires a real node ID in the API graph")
            present = graph[str(node_id)].get("inputs")
            if not isinstance(present, dict) or not all(k in present for k in inputs):
                raise ValueError(f"{name}.{option} node must expose inputs {inputs}")
        output_id = endpoint.options.get("output_node")
        if not isinstance(output_id, (str, int)) or str(output_id) not in graph:
            raise ValueError(f"{name}.output_node must point to an existing saved image node")
        if "SaveImage" not in graph[str(output_id)]["class_type"]:
            raise ValueError(f"{name}.output_node must be a saved output image node")


class _Selection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: str
    filename: str
    graph_reference: str
    model_revision: str
    model_terms_url: str


class _SelectionFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: int
    stages: dict[str, list[_Selection]]


def _supplemental_models(path: Path, checkpoints_root: Path) -> dict[str, list[LocalModelFile]]:
    """Read a small private list of user-selected files. Never download weights."""
    payload = _SelectionFile.model_validate(_json_document(path, 128 * 1024))
    if payload.schema_version != 1 or set(payload.stages) != {"generate", "cutout"}:
        raise ValueError("Supplemental model manifest must list generate and cutout stages")
    if not any(payload.stages.values()):
        raise ValueError("Supplemental model manifest cannot be empty")
    result = {}
    for stage, entries in payload.stages.items():
        if len(entries) > 24:
            raise ValueError("Too many supplemental model files")
        result[stage] = []
        for entry in entries:
            proposed = LocalModelFile.model_validate({
                **entry.model_dump(), "sha256": "0" * 64,
                "acknowledged_terms_for_local_use": True,
            })
            file = _local_file(checkpoints_root, proposed.filename)
            result[stage].append(proposed.model_copy(update={
                "sha256": _sha256_file(file),
            }))
    return result


def prepare_micro_bindings(
    *,
    recipe_path: Path,
    workflows_root: Path,
    checkpoints_root: Path,
    generation_graph: str,
    generation_checkpoint: str,
    generation_revision: str,
    generation_terms_url: str,
    cutout_graph: str,
    cutout_checkpoint: str,
    cutout_revision: str,
    cutout_terms_url: str,
    acknowledged_terms: bool,
    destination: Path,
    profile: Profile | None = None,
    additional_models: Path | None = None,
    generation_checkpoint_graph_ref: str | None = None,
    cutout_checkpoint_graph_ref: str | None = None,
) -> dict:
    """Create bindings once only after exact bytes, rights acknowledgement and DAG checks.

    Destination is private operator state, create-only and outside approved
    model/workflow roots. Static input verification is not license approval.
    """
    if acknowledged_terms is not True:
        raise ValueError("Explicit --acknowledge-model-terms required for both local models")
    recipe = load_recipe(recipe_path)
    if recipe.kind != "micro":
        raise ValueError("Offline model setup supports only prehnite-micro")
    stage_inputs = {
        "generate": (generation_graph, generation_checkpoint,
                     generation_revision, generation_terms_url),
        "cutout": (cutout_graph, cutout_checkpoint,
                   cutout_revision, cutout_terms_url),
    }
    if {s.id for s in recipe.stages if s.model.provider != "demo"} != set(stage_inputs):
        raise ValueError("Micro recipe external stage layout changed: refuse setup")
    supplemental = (_supplemental_models(additional_models, checkpoints_root)
                    if additional_models else {"generate": [], "cutout": []})
    schema_version = 2 if additional_models else 1
    checkpoint_refs = {"generate": generation_checkpoint_graph_ref,
                       "cutout": cutout_checkpoint_graph_ref}
    if any(v is not None for v in checkpoint_refs.values()) and not additional_models:
        raise ValueError("Explicit loader aliases require --additional-models schema v2")
    stages = {}
    for stage_id, (workflow, checkpoint, revision, terms_url) in stage_inputs.items():
        # Validate file names/terms *before* accessing disk, including Windows rules.
        proposed = LocalStage.model_validate({
            "workflow": workflow,
            "workflow_sha256": "0" * 64,
            "checkpoint": checkpoint,
            "checkpoint_sha256": "0" * 64,
            "checkpoint_graph_reference": checkpoint_refs[stage_id],
            "additional_files": supplemental[stage_id],
            "model_revision": revision,
            "model_terms_url": terms_url,
            "acknowledged_terms_for_local_use": True,
        })
        graph_path = _local_file(workflows_root, proposed.workflow)
        model_path = _local_file(checkpoints_root, proposed.checkpoint)
        _validate_graph(graph_path)
        stages[stage_id] = proposed.model_copy(update={
            "workflow_sha256": _sha256_file(graph_path),
            "checkpoint_sha256": _sha256_file(model_path),
        })
    bindings = LocalBindings(
        schema_version=schema_version,
        recipe_sha256=recipe_sha256(recipe),
        stages=stages,
    )
    # Recheck the exact bytes before materializing any receipt.
    result = resolve_local_micro(recipe, bindings, workflows_root, checkpoints_root)
    if profile is not None:
        # MicroExecution.verify reads the existing validated JSON file; perform
        # the same strict profile invariants without writing a staging file.
        from .recipe_execution import verify_micro_profile
        verify_micro_profile(recipe, bindings, workflows_root, profile)
        _check_graph_node_mappings(profile, workflows_root, generation_graph, cutout_graph)

    target = destination.resolve(strict=False)
    for approved in (workflows_root, checkpoints_root):
        root = approved.resolve(strict=True)
        if target == root or target.is_relative_to(root):
            raise ValueError("Bindings destination cannot overlap checkpoint/workflow roots")
    if target.exists() or destination.is_symlink():
        raise FileExistsError("Bindings file exists; will not overwrite or mutate approved recipe")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise ValueError("Bindings parent directory must already exist and not be a symlink")
    payload = json.dumps(bindings.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"
    # Exclusive create protects against concurrent processes and accidental rewrite.
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
    return {
        "schema_version": schema_version,
        "status": "local_bindings_written_not_executed",
        "recipe_sha256": result["recipe_sha256"],
        "resolved_inputs_sha256": result["resolved_inputs_sha256"],
        "external_stages_bound": sorted(stages),
        "supplemental_model_file_count": sum(len(x) for x in supplemental.values()),
        "graph_file_reference_coverage": result["graph_file_reference_coverage"],
        "rights_independently_verified": False,
        "runtime_verified": False,
        "physical_gpu_verified": False,
        "provider_calls": 0,
        "downloads": 0,
        "paid_usd": 0,
    }
