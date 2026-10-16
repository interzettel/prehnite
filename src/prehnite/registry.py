"""Offline capability contracts. No provider price or model license is bundled.

This registry describes Prehnite's *implemented adapter* capabilities,
not a guarantee that a third-party endpoint is currently available.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .schema import Endpoint, Manifest, Profile

ASPECTS = ("9:16", "3:4", "4:3", "16:9", "1:1")
TIERS = ("2k", "4k")
KLEIN_2K_DIMENSIONS = {
    "9:16": (1152, 2048), "3:4": (1536, 2048),
    "4:3": (2048, 1536), "16:9": (2048, 1152),
    "1:1": (2048, 2048),
}
ESRGAN_MODELS = (
    "RealESRGAN_x4plus", "RealESRGAN_x2plus",
    "RealESRGAN_x4plus_anime_6B", "RealESRGAN_x4_v3",
    "RealESRGAN_x4_wdn_v3", "RealESRGAN_x4_anime_v3",
)


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    model: str
    capability: Literal["generate", "upscale", "segment", "judge", "matte"]
    paid: bool
    description: str
    input_kind: Literal["prompt", "image", "image_and_text", "image_pair"]
    output_formats: tuple[str, ...] = ("png",)
    aspect_ratios: tuple[str, ...] = ()
    resolution_tiers: tuple[str, ...] = ()
    max_output_side: int | None = None
    uploads_source: bool = False
    supported_options: tuple[str, ...] = ()
    schema_url: str | None = None
    licensing: str = "Review third-party terms before use."
    price_status: str = "not_in_registry"
    adapter_status: str = "offline_contract_only"


MODELS = (
    ModelInfo("fal", "blackforestlabs/flux-3/klein/text-to-image",
              "generate", True, "FLUX.3 Klein, explicit width/height",
              "prompt", aspect_ratios=ASPECTS, resolution_tiers=TIERS,
              max_output_side=4096, supported_options=("enable_prompt_expansion",),
              schema_url="https://fal.ai/models/blackforestlabs/flux-3/klein/text-to-image",
              price_status="user_estimate_required"),
    ModelInfo("fal", "blackforestlabs/flux-3/text-to-image",
              "generate", True, "FLUX.3 Image, aspect ratio and resolution tier",
              "prompt", aspect_ratios=ASPECTS, resolution_tiers=TIERS,
              supported_options=("enable_prompt_expansion",),
              schema_url="https://fal.ai/models/blackforestlabs/flux-3/text-to-image/api",
              price_status="user_estimate_required"),
    ModelInfo("fal", "fal-ai/esrgan", "upscale", True, "2x image super-resolution",
              "image", supported_options=("model", "scale"), uploads_source=True,
              schema_url="https://fal.ai/models/fal-ai/esrgan/api",
              price_status="user_estimate_required"),
    ModelInfo("fal", "fal-ai/sam-3-1/image", "segment", True,
              "One text-prompted PNG mask, no multi-object disambiguation",
              "image_and_text", uploads_source=True,
              schema_url="https://fal.ai/models/fal-ai/sam-3-1/image/api",
              price_status="user_estimate_required"),
    # The matte adapter is not implemented: do not advertise it as runnable.
    ModelInfo("fal", "fal-ai/birefnet/v2", "matte", True,
              "Candidate for future matting adapter (not implemented)",
              "image", uploads_source=True, adapter_status="not_implemented",
              schema_url="https://fal.ai/models/fal-ai/birefnet/v2",
              price_status="user_estimate_required"),
    ModelInfo("comfyui", "user-workflow", "generate", False,
              "User-supplied local API graph; hardware not verified",
              "prompt", aspect_ratios=ASPECTS, resolution_tiers=TIERS,
              adapter_status="user_workflow_unverified",
              licensing="External checkpoints and ComfyUI retain their own licenses."),
    ModelInfo("comfyui", "user-upscale", "upscale", False,
              "User-supplied local upscaler graph; hardware not verified",
              "image", adapter_status="user_workflow_unverified",
              licensing="External checkpoints and ComfyUI retain their own licenses."),
    ModelInfo("comfyui", "user-segmentation", "segment", False,
              "User-supplied local segmentation graph; hardware not verified",
              "image_and_text", adapter_status="user_workflow_unverified",
              licensing="External checkpoints and ComfyUI retain their own licenses."),
    ModelInfo("anthropic", "user-specified", "judge", True,
              "BYO paid judge model; not remotely validated",
              "image_pair", uploads_source=True, adapter_status="unverified",
              licensing="External Anthropic API/model terms apply.",
              price_status="user_estimate_required"),
    ModelInfo("demo", "synthetic", "generate", False, "Offline synthetic images",
              "prompt", aspect_ratios=ASPECTS, resolution_tiers=TIERS,
              licensing="Bundled synthetic Python/Pillow adapter; MIT project code.",
              adapter_status="offline_tested"),
    ModelInfo("demo", "pillow", "upscale", False, "Pillow interpolation, not AI",
              "image", licensing="Pillow has its own license.",
              adapter_status="offline_tested"),
    ModelInfo("demo", "simple-mask", "segment", False, "Synthetic fixture mask",
              "image_and_text", licensing="Bundled synthetic Python/Pillow adapter.",
              adapter_status="offline_tested"),
    ModelInfo("demo", "synthetic", "segment", False, "Legacy demo synthetic mask alias",
              "image_and_text", licensing="Bundled synthetic Python/Pillow adapter.",
              adapter_status="offline_tested"),
    ModelInfo("demo", "technical", "judge", False, "Dimension checks, not aesthetics",
              "image_pair", licensing="Bundled project code.",
              adapter_status="offline_tested"),
)


def list_models() -> list[dict]:
    """JSON-friendly capability catalogue for CLI and prospective agents."""
    from dataclasses import asdict
    return [asdict(model) for model in MODELS]


def choices(operation: str) -> str:
    return ", ".join(sorted(
        f"{m.provider}:{m.model}" for m in MODELS
        if m.capability == operation and m.adapter_status != "not_implemented"
    ))


def _validate_fal_options(model: ModelInfo, endpoint: Endpoint) -> None:
    unknown = set(endpoint.options) - set(model.supported_options)
    if unknown:
        raise ValueError(f"{model.model} does not support options {sorted(unknown)}; "
                         f"allowed: {list(model.supported_options)}")
    if endpoint.model == "fal-ai/esrgan":
        scale = endpoint.options.get("scale", 2)
        if isinstance(scale, bool) or scale != 2:
            raise ValueError("Prehnite's ESRGAN adapter currently supports only scale=2")
        method = endpoint.options.get("model", "RealESRGAN_x2plus")
        if method not in ESRGAN_MODELS:
            raise ValueError(f"Unsupported ESRGAN model {method!r}; "
                             f"supported: {', '.join(ESRGAN_MODELS)}")
    elif "enable_prompt_expansion" in endpoint.options:
        if not isinstance(endpoint.options["enable_prompt_expansion"], bool):
            raise ValueError("enable_prompt_expansion must be a boolean")


def validate_capability(endpoint: Endpoint, operation: str,
                        *, ratio: str | None = None,
                        tier: str | None = None,
                        allow_cloud_uploads: bool = False) -> None:
    """Fail before any network call; avoid validating idle/unused stages."""
    if endpoint.provider == "disabled":
        raise ValueError(f"No {operation} adapter is enabled")
    if endpoint.provider == "anthropic":
        if operation != "judge" or not endpoint.model:
            raise ValueError("Anthropic is only supported as an explicit judge model")
        return  # Model IDs/terms must be confirmed by the caller; not certified here.
    if endpoint.provider == "comfyui":
        if operation not in ("generate", "upscale", "segment"):
            raise ValueError(f"ComfyUI {operation} is not implemented")
        if not endpoint.model:
            raise ValueError("Specify a local ComfyUI model/workflow label")
        # ComfyUI is deliberately open-ended: names refer to user-supplied
        # local graphs, not to a hosted provider allowlist.
        if not endpoint.options.get("workflow"):
            raise ValueError("ComfyUI requires options.workflow (API JSON graph)")
        return
    if endpoint.provider == "demo" and operation == "judge" and not endpoint.model:
        return  # Existing default technical judge is the local demo.
    match = next((m for m in MODELS if
                  (m.provider, m.model, m.capability) ==
                  (endpoint.provider, endpoint.model, operation)), None)
    if match is None or match.adapter_status == "not_implemented":
        raise ValueError(
            f"Unsupported {operation} adapter {endpoint.provider}:{endpoint.model}; "
            f"available: {choices(operation)}"
        )
    if ratio is not None and match.aspect_ratios and ratio not in match.aspect_ratios:
        raise ValueError(f"{match.model} does not support aspect ratio {ratio!r}")
    if tier is not None and match.resolution_tiers and tier not in match.resolution_tiers:
        raise ValueError(f"{match.model} does not support tier {tier!r}")
    if (match.model == "blackforestlabs/flux-3/klein/text-to-image"
            and ratio is not None and tier is not None):
        factor = 2 if tier == "4k" else 1
        requested_side = max(KLEIN_2K_DIMENSIONS[ratio]) * factor
        if match.max_output_side and requested_side > match.max_output_side:
            raise ValueError(f"{match.model} exceeds its declared maximum output side")
    if match.provider == "fal":
        if match.uploads_source and not allow_cloud_uploads:
            raise ValueError(f"{operation} requires allow_cloud_uploads=true")
        _validate_fal_options(match, endpoint)
    elif endpoint.options:
        raise ValueError(f"Offline demo {operation} does not accept provider options")


def validate_workflow_capabilities(manifest: Manifest, profile: Profile) -> None:
    """Validate exactly the stages this manifest can execute."""
    for asset in manifest.assets:
        if asset.prompt:
            for variant in profile.variants:
                tier = "2k" if variant == "enhanced_2k" else "4k"
                validate_capability(profile.generation, "generate",
                                    ratio=asset.aspect_ratio, tier=tier)
                if variant == "enhanced_2k":
                    validate_capability(profile.upscale, "upscale",
                                        allow_cloud_uploads=profile.costs.allow_cloud_uploads)
        if asset.targets:
            validate_capability(profile.segmentation, "segment",
                                allow_cloud_uploads=profile.costs.allow_cloud_uploads)
        if profile.judge.provider != "disabled":
            validate_capability(profile.judge, "judge",
                                allow_cloud_uploads=profile.costs.allow_cloud_uploads)
