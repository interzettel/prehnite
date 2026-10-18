"""Reusable cutout quality/refinement contracts.

The existing Engine owns reviewed-source validation, local segmentation,
journaling, recovery and no-retry behavior. This module owns only the
post-segmentation step: configurable CPU alpha candidates, technical QA,
stage-separated evidence and explicit acceptance records.

No model is loaded, no network is contacted and no candidate is accepted
without an explicit reviewer decision.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Literal

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .images import _mask_alpha, sha256
from .schema import relative_name

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[a-z][a-z0-9_-]{0,47}$")
_MAX_RECIPE_BYTES = 128 * 1024
_STAGES = (
    "resource_readiness",
    "dependency_compatibility",
    "technical_execution",
    "segmentation_validity",
    "alpha_quality",
    "visual_acceptance",
    "owner_final_acceptance",
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _sha(value: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError("Expected lowercase SHA256")
    return value


class SourceDefinition(Strict):
    name: str = Field(min_length=1, max_length=160)
    sha256: str

    _check_sha = field_validator("sha256")(classmethod(lambda cls, v: _sha(v)))


class TargetDefinition(Strict):
    id: str
    phrase: str = Field(min_length=2, max_length=160)
    include: list[str] = Field(min_length=1, max_length=12)
    exclude: list[str] = Field(min_length=1, max_length=12)

    @field_validator("id")
    @classmethod
    def check_id(cls, value: str) -> str:
        if not _ID.fullmatch(value):
            raise ValueError("Target ID must be a stable lowercase identifier")
        return value

    @model_validator(mode="after")
    def validate_terms(self) -> TargetDefinition:
        terms = self.include + self.exclude
        if any(not term.strip() or len(term) > 120 for term in terms):
            raise ValueError("Include/exclude terms must be nonempty and bounded")
        if len({term.casefold() for term in terms}) != len(terms):
            raise ValueError("Include/exclude terms cannot overlap or repeat")
        if self.phrase != self.phrase.strip():
            raise ValueError("Target phrase must be trimmed")
        return self


class WorkflowBinding(Strict):
    path: str
    sha256: str
    input_node: str
    target_node: str
    target_input: Literal["text", "prompt", "value"]
    output_node: str

    _sha_check = field_validator("sha256")(classmethod(lambda cls, v: _sha(v)))

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        return relative_name(value)

    @field_validator("input_node", "target_node", "output_node")
    @classmethod
    def safe_node(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", value):
            raise ValueError("Workflow node ID is invalid")
        return value


class ModelBinding(Strict):
    role: str
    path: str
    sha256: str

    _sha_check = field_validator("sha256")(classmethod(lambda cls, v: _sha(v)))

    @field_validator("role")
    @classmethod
    def safe_role(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", value):
            raise ValueError("Model role is invalid")
        return value

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        return relative_name(value)


class AlphaCandidateSpec(Strict):
    id: str
    sigma_px: float = Field(gt=0.1, le=3.0)
    # Decontamination is deliberately mandatory: feathering without
    # foreground RGB expansion can reintroduce background colors.
    decontaminate: Literal[True] = True
    preserve_core_px: int = Field(default=1, ge=0, le=4)

    @field_validator("id")
    @classmethod
    def check_id(cls, value: str) -> str:
        if not _ID.fullmatch(value):
            raise ValueError("Alpha candidate ID must be a stable lowercase identifier")
        return value


class QAPolicy(Strict):
    min_hard_iou: float = Field(default=0.995, ge=0, le=1)
    max_removed_fraction: float = Field(default=0.01, ge=0, le=1)
    max_added_fraction: float = Field(default=0.02, ge=0, le=1)
    max_coverage_delta: float = Field(default=0.002, ge=0, le=1)
    max_partial_alpha_fraction: float = Field(default=0.02, ge=0, le=1)
    max_narrow_width_delta_px: int = Field(default=1, ge=0, le=8)


class CutoutRecipe(Strict):
    schema_version: Literal[1] = 1
    source: SourceDefinition
    target: TargetDefinition
    workflow: WorkflowBinding
    models: list[ModelBinding] = Field(min_length=1, max_length=16)
    alpha_candidates: list[AlphaCandidateSpec] = Field(min_length=1, max_length=4)
    qa: QAPolicy = Field(default_factory=QAPolicy)

    @model_validator(mode="after")
    def unique(self) -> CutoutRecipe:
        if len({row.id for row in self.alpha_candidates}) != len(self.alpha_candidates):
            raise ValueError("Alpha candidate IDs must be unique")
        if len({row.role for row in self.models}) != len(self.models):
            raise ValueError("Model binding roles must be unique")
        return self


class StageResult(Strict):
    status: Literal["not_run", "passed", "failed", "needs_review", "blocked",
                    "unverified"]
    reason: str = Field(default="", max_length=500)
    evidence_sha256: str | None = None

    @field_validator("evidence_sha256")
    @classmethod
    def check_evidence(cls, value: str | None) -> str | None:
        return _sha(value) if value is not None else value


class FileIntegrity(Strict):
    """Plain local byte-integrity assertion, not model compatibility."""
    status: Literal["passed"] = "passed"
    source_sha256: str
    workflow_sha256: str
    model_sha256: dict[str, str]


class ResourceObservation(Strict):
    """Versioned view of PR #159's observation-only readiness report."""
    schema_version: Literal[1]
    kind: Literal["resource_readiness_observation"]
    observation_status: Literal["pass", "blocked", "unknown"]
    startup_authorized: Literal[False]
    model_compatibility: str
    technical_execution: str
    visual_acceptance: str
    observation_sha256: str


