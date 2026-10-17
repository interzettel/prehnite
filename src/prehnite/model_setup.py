"""Explicit, offline setup for operator-supplied local micro models and graphs.

This is not a downloader or a rights adjudicator. No HTTP calls, inference,
weight redistribution or ComfyUI runtime operations occur here.
"""
from __future__ import annotations

import json
from pathlib import Path

from .recipe_execution import MicroExecution
from .recipe_resolver import (
    LocalBindings, LocalStage, _local_file, _sha256_file, _validate_graph,
    resolve_local_micro,
)
from .recipes import load_recipe, recipe_sha256
from .schema import Profile


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
    stages = {}
    for stage_id, (workflow, checkpoint, revision, terms_url) in stage_inputs.items():
        # Validate file names/terms *before* accessing disk, including Windows rules.
        proposed = LocalStage.model_validate({
            "workflow": workflow,
            "workflow_sha256": "0" * 64,
            "checkpoint": checkpoint,
            "checkpoint_sha256": "0" * 64,
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
        schema_version=1,
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
        "schema_version": 1,
        "status": "local_bindings_written_not_executed",
        "recipe_sha256": result["recipe_sha256"],
        "resolved_inputs_sha256": result["resolved_inputs_sha256"],
        "external_stages_bound": sorted(stages),
        "rights_independently_verified": False,
        "runtime_verified": False,
        "physical_gpu_verified": False,
        "provider_calls": 0,
        "downloads": 0,
        "paid_usd": 0,
    }
