"""Read-only local model/ComfyUI graph resolution for blueprint-only micro recipes.

Never calls ComfyUI, downloads weights, approves rights or makes a recipe executable.
A resolved-input receipt is NOT yet a journal-bound runnable recipe.
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .recipes import Recipe, recipe_sha256
from .schema import relative_name

_SHA = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+/-]{1,126}$")
_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".gguf", ".bin"}
_MAX_BINDINGS = 128 * 1024
_MAX_GRAPH = 4 * 1024 * 1024


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LocalStage(Strict):
    workflow: str = Field(min_length=5, max_length=260)
    workflow_sha256: str
    checkpoint: str = Field(min_length=5, max_length=260)
    checkpoint_sha256: str
    model_revision: str = Field(min_length=2, max_length=127)
    model_terms_url: str = Field(min_length=12, max_length=600)
    acknowledged_terms_for_local_use: Literal[True]

    @model_validator(mode="after")
    def validate_claims(self) -> "LocalStage":
        for digest in (self.workflow_sha256, self.checkpoint_sha256):
            if not _SHA.fullmatch(digest):
                raise ValueError("Expected lowercase SHA256 for each local file")
        if not _REVISION.fullmatch(self.model_revision):
            raise ValueError("Invalid model revision label")
        for name in (self.workflow, self.checkpoint):
            if relative_name(name) != name:
                raise ValueError("Unsafe noncanonical local path")
        if not self.workflow.lower().endswith(".json"):
            raise ValueError("Workflow must be a ComfyUI API-format JSON file")
        if Path(self.checkpoint).suffix.lower() not in _EXTENSIONS:
            raise ValueError("Unknown checkpoint file extension")
        url = urlsplit(self.model_terms_url)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.hostname.lower() in (
                    "localhost", "127.0.0.1", "::1")):
            raise ValueError("Model terms must be a plain public HTTPS URL")
        return self


class LocalBindings(Strict):
    schema_version: Literal[1]
    recipe_sha256: str
    stages: dict[str, LocalStage] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_identity(self) -> "LocalBindings":
        if not _SHA.fullmatch(self.recipe_sha256):
            raise ValueError("Bindings require canonical recipe SHA256")
        return self


def _json_document(path: Path, limit: int) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected regular JSON file, not a symlink")
    size = path.stat().st_size
    if size <= 0 or size > limit:
        raise ValueError("JSON file outside accepted byte bounds")

    def unique(pairs: list[tuple[str, object]]) -> dict:
        result: dict = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("Duplicate JSON key")
            result[name] = value
        return result

    document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              ValueError("Nonfinite JSON value")))
    if not isinstance(document, dict):
        raise ValueError("JSON document must be an object")
    return document


def load_local_bindings(path: Path) -> LocalBindings:
    return LocalBindings.model_validate(_json_document(path, _MAX_BINDINGS))


def _local_file(root: Path, relative: str) -> Path:
    """Prevent traversal and symlinks, including intermediate path components."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Approved local root must be a real directory")
    if relative_name(relative) != relative:
        raise ValueError("Invalid local relative path")
    target = root
    for component in relative.split("/"):
        target = target / component
        if target.is_symlink():
            raise ValueError("Symlinked local model/workflow paths are forbidden")
    resolved_root = root.resolve(strict=True)
    resolved_target = target.resolve(strict=True)
    if not resolved_target.is_relative_to(resolved_root):
        raise ValueError("Path escaped approved root")
    if not stat.S_ISREG(resolved_target.stat().st_mode):
        raise ValueError("Input must be a regular file")
    return resolved_target


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _validate_graph(path: Path) -> None:
    graph = _json_document(path, _MAX_GRAPH)
    if not graph or len(graph) > 512:
        raise ValueError("ComfyUI API graph needs 1-512 nodes")
    for key, node in graph.items():
        if not isinstance(key, str) or not key.isdecimal() or not isinstance(node, dict):
            raise ValueError("Expected ComfyUI API graph keyed by numeric node IDs")
        if not isinstance(node.get("class_type"), str) or not node["class_type"]:
            raise ValueError("ComfyUI graph node lacks class_type")
        if not isinstance(node.get("inputs"), dict):
            raise ValueError("ComfyUI graph node lacks inputs")
    # Static shape checks cannot establish that a remote/local ComfyUI runtime
    # has those nodes, compatible weights, or a meaningful output.


def resolve_local_micro(recipe: Recipe, bindings: LocalBindings,
                        workflows_root: Path, checkpoints_root: Path) -> dict:
    """Verify explicit owner-supplied bytes; return non-executable receipt."""
    if recipe.kind != "micro" or recipe.release_status != "blueprint_only":
        raise ValueError("Offline resolver supports only micro blueprint previews")
    if bindings.recipe_sha256 != recipe_sha256(recipe):
        raise ValueError("Recipe fingerprint changed since owner bindings were captured")
    external = {s.id: s for s in recipe.stages if s.model.provider != "demo"}
    if set(bindings.stages) != set(external):
        raise ValueError("Bindings must match every and only external recipe stage")
    resolved = []
    for stage in recipe.stages:
        if stage.model.provider == "demo":
            continue
        if (stage.execution != "local" or stage.model.provider != "comfyui"
                or stage.model.pin_status != "unresolved"):
            raise ValueError("Only unresolved, local ComfyUI stages can be resolved")
        binding = bindings.stages[stage.id]
        graph_path = _local_file(workflows_root, binding.workflow)
        weight_path = _local_file(checkpoints_root, binding.checkpoint)
        if _sha256_file(graph_path) != binding.workflow_sha256:
            raise ValueError(f"Workflow SHA256 mismatch at stage {stage.id}")
        if _sha256_file(weight_path) != binding.checkpoint_sha256:
            raise ValueError(f"Checkpoint SHA256 mismatch at stage {stage.id}")
        _validate_graph(graph_path)
        resolved.append({
            "stage_id": stage.id, "provider": stage.model.provider,
            "model": stage.model.model, "declared_model_revision": binding.model_revision,
            "workflow_sha256": binding.workflow_sha256,
            "checkpoint_sha256": binding.checkpoint_sha256,
            "model_terms_url": binding.model_terms_url,
            "operator_acknowledged_terms": True,
            "rights_verified_by_prehnite": False,
            "comfyui_graph_shape_checked": True,
        })
    frozen = {"recipe_id": recipe.id, "recipe_version": recipe.version,
              "recipe_sha256": recipe_sha256(recipe), "external_stage_inputs": resolved}
    canonical = json.dumps(frozen, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        "schema_version": 1, **frozen,
        "resolved_inputs_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "status": "offline_files_verified",
        "hardware_suitability_verified": False,
        "comfyui_runtime_verified": False,
        "local_model_executable": False,
        "recipe_journal_pinning_implemented": False,
        "provider_calls_or_downloads": False,
        "cloud_spend_authorized": False,
        "third_party_license_approved": False,
    }