class CandidateResult(Strict):
    id: str
    path: str
    sha256: str
    status: Literal["passed", "rejected"]
    metrics: dict
    rejection_reasons: list[str] = Field(default_factory=list)
    review_status: Literal["review_pending"] = "review_pending"


class CutoutQualityReport(Strict):
    schema_version: Literal[1] = 1
    recipe_sha256: str
    source_sha256: str
    mask_sha256: str
    target: TargetDefinition
    workflow_sha256: str
    file_integrity: FileIntegrity
    resource_observation: ResourceObservation | None = None
    stages: dict[str, StageResult]
    candidates: list[CandidateResult]
    recommended_candidate: str | None = None
    visual_acceptance: Literal["not_recorded"] = "not_recorded"
    owner_final_acceptance: Literal["not_recorded"] = "not_recorded"

    @model_validator(mode="after")
    def seven_stages(self) -> CutoutQualityReport:
        if set(self.stages) != set(_STAGES):
            raise ValueError("Cutout report must contain all seven separate stages")
        return self


class CutoutContractError(ValueError):
    """Refuse invalid recipe, provenance, geometry or unsafe acceptance."""


def load_recipe(path: Path) -> CutoutRecipe:
    if path.is_symlink() or path.suffix.lower() != ".json" or not path.is_file():
        raise CutoutContractError("Recipe must be a regular local JSON file")
    if path.stat().st_size <= 0 or path.stat().st_size > _MAX_RECIPE_BYTES:
        raise CutoutContractError("Recipe size is invalid")

    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CutoutContractError(f"Duplicate recipe key: {key}")
            result[key] = value
        return result

    try:
        document = json.loads(path.read_text(encoding="utf-8"),
                              object_pairs_hook=reject_duplicates)
    except UnicodeError as exc:
        raise CutoutContractError("Recipe must be UTF-8") from exc
    return CutoutRecipe.model_validate(document)


