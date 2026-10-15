"""Capability registry and model-provider selection."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    model: str
    capability: str
    paid: bool
    description: str


MODELS = (
    ModelInfo("fal", "blackforestlabs/flux-3/klein/text-to-image", "generate", True,
              "Hosted FLUX.3 Klein; 2k/4k tiers"),
    ModelInfo("fal", "fal-ai/esrgan", "upscale", True, "RealESRGAN_x2plus"),
    ModelInfo("fal", "fal-ai/sam-3-1/image", "segment", True, "Text-prompted segmentation"),
    ModelInfo("fal", "fal-ai/birefnet/v2", "matte", True, "Foreground matting"),
    ModelInfo("demo", "synthetic", "generate", False, "Synthetic offline fixture"),
    ModelInfo("demo", "pillow", "upscale", False, "Pillow interpolation, not AI enhancement"),
    ModelInfo("demo", "simple-mask", "segment", False, "Synthetic mask, testing only"),
    ModelInfo("demo", "technical", "judge", False, "Technical checks, not perceptual review"),
)


def list_models() -> list[dict]:
    return [m.__dict__ for m in MODELS]
