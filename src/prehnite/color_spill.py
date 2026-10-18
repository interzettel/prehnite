"""Opt-in pixel-level color-spill correction for a known *uniform* backdrop.

This is not generic photo matting. Given a trustworthy soft alpha and a
verified, operator-declared RGB background, observed RGB is modelled as
C = alpha * F + (1 - alpha) * B. Solve for F only in the existing foreground
boundary band. Never remove alpha, change the hard silhouette, or try to
guess a natural-image backdrop. Optical transparency requires human review.
"""
from __future__ import annotations

from PIL import Image

MAX_SPILL_PIXELS = 12_000_000


class ColorSpillRefused(ValueError):
    """The explicit background/alpha evidence is insufficient for safe unmixing."""


def unmix_known_uniform_background(
    source: Image.Image,
    alpha: Image.Image,
    hard: Image.Image,
    *,
    background_rgb: tuple[int, int, int],
    border_tolerance: int = 8,
    min_alpha: int = 48,
    max_clipped_fraction: float = 0.1,
) -> tuple[Image.Image, dict]:
    """Return foreground RGB and factual correction statistics; never alter alpha.

    Only modify pixels inside the supplied hard foreground where the *soft*
    alpha is nonzero and <255. Preserve fully opaque interior RGB verbatim,
    including any real product feature whose color equals the background.
    Refuse a nonuniform/incorrect backdrop instead of treating all greenish
    or similar-colored objects as removable contamination. The caller retains
    the exact alpha channel and keeps independent visual review mandatory.
    """
    if not (
        source.mode in ("RGB", "RGBA")
        and alpha.mode == "L"
        and hard.mode == "L"
        and source.size == alpha.size == hard.size
    ):
        raise ColorSpillRefused("rgb_alpha_hard_geometry_mismatch")
    width, height = source.size
    if width < 8 or height < 8 or width * height > MAX_SPILL_PIXELS:
        raise ColorSpillRefused("unsupported_spill_image_size")
    if (not isinstance(background_rgb, tuple) or len(background_rgb) != 3
            or any(type(x) is not int or not 0 <= x <= 255 for x in background_rgb)):
        raise ColorSpillRefused("invalid_known_background_rgb")
    if (not 0 <= border_tolerance <= 16 or not 32 <= min_alpha <= 224
            or not 0 <= max_clipped_fraction <= 0.25):
        raise ColorSpillRefused("unsafe_unmix_policy")
    rgb = source.convert("RGB")
    pixels = rgb.load()
    hard_pixels = hard.load()
    alpha_pixels = alpha.load()
    max_delta = 0
    # Verify every frame-border pixel, not just a selected corner or average.
    # Reject cropped foreground and incorrect/nonuniform operator assertions.
    for x in range(width):
        for y in (0, height - 1):
            if hard_pixels[x, y] > 127:
                raise ColorSpillRefused("foreground_touches_frame")
            max_delta = max(max_delta, max(abs(pixels[x, y][c] - background_rgb[c])
                                           for c in range(3)))
    for y in range(1, height - 1):
        for x in (0, width - 1):
            if hard_pixels[x, y] > 127:
                raise ColorSpillRefused("foreground_touches_frame")
            max_delta = max(max_delta, max(abs(pixels[x, y][c] - background_rgb[c])
                                           for c in range(3)))
    if max_delta > border_tolerance:
        raise ColorSpillRefused("background_not_uniform_or_mismatched")

    result = rgb.copy()
    output = result.load()
    candidates = corrected = clipped = below_alpha = collision_preserved = 0
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            opacity = alpha_pixels[x, y]
            if hard_pixels[x, y] <= 127 or opacity in (0, 255):
                continue
            if opacity < min_alpha:
                below_alpha += 1
                continue
            candidates += 1
            observed = pixels[x, y]
            # Solve the physical straight-alpha color mixture in 8-bit units:
            # foreground = (255*C - (255-a)*B) / a.
            estimates = tuple(
                (255 * observed[c] - (255 - opacity) * background_rgb[c]) / opacity
                for c in range(3)
            )
            # Clamping would invent colors when alpha/background assumptions
            # are wrong. Reject clipped candidates instead of saturating.
            if any(v < -1.0 or v > 256.0 for v in estimates):
                clipped += 1
                continue
            restored = tuple(max(0, min(255, round(v))) for v in estimates)
            if observed == background_rgb:
                collision_preserved += 1
            if restored != observed:
                output[x, y] = restored
                corrected += 1
    if candidates and clipped / candidates > max_clipped_fraction:
        raise ColorSpillRefused("unmix_clipping_exceeds_declared_limit")
    return result, {
        "color_spill_unmix_applied": True,
        "color_spill_background_rgb": list(background_rgb),
        "color_spill_border_max_delta": max_delta,
        "color_spill_eligible_edge_pixels": candidates,
        "color_spill_corrected_edge_pixels": corrected,
        "color_spill_clipped_edge_pixels": clipped,
        "color_spill_low_alpha_skipped_pixels": below_alpha,
        "color_spill_background_color_collision_preserved_pixels": collision_preserved,
        "color_spill_alpha_modified_pixels": 0,
    }
