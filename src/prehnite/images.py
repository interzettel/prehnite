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


def make_cutout(source: Path, mask_path: Path, destination: Path,
                *, refine: bool = False) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image, Image.open(mask_path) as mask:
        image = ImageOps.exif_transpose(image).convert("RGBA")
        # SAM endpoints generally return grayscale RGB masks; never use JPEG alpha.
        if mask.mode == "RGBA":
            alpha = mask.getchannel("A")
            # Transparent-background masks use their alpha; opaque masks use luminance.
            if alpha.getextrema() == (255, 255):
                alpha = mask.convert("RGB").convert("L")
        else:
            alpha = mask.convert("L")
        alpha = alpha.resize(image.size, Image.Resampling.LANCZOS)
        if refine:
            alpha = alpha.filter(ImageFilter.MedianFilter(size=3))
            alpha = alpha.filter(ImageFilter.GaussianBlur(radius=0.65))
        extrema = alpha.getextrema()
        if extrema == (0, 0) or extrema == (255, 255):
            raise ValueError("Empty or entire-frame mask cannot be accepted as cutout")
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
