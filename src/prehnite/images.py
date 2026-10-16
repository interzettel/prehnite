"""Pure local pixel operations; never modify the source file in place."""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def image_info(path: Path) -> dict:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return {"width": image.width, "height": image.height,
                "mode": image.mode, "sha256": sha256(path)}


def resize_to(source: Path, destination: Path, size: tuple[int, int]) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original)
        if abs(image.width / image.height - size[0] / size[1]) > 0.03:
            raise ValueError("Unexpected aspect ratio: refusing to crop image")
        image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
        if destination.suffix.lower() in (".jpg", ".jpeg"):
            image.convert("RGB").save(destination, "JPEG", quality=94, subsampling=0)
        elif destination.suffix.lower() == ".webp":
            image.save(destination, "WEBP", quality=95)
        elif destination.suffix.lower() == ".png":
            image.save(destination, "PNG", optimize=True)
        else:
            raise ValueError("Use .png, .jpg, .jpeg or .webp image output")
    return image_info(destination)



def _mask_alpha(mask: Image.Image, source_size: tuple[int, int]) -> Image.Image:
    """Normalize one mask without silently stretching a different aspect ratio."""
    oriented = ImageOps.exif_transpose(mask)
    w, h = source_size
    if abs(oriented.width / oriented.height - w / h) > 0.015:
        raise ValueError("Mask and source have different aspect ratios; alignment unknown")
    if oriented.mode == "RGBA":
        channel = oriented.getchannel("A")
        if channel.getextrema() == (255, 255):
            oriented = oriented.convert("RGB")
        else:
            alpha = channel
            extrema = alpha.getextrema()
            if extrema in ((0, 0), (255, 255)):
                raise ValueError("Empty or entire-frame mask cannot be accepted as cutout")
            return alpha.resize(source_size, Image.Resampling.LANCZOS)
    if oriented.mode == "RGB":
        red, green, blue = oriented.split()
        if ImageChops.difference(red, green).getbbox() or ImageChops.difference(red, blue).getbbox():
            raise ValueError("Colored mask channels cannot be treated as grayscale alpha")
        alpha = red
    elif oriented.mode in ("1", "L"):
        alpha = oriented.convert("L")
    else:
        raise ValueError(f"Unsupported mask mode: {oriented.mode}")
    if alpha.getextrema() in ((0, 0), (255, 255)):
        raise ValueError("Empty or entire-frame mask cannot be accepted as cutout")
    return alpha.resize(source_size, Image.Resampling.LANCZOS)


def validate_segmentation_mask(source: Path, mask_path: Path) -> dict:
    """Validate one-mask geometry and channel semantics before stage acceptance."""
    with Image.open(source) as original, Image.open(mask_path) as mask:
        size = ImageOps.exif_transpose(original).size
        alpha = _mask_alpha(mask, size)
        extrema = alpha.getextrema()
        return {"width": size[0], "height": size[1], "alpha_extrema": extrema}


def make_cutout(source: Path, mask_path: Path, destination: Path,
                *, refine: bool = False) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image, Image.open(mask_path) as mask:
        image = ImageOps.exif_transpose(image).convert("RGBA")
        # SAM can return RGB grayscale or RGBA alpha; reject mismatched
        # coordinate geometry and ambiguous colorized segmentation maps.
        alpha = _mask_alpha(mask, image.size)
        if refine:
            alpha = alpha.filter(ImageFilter.MedianFilter(size=3))
            alpha = alpha.filter(ImageFilter.GaussianBlur(radius=0.65))
        extrema = alpha.getextrema()
        image.putalpha(alpha)
        image.save(destination, "PNG", optimize=True)
        coverage = sum(1 for n in alpha.resize((128, 128)).tobytes() if n > 127) / 16384
        return {**image_info(destination), "coverage": coverage, "alpha_extrema": extrema}


def preview_cutout(path: Path, destination: Path, max_edge: int = 1100) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
        rgba.thumbnail((max_edge, max_edge))
        bg = Image.new("RGB", rgba.size, "#dcdcdc")
        bg.paste(rgba, mask=rgba.getchannel("A"))
        bg.save(destination, "JPEG", quality=87)
    return destination
