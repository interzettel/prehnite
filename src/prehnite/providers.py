"""Interchangeable image inference. All paid operations must pass a policy gate."""
from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageDraw, ImageFilter

from .schema import Endpoint
from .images import validate_segmentation_mask
from .registry import KLEIN_2K_DIMENSIONS, validate_capability


@dataclass
class Result:
    path: Path
    provider_request_id: str | None = None
    metadata: dict = field(default_factory=dict)


def download_image(url: str, destination: Path) -> None:
    # URLs originate from fal's returned image artifacts; restrict cross-network downloads.
    p = urlparse(url)
    if p.scheme != "https" or not (
        p.hostname == "fal.media" or (p.hostname or "").endswith(".fal.media")
    ):
        raise ValueError("Refusing non-fal or non-HTTPS output URL")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=False, timeout=120) as r:
        r.raise_for_status()
        if int(r.headers.get("content-length", "0")) > 100_000_000:
            raise ValueError("Artifact too large")
        total = 0
        with destination.open("wb") as f:
            for chunk in r.iter_bytes(1024 * 1024):
                total += len(chunk)
                if total > 100_000_000:
                    raise ValueError("Artifact too large")
                f.write(chunk)
    with Image.open(destination) as image:
        image.verify()


class Demo:
    """Deterministic synthetic fixtures, NOT a real image generation model."""

    def generate(self, prompt: str, aspect_ratio: str, tier: str, seed: int,
                 output: Path, endpoint: Endpoint, on_submit=None,
                 resume_id=None) -> Result:
        w, h = {"9:16": (576, 1024), "3:4": (768, 1024), "4:3": (1024, 768),
                "16:9": (1024, 576), "1:1": (1024, 1024)}[aspect_ratio]
        if tier == "4k":
            w, h = w * 2, h * 2
        rng = random.Random(seed)
        im = Image.new("RGB", (w, h), (rng.randrange(80, 180), 110, 125))
        draw = ImageDraw.Draw(im)
        draw.ellipse((w // 5, h // 5, w * 4 // 5, h * 4 // 5),
                     fill=(220, rng.randrange(90, 180), 80))
        draw.text((16, 16), "DEMO - NOT AI PHOTOGRAPHY", fill="white")
        output.parent.mkdir(parents=True, exist_ok=True)
        im.save(output)
        return Result(output, metadata={"synthetic": True, "seed": seed})

    def upscale(self, source: Path, output: Path, endpoint: Endpoint, on_submit=None,
                resume_id=None) -> Result:
        with Image.open(source) as im:
            result = im.resize((im.width * 2, im.height * 2), Image.Resampling.LANCZOS)
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(output)
        return Result(output, metadata={"interpolation_only": True})

    def segment(self, source: Path, target: str, output: Path, endpoint: Endpoint,
                on_submit=None, resume_id=None) -> Result:
        with Image.open(source) as im:
            mask = Image.new("L", im.size, 0)
            ImageDraw.Draw(mask).ellipse((im.width // 5, im.height // 5,
                                         im.width * 4 // 5, im.height * 4 // 5),
                                        fill=255)
            output.parent.mkdir(parents=True, exist_ok=True)
            mask.save(output)
        return Result(output, metadata={"synthetic_mask": True})


FLUX3_KLEIN = "blackforestlabs/flux-3/klein/text-to-image"
FLUX3_IMAGE = "blackforestlabs/flux-3/text-to-image"
ESRGAN = "fal-ai/esrgan"

# Klein accepts explicit image_size dimensions. Values are a long-edge
# target, NOT proof of the exact pixels a remote model will return.
_KLEIN_2K = KLEIN_2K_DIMENSIONS


def fal_generation_inputs(endpoint: Endpoint, prompt: str, ratio: str,
                          tier: str, seed: int) -> dict:
    """Model-specific arguments, fail-closed rather than guessing schema."""
    if ratio not in _KLEIN_2K or tier not in ("2k", "4k"):
        raise ValueError("Unsupported fal aspect ratio or resolution tier")
    common = {
        "prompt": prompt,
        "output_format": "png",
        "enable_prompt_expansion": bool(
            endpoint.options.get("enable_prompt_expansion", False)),
    }
    if endpoint.model == FLUX3_KLEIN:
        w, h = _KLEIN_2K[ratio]
        factor = 2 if tier == "4k" else 1
        return {**common, "seed": seed,
                "image_size": {"width": w * factor, "height": h * factor}}
    if endpoint.model == FLUX3_IMAGE:
        # FLUX.3 Image API exposes ratio/resolution, but its published schema
        # does not advertise an explicit seed. Do not submit an unknown field.
        return {**common, "aspect_ratio": ratio, "resolution": tier}
    raise ValueError(
        f"No verified fal generation schema for {endpoint.model!r}; "
        "add a typed adapter before making paid requests"
    )


class Fal:
    """fal-client queue adapter preserving request IDs before waiting for results."""

    @staticmethod
    def _client():
        # Check before *uploading* any private source image, too.
        if not os.environ.get("FAL_KEY"):
            raise RuntimeError("Set FAL_KEY before using paid fal inference")
        try:
            import fal_client
        except ImportError as exc:
            raise RuntimeError("Install prehnite[fal] to use fal") from exc
        return fal_client

    def _execute(self, endpoint: Endpoint, inputs: dict, output: Path,
                 select: str, on_submit: Callable[[str], None] | None,
                 resume_id: str | None) -> Result:
        fal_client = self._client()
        if resume_id:
            handle = fal_client.get_handle(endpoint.model, resume_id)
        else:
            # Submission can be billed even if the response is lost. The caller must
            # mark an ambiguous submission for manual reconciliation, not blind retry.
            handle = fal_client.submit(endpoint.model, arguments=inputs)
            if not isinstance(getattr(handle, "request_id", None), str) or not handle.request_id:
                raise ValueError("fal queue did not return a usable request ID")
            if on_submit:
                on_submit(handle.request_id)
        result = handle.get(interval=1.0)
        if not isinstance(result, dict):
            raise ValueError("fal queue returned an invalid response object")
        entries = result.get(select)
        if isinstance(entries, list) and not entries:
            raise ValueError("Unexpected fal response: empty image list")
        if select == "masks" and (not isinstance(entries, list) or len(entries) != 1):
            raise ValueError("SAM must return exactly one unambiguous mask")
        item = entries[0] if isinstance(entries, list) else entries
        if not isinstance(item, dict) or not item.get("url"):
            raise ValueError("Unexpected fal response: missing image URL")
        download_image(item["url"], output)
        return Result(output, handle.request_id,
                      {"seed": result.get("seed"), "timings": result.get("timings", {}),
                       "image": {"width": item.get("width"), "height": item.get("height")}})

    def generate(self, prompt: str, aspect_ratio: str, tier: str, seed: int,
                 output: Path, endpoint: Endpoint, on_submit=None, resume_id=None) -> Result:
        validate_capability(endpoint, "generate", ratio=aspect_ratio, tier=tier)
        # On a resume the queue ID is authoritative; never construct a new
        # generation request or submit it to another endpoint.
        inputs = {} if resume_id else fal_generation_inputs(
            endpoint, prompt, aspect_ratio, tier, seed)
        return self._execute(endpoint, inputs, output, "images", on_submit, resume_id)

    def upscale(self, source: Path, output: Path, endpoint: Endpoint,
                on_submit=None, resume_id=None) -> Result:
        validate_capability(endpoint, "upscale", allow_cloud_uploads=True)
        if endpoint.model != ESRGAN:
            raise ValueError("Unsupported fal upscale model; require a tested schema")
        fal_client = self._client()
        # Upload only for a NEW remote request. On resumption, replaying
        # upload_file leaks bytes and consumes bandwidth needlessly.
        inputs = {} if resume_id else {
            "image_url": fal_client.upload_file(str(source)),
            "scale": 2,
            "model": endpoint.options.get("model", "RealESRGAN_x2plus"),
            "output_format": "png",
        }
        return self._execute(endpoint, inputs, output, "image", on_submit, resume_id)

    def segment(self, source: Path, target: str, output: Path, endpoint: Endpoint,
                on_submit=None, resume_id=None) -> Result:
        validate_capability(endpoint, "segment", allow_cloud_uploads=True)
        if endpoint.model != "fal-ai/sam-3-1/image":
            raise ValueError("Unsupported fal segmentation model; use documented SAM 3.1 image endpoint")
        fal_client = self._client()
        inputs = {} if resume_id else {
            "image_url": fal_client.upload_file(str(source)),
            "prompt": target,
            "apply_mask": False,
            "return_multiple_masks": False,
            "include_scores": True,
            "output_format": "png",
        }
        result = self._execute(endpoint, inputs, output, "masks", on_submit, resume_id)
        checked = validate_segmentation_mask(source, output)
        result.metadata["mask_validation"] = checked
        return result


def get_provider(endpoint: Endpoint):
    if endpoint.provider == "demo":
        return Demo()
    if endpoint.provider == "fal":
        return Fal()
    if endpoint.provider == "comfyui":
        from .comfy import Comfy
        return Comfy()
    raise ValueError(f"No installed adapter for {endpoint.provider}")
