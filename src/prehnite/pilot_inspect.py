"""Read-only ComfyUI graph introspection for a fixed 8 GiB generation pilot.

Does not start ComfyUI, inspect checkpoints, contact APIs or execute inference.
This is static mapping diagnostics, never a hardware or model-licence approval.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .comfy import _base_url
from .manifest import load_manifest, load_profile, validate_job

_MAX_BYTES = 2 * 1024 * 1024
_MAX_NODES = 512
_NODE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_KEYS = ("prompt_node", "seed_node", "size_node", "output_node")


def _graph(root: Path, filename: Any) -> tuple[dict, str]:
    if (not isinstance(filename, str) or not filename.endswith(".json")
            or filename.startswith(".") or "/" in filename or "\\" in filename):
        raise ValueError("workflow must be a simple .json filename in --workflows")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("--workflows must name an existing directory")
    source = (root / filename).resolve(strict=True)
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError("workflow must stay inside --workflows")
    if source.stat().st_size > _MAX_BYTES:
        raise ValueError("API graph exceeds 2 MiB inspection limit")
    raw = source.read_bytes()
    if len(raw) > _MAX_BYTES:
        raise ValueError("API graph exceeds 2 MiB inspection limit")
    graph = json.loads(raw)
    if not isinstance(graph, dict) or not 1 <= len(graph) <= _MAX_NODES:
        raise ValueError("expected a nonempty API graph with at most 512 nodes")
    for key, node in graph.items():
        if (not isinstance(key, str) or not _NODE_ID.fullmatch(key)
                or not isinstance(node, dict)
                or not isinstance(node.get("class_type"), str)
                or not isinstance(node.get("inputs"), dict)):
            raise ValueError("invalid ComfyUI API node shape")
    return graph, hashlib.sha256(raw).hexdigest()


def _candidates(graph: dict, keys: tuple[str, ...], *,
                saved_image: bool = False) -> list[dict[str, str]]:
    candidates = []
    for node_id, value in graph.items():
        inputs = value["inputs"]
        if not all(key in inputs for key in keys):
            continue
        if saved_image and "SaveImage" not in value["class_type"]:
            continue
        candidates.append({"id": node_id, "class_type": value["class_type"]})
    return sorted(candidates, key=lambda c: c["id"])


def inspect_generation_pilot(
    manifest_path: Path, profile_path: Path, workflows_root: Path
) -> dict:
    """Report exact candidate IDs, mapping errors and missing execution evidence.

    Never serializes input values, arbitrary graph text, prompts or model paths.
    """
    manifest = load_manifest(manifest_path)
    profile = load_profile(profile_path)
    validate_job(manifest, profile, workflows_root)
    if len(manifest.assets) != 10 or profile.variants != ["native_1k"]:
        raise ValueError("inspector requires the ten-item native-1K pilot shape")
    if any(not a.prompt or a.source or a.targets for a in manifest.assets):
        raise ValueError("inspector supports generation-only prompt assets")
    if (profile.generation.provider != "comfyui"
            or profile.upscale.provider != "disabled"
            or profile.segmentation.provider != "disabled"
            or profile.judge.provider not in ("demo", "disabled")
            or profile.policy.maximum_attempts != 1
            or profile.costs.allow_paid or profile.costs.allow_cloud_uploads
            or profile.costs.max_usd != 0):
        raise ValueError("inspector requires single-attempt, local-only profile")
    _base_url(profile.generation)  # Safety boundary check only, NO request.
    opts = profile.generation.options
    graph, sha = _graph(workflows_root, opts.get("workflow"))
    seed_field = opts.get("seed_input", "seed")
    if not isinstance(seed_field, str) or not _NODE_ID.fullmatch(seed_field):
        raise ValueError("seed_input must be an explicit safe input name")
    candidates = {
        "prompt_node": _candidates(graph, ("text",)),
        "seed_node": _candidates(graph, (seed_field,)),
        "size_node": _candidates(graph, ("width", "height")),
        "output_node": _candidates(graph, (), saved_image=True),
    }
    required = {
        "prompt_node": ("text",),
        "seed_node": (seed_field,),
        "size_node": ("width", "height"),
        "output_node": (),
    }
    errors = []
    mapped: dict[str, str | None] = {}
    for option in _KEYS:
        chosen = opts.get(option)
        if not isinstance(chosen, (str, int)) or isinstance(chosen, bool):
            errors.append(f"{option}: explicit node ID required")
            mapped[option] = None
            continue
        chosen = str(chosen)
        mapped[option] = chosen
        node = graph.get(chosen)
        if not isinstance(node, dict):
            errors.append(f"{option}: node ID does not exist")
            continue
        if not all(field in node["inputs"] for field in required[option]):
            errors.append(f"{option}: mapped node lacks required inputs")
        if option == "output_node" and "SaveImage" not in node["class_type"]:
            errors.append("output_node: mapped node is not a SaveImage node")
    return {
        "schema_version": 1,
        "status": "static_mapping_valid" if not errors else "blocked",
        "batch_id": manifest.id,
        "asset_count": len(manifest.assets),
        "workflow_file": opts["workflow"],
        "workflow_sha256": sha,
        "graph_node_count": len(graph),
        "mapped_node_ids": mapped,
        "candidate_node_ids": candidates,
        "errors": errors,
        "read_only": True,
        "provider_calls": 0,
        "gpu_operations": 0,
        "weights_downloaded": False,
        "execution_ready": False,
        "model_rights_checked": False,
        "model_file_bytes_verified": False,
        "live_comfyui_node_compatibility_checked": False,
        "recommended_next_step": (
            "Verify local model licence and model/graph byte hashes; "
            "independently approve a hardware-safe generation trial. "
            "Static mapping alone does not authorize inference."
        ),
    }