def recipe_sha256(recipe: CutoutRecipe) -> str:
    payload = json.dumps(recipe.model_dump(mode="json"), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _checked_relative(root: Path, relative: str, expected: str, label: str) -> Path:
    root = root.resolve(strict=True)
    path = (root / relative_name(relative)).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise CutoutContractError(f"{label} file is missing or outside root")
    if sha256(path) != expected:
        raise CutoutContractError(f"{label} SHA256 mismatch")
    return path


def verify_bindings(recipe: CutoutRecipe, *, source: Path, workflow_root: Path,
                    models_root: Path) -> dict[str, Path]:
    """Verify source, workflow graph bindings and declared model bytes."""
    if not source.is_file() or source.is_symlink():
        raise CutoutContractError("Source must be a regular local file")
    if sha256(source) != recipe.source.sha256:
        raise CutoutContractError("Source SHA256 mismatch")
    workflow = _checked_relative(workflow_root, recipe.workflow.path,
                                 recipe.workflow.sha256, "Workflow")
    try:
        graph = json.loads(workflow.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CutoutContractError("Workflow is not valid JSON") from exc
    if not isinstance(graph, dict):
        raise CutoutContractError("Workflow must be an API graph object")
    for node, label, key in (
        (recipe.workflow.input_node, "input_node", "image"),
        (recipe.workflow.target_node, "target_node", recipe.workflow.target_input),
        (recipe.workflow.output_node, "output_node", "images"),
    ):
        entry = graph.get(node)
        if not isinstance(entry, dict):
            raise CutoutContractError(f"Workflow {label} is missing")
        inputs = entry.get("inputs")
        if not isinstance(inputs, dict) or key not in inputs:
            raise CutoutContractError(f"Workflow {label} lacks input '{key}'")
    models = {
        row.role: _checked_relative(models_root, row.path, row.sha256, f"Model {row.role}")
        for row in recipe.models
    }
    return {"workflow": workflow, "models": models}


def _hard_alpha(alpha: Image.Image) -> Image.Image:
    return alpha.point(lambda value: 255 if value > 127 else 0)


def _count_components_and_holes(mask: Image.Image) -> tuple[int, int, int]:
    """Return (foreground components, hole components, hole pixels).

    Detection is intentionally 4-connected (Pillow flood fill). All four
    borders seed the exterior background, so a foreground object touching one
    corner cannot hide a separate border-connected background region.
    """
    work = mask.copy()
    pixels = work.load()
    width, height = work.size
    components = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == 255:
                ImageDraw.floodfill(work, (x, y), 128, thresh=0)
                components += 1

    exterior = ImageOps.invert(mask)
    pixels = exterior.load()
    border = []
    for x in range(width):
        border.extend(((x, 0), (x, height - 1)))
    for y in range(1, height - 1):
        border.extend(((0, y), (width - 1, y)))
    for x, y in border:
        if pixels[x, y] == 255:
            ImageDraw.floodfill(exterior, (x, y), 128, thresh=0)
    hole_pixels = sum(1 for value in exterior.tobytes() if value == 255)
    hole_components = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == 255:
                ImageDraw.floodfill(exterior, (x, y), 128, thresh=0)
                hole_components += 1
    return components, hole_components, hole_pixels


def _border_fraction(mask: Image.Image) -> float:
    width, height = mask.size
    values = bytearray()
    for box in ((0, 0, width, 1), (0, height - 1, width, height),
                (0, 0, 1, height), (width - 1, 0, width, height)):
        values.extend(mask.crop(box).tobytes())
    return sum(1 for value in values if value > 127) / max(1, len(values))


def _fill_foreground_rgb(rgba: Image.Image, hard: Image.Image, radius: int) -> Image.Image:
    """Expand nearest opaque RGB into transparent/fringe pixels.

    Background-colored transparent pixels must never become visible simply
    because alpha is softened. Pixels inside the foreground keep their source
    RGB; only the transparent fringe is replaced.
    """
    rgb = rgba.convert("RGB")
    known = hard.copy()
    filled = rgb.copy()
    for _ in range(max(1, radius)):
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            shifted_rgb = Image.new("RGB", filled.size)
            shifted_rgb.paste(filled, (dx, dy))
            shifted_known = Image.new("L", filled.size, 0)
            shifted_known.paste(known, (dx, dy))
            take = ImageChops.multiply(shifted_known, ImageOps.invert(known))
            if take.getbbox():
                filled.paste(shifted_rgb, (0, 0), take)
                known = ImageChops.lighter(known, take)
    # Remaining far-away transparent RGB is invisible at alpha=0, but must
    # still not retain arbitrary background bytes. Use the mean foreground.
    unknown = ImageOps.invert(known)
    if unknown.getbbox():
        mean = ImageStat.Stat(filled, hard).mean
        filled.paste(tuple(round(value) for value in mean), mask=unknown)
    return filled


def _alpha_metrics(alpha: Image.Image, original: Image.Image,
                   operation: dict | None = None) -> dict:
    hard = _hard_alpha(alpha)
    orig = _hard_alpha(original)
    hard_bytes = hard.tobytes()
    orig_bytes = orig.tobytes()
    intersect = sum(1 for a, b in zip(hard_bytes, orig_bytes) if a and b)
    union = sum(1 for a, b in zip(hard_bytes, orig_bytes) if a or b)
    added = sum(1 for a, b in zip(hard_bytes, orig_bytes) if a and not b)
    removed = sum(1 for a, b in zip(hard_bytes, orig_bytes) if b and not a)
    orig_count = max(1, sum(1 for value in orig_bytes if value))
    bbox = hard.getbbox()
    original_bbox = orig.getbbox()
    components, hole_components, hole_pixels = _count_components_and_holes(hard)
    original_components, original_hole_components, original_hole_pixels = (
        _count_components_and_holes(orig))
    partial = sum(1 for value in alpha.tobytes() if 0 < value < 255)
    width = alpha.width
    # Narrow-structure check: row widths at the bbox quartiles.
    width_delta = 0
    if bbox and original_bbox:
        y0, y1 = bbox[1], bbox[3]
        for fraction in (0.35, 0.5, 0.65):
            row = min(y1 - 1, max(y0, int(y0 + (y1 - y0) * fraction)))
            def row_width(mask: Image.Image, scan_row: int = row) -> int:
                span = mask.crop((0, scan_row, width, scan_row + 1)).getbbox()
                return (span[2] - span[0]) if span else 0
            width_delta = max(width_delta, abs(row_width(hard) - row_width(orig)))
    histogram = alpha.histogram()
    coverage = sum(index * count for index, count in enumerate(histogram)) / (
        255 * max(1, alpha.width * alpha.height))
    return {
        "alpha_coverage": round(coverage, 6),
        "hard_iou": round(intersect / union if union else 1.0, 6),
        "added_pixels": added,
        "removed_pixels": removed,
        "removed_fraction": round(removed / orig_count, 6),
        "added_fraction": round(added / orig_count, 6),
        "coverage_delta": round(abs(coverage - (
            sum(index * count for index, count in enumerate(orig.histogram())) / (
                255 * max(1, orig.width * orig.height)))), 6),
        "bbox_xyxy": list(bbox) if bbox else [],
        "components": components,
        "original_components": original_components,
        "hole_components": hole_components,
        "original_hole_components": original_hole_components,
        "hole_pixels": hole_pixels,
        "original_hole_pixels": original_hole_pixels,
        "partial_alpha_pixels": partial,
        "partial_alpha_fraction": round(partial / max(1, alpha.width * alpha.height), 6),
        "max_narrow_width_delta_px": width_delta,
        "alpha_unique_count": len([count for count in histogram if count]),
        "alpha_min": next(index for index, count in enumerate(histogram) if count),
        "alpha_max": max(index for index, count in enumerate(histogram) if count),
        **(operation or {}),
    }


def _candidate_image(source: Image.Image, mask: Image.Image, spec: AlphaCandidateSpec
                     ) -> tuple[Image.Image, Image.Image, dict]:
    alpha = _mask_alpha(mask, source.size)
    hard = _hard_alpha(alpha)
    filtered = hard.filter(ImageFilter.GaussianBlur(radius=spec.sigma_px))
    core = hard.filter(ImageFilter.MinFilter(size=2 * spec.preserve_core_px + 1))
    candidate_alpha = Image.composite(Image.new("L", alpha.size, 255), filtered, core)
    candidate_alpha = candidate_alpha.point(lambda value: 0 if value < 2 else value)
    radius = max(1, math.ceil(spec.sigma_px * 3) + 1)
    source_rgba = source.convert("RGBA")
    filled = _fill_foreground_rgb(source_rgba, hard, radius)
    # Operation evidence only: count pixels whose RGB was expanded from the
    # nearest opaque foreground. This is not a halo/visual-quality claim.
    original_rgb = source_rgba.convert("RGB")
    expanded_rgb = filled.convert("RGB")
    replaced = ImageChops.difference(original_rgb, expanded_rgb).convert("L")
    replaced_pixels = sum(1 for value in replaced.tobytes() if value)
    operation = {
        "foreground_rgb_expansion_applied": True,
        "foreground_rgb_expansion_radius_px": radius,
        "transparent_rgb_replaced_pixels": replaced_pixels,
    }
    candidate = expanded_rgb.convert("RGBA")
    candidate.putalpha(candidate_alpha)
    return candidate, alpha, operation


def _save_png_atomic(image: Image.Image, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    if temporary.exists():
        temporary.unlink()
    image.save(temporary, format="PNG", optimize=True)
    temporary.replace(destination)


def _stage(status: str, reason: str = "", evidence: str | None = None) -> StageResult:
    return StageResult(status=status, reason=reason, evidence_sha256=evidence)


def _file_integrity(recipe: CutoutRecipe, source: Path,
                    bindings: dict[str, Path]) -> FileIntegrity:
    return FileIntegrity(
        source_sha256=sha256(source),
        workflow_sha256=sha256(bindings["workflow"]),
        model_sha256={role: sha256(path) for role, path in bindings["models"].items()},
    )


def _resource_evidence(path: Path | None) -> tuple[StageResult,
                                                    ResourceObservation | None]:
    if path is None:
        return (_stage("not_run", "caller_did_not_supply_readiness_evidence"), None)
    if path.is_symlink() or not path.is_file():
        raise CutoutContractError("Resource observation must be a regular file")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CutoutContractError("Resource observation is not valid UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise CutoutContractError("Resource observation must be an object")
    if (document.get("schema_version") != 1
            or document.get("kind") != "resource_readiness_observation"):
        raise CutoutContractError("Unsupported resource observation schema")
    if document.get("startup_authorized") is not False:
        raise CutoutContractError("Passing resource observation must not authorize startup")
    status = document.get("status")
    if status not in ("pass", "blocked", "unknown"):
        raise CutoutContractError("Unsupported resource observation status")
    model_compatibility = document.get("model_compatibility")
    technical_execution = document.get("technical_execution")
    visual_acceptance = document.get("visual_acceptance")
    if not all(isinstance(value, str) and value
               for value in (model_compatibility, technical_execution, visual_acceptance)):
        raise CutoutContractError("Resource observation must preserve unverified stage fields")
    observation = ResourceObservation(
        schema_version=1,
        kind="resource_readiness_observation",
        observation_status=status,
        startup_authorized=False,
        model_compatibility=model_compatibility,
        technical_execution=technical_execution,
        visual_acceptance=visual_acceptance,
        observation_sha256=sha256(path),
    )
    if status == "pass":
        stage = _stage("passed", "resource_observation_pass_not_startup_authorization",
                       observation.observation_sha256)
    elif status == "blocked":
        stage = _stage("blocked", "resource_observation_blocked",
                       observation.observation_sha256)
    else:
        stage = _stage("unverified", "resource_observation_unknown",
                       observation.observation_sha256)
    return stage, observation


def run_cutout_qa(recipe_path: Path, *, source: Path, mask: Path,
                  workflow_root: Path, models_root: Path, output_dir: Path,
                  resource_readiness: Path | None = None) -> Path:
    """Generate declared alpha candidates and a seven-stage report.

    No candidate receives visual acceptance. The command is deterministic and
    writes only into a new/explicit output directory.
    """
    recipe = load_recipe(recipe_path)
    if _sha256_file_if_exists(mask) is None:
        raise CutoutContractError("Mask is missing")
    bindings = verify_bindings(recipe, source=source, workflow_root=workflow_root,
                               models_root=models_root)
    integrity = _file_integrity(recipe, source, bindings)
    resource, resource_observation = _resource_evidence(resource_readiness)
    mask_path = mask.resolve(strict=True)
    with Image.open(source) as source_image:
        source_rgba = ImageOps.exif_transpose(source_image).convert("RGBA").copy()
    try:
        with Image.open(mask_path) as mask_image:
            alpha = _mask_alpha(mask_image, source_rgba.size)
    except ValueError as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        report = CutoutQualityReport(
            recipe_sha256=recipe_sha256(recipe),
            source_sha256=sha256(source),
            mask_sha256=sha256(mask_path),
            target=recipe.target,
            workflow_sha256=sha256(bindings["workflow"]),
            file_integrity=integrity,
            resource_observation=resource_observation,
            stages={
                "resource_readiness": resource,
                "dependency_compatibility": _stage(
                    "unverified", "file_integrity_verified_runtime_compatibility_unverified"),
                "technical_execution": _stage("failed", f"mask_decode_failed: {exc}"),
                "segmentation_validity": _stage("failed", f"mask_geometry_invalid: {exc}"),
                "alpha_quality": _stage("blocked", "no_geometry_valid_mask"),
                "visual_acceptance": _stage("not_run", "independent_visual_review_required"),
                "owner_final_acceptance": _stage("not_run", "owner_authorization_required"),
            },
            candidates=[],
            recommended_candidate=None,
        )
        destination = output_dir / "cutout-quality.json"
        _write_json_exclusive(destination, report.model_dump(mode="json"))
        return destination
    hard = _hard_alpha(alpha)
    hard_count = sum(1 for value in hard.tobytes() if value)
    border = _border_fraction(hard)
    components, _, _ = _count_components_and_holes(hard)
    if hard_count == 0:
        segmentation = _stage("failed", "empty_mask")
    elif hard_count == hard.width * hard.height:
        segmentation = _stage("failed", "entire_frame_mask")
    elif border > 0.75 and hard_count > hard.width * hard.height * 0.5:
        segmentation = _stage("failed", "suspected_inverted_mask")
    elif components != 1:
        segmentation = _stage("needs_review", "multiple_disconnected_components")
    else:
        segmentation = _stage("passed", "supplied_mask_geometry_checked_not_execution_provenance")

    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise CutoutContractError("QA output directory must be new or empty")
    candidates: list[CandidateResult] = []
    if segmentation.status == "passed":
        mask_image = Image.open(mask_path)
        for spec in recipe.alpha_candidates:
            candidate, _, operation = _candidate_image(source_rgba, mask_image, spec)
            destination = output_dir / f"{spec.id}.png"
            _save_png_atomic(candidate, destination)
            metrics = _alpha_metrics(candidate.getchannel("A"), alpha, operation)
            reasons = []
            if metrics["hard_iou"] < recipe.qa.min_hard_iou:
                reasons.append("hard_silhouette_iou_below_threshold")
            if metrics["removed_fraction"] > recipe.qa.max_removed_fraction:
                reasons.append("removed_fraction_above_threshold")
            if metrics["added_fraction"] > recipe.qa.max_added_fraction:
                reasons.append("added_fraction_above_threshold")
            if metrics["coverage_delta"] > recipe.qa.max_coverage_delta:
                reasons.append("coverage_change_above_threshold")
            if metrics["components"] != metrics["original_components"]:
                reasons.append("connected_component_change")
            if metrics["hole_components"] != metrics["original_hole_components"]:
                reasons.append("hole_component_change")
            if metrics["max_narrow_width_delta_px"] > recipe.qa.max_narrow_width_delta_px:
                reasons.append("narrow_structure_width_change")
            if metrics["partial_alpha_fraction"] > recipe.qa.max_partial_alpha_fraction:
                reasons.append("excessive_feathering")
            status = "passed" if not reasons else "rejected"
            candidates.append(CandidateResult(
                id=spec.id, path=str(destination), sha256=sha256(destination),
                status=status, metrics=metrics, rejection_reasons=reasons,
            ))
        mask_image.close()

    passed = [row.id for row in candidates if row.status == "passed"]
    alpha_quality = _stage(
        "passed" if passed else "failed",
        "candidate_passed_technical_qa" if passed else "no_candidate_passed_technical_qa",
    )
    dependency = _stage(
        "unverified", "file_integrity_verified_runtime_compatibility_unverified")
    technical = _stage(
        "unverified", "supplied_mask_is_not_a_bound_execution_receipt")
    stages = {
        "resource_readiness": resource,
        "dependency_compatibility": dependency,
        "technical_execution": technical,
        "segmentation_validity": segmentation,
        "alpha_quality": alpha_quality,
        "visual_acceptance": _stage("not_run", "independent_visual_review_required"),
        "owner_final_acceptance": _stage("not_run", "owner_authorization_required"),
    }
    recommended = passed[0] if passed else None
    report = CutoutQualityReport(
        recipe_sha256=recipe_sha256(recipe),
        source_sha256=sha256(source),
        mask_sha256=sha256(mask_path),
        target=recipe.target,
        workflow_sha256=sha256(bindings["workflow"]),
        file_integrity=integrity,
        resource_observation=resource_observation,
        stages=stages,
        candidates=candidates,
        recommended_candidate=recommended,
    )
    destination = output_dir / "cutout-quality.json"
    _write_json_exclusive(destination, report.model_dump(mode="json"))
    return destination


def _sha256_file_if_exists(path: Path) -> str | None:
    return sha256(path) if path.is_file() and not path.is_symlink() else None


def _write_json_exclusive(path: Path, payload: dict) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError("QA report already exists; will not overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    temporary.replace(path)


def create_acceptance_record(*, quality_report: Path, candidate_id: str,
                             reviewer: str, decision: Literal["accepted", "rejected"],
                             scope: str, evidence: list[Path], output: Path) -> dict:
    """Create one explicit, create-only visual acceptance record.

    This records an independent review decision; it does not establish owner
    final acceptance, model rights or a production certification.
    """
    if not reviewer.strip() or len(reviewer) > 160:
        raise CutoutContractError("Reviewer must be nonempty and bounded")
    if not scope.strip() or len(scope) > 800:
        raise CutoutContractError("Review scope must be nonempty and bounded")
    if decision == "accepted" and not evidence:
        raise CutoutContractError("Accepted review requires at least one evidence file")
    report = json.loads(quality_report.read_text(encoding="utf-8"))
    rows = [row for row in report.get("candidates", []) if row.get("id") == candidate_id]
    if len(rows) != 1:
        raise CutoutContractError("Candidate is not uniquely present in quality report")
    candidate = rows[0]
    if decision == "accepted" and candidate.get("status") != "passed":
        raise CutoutContractError("Rejected technical candidate cannot be accepted")
    alpha_status = report.get("stages", {}).get("alpha_quality", {}).get("status")
    if decision == "accepted" and alpha_status != "passed":
        raise CutoutContractError("Candidate cannot be accepted unless alpha QA passed")
    candidate_path = Path(candidate["path"]).resolve(strict=True)
    if sha256(candidate_path) != candidate["sha256"]:
        raise CutoutContractError("Candidate bytes changed since QA")
    evidence_items = []
    for path in evidence:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise CutoutContractError("Acceptance evidence is not a file")
        evidence_items.append({"path": str(resolved), "sha256": sha256(resolved)})
    if output.exists() or output.is_symlink():
        raise FileExistsError("Acceptance record already exists; will not overwrite")
    record = {
        "schema_version": 1,
        "decision": decision,
        "reviewer": reviewer.strip(),
        "scope": scope.strip(),
        "candidate_id": candidate["id"],
        "candidate_sha256": candidate["sha256"],
        "candidate_path": str(candidate_path),
        "quality_report": str(quality_report.resolve(strict=True)),
        "quality_report_sha256": sha256(quality_report),
        "source_sha256": report["source_sha256"],
        "mask_sha256": report["mask_sha256"],
        "recipe_sha256": report["recipe_sha256"],
        "stages": {
            "visual_acceptance": {"status": "passed" if decision == "accepted" else "failed",
                                  "reviewer": reviewer.strip()},
            "owner_final_acceptance": {"status": "not_recorded"},
        },
        "review_pending": decision != "accepted",
        "evidence": evidence_items,
        "note": "Independent visual review only; owner final acceptance is separate.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return record
