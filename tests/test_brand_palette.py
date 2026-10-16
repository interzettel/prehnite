"""Canonical brand palette and offline embedding constraints."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from prehnite.brand import DARK, LIGHT, embedded_theme_css


def _relative_luminance(hex_code: str) -> float:
    channels = (int(hex_code[n:n+2], 16) / 255 for n in (1, 3, 5))
    r, g, b = (
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    )
    return 0.2126*r + 0.7152*g + 0.0722*b


def _contrast(a: str, b: str) -> float:
    l1, l2 = sorted((_relative_luminance(a), _relative_luminance(b)))
    return (l2 + 0.05) / (l1 + 0.05)


def test_brand_light_and_dark_text_exceed_wcag_aa():
    assert _contrast(LIGHT["ink"], LIGHT["bg"]) >= 4.5
    assert _contrast(LIGHT["sub"], LIGHT["bg"]) >= 4.5
    assert _contrast(LIGHT["coral_text"], LIGHT["bg"]) >= 4.5
    assert _contrast(DARK["ink"], DARK["bg"]) >= 4.5
    assert _contrast(DARK["sub"], DARK["bg"]) >= 4.5
    assert _contrast(DARK["coral_text"], DARK["bg"]) >= 4.5


def test_vivid_coral_is_not_used_as_small_light_mode_text():
    assert _contrast(LIGHT["coral"], LIGHT["bg"]) < 4.5
    assert LIGHT["coral"] != LIGHT["coral_text"]


def test_inline_theme_contains_both_color_modes_and_no_external_assets():
    css = embedded_theme_css()
    assert "--bg:#F6EFE2" in css
    assert "--ink:#075231" in css
    assert "--coral:#F7655B" in css
    assert "@media(prefers-color-scheme:dark)" in css
    assert "--bg:#132820" in css
    assert "url(" not in css
    assert "import" not in css.lower()
    assert "http" not in css.lower()


def test_owner_selected_full_resolution_png_and_rounded_readme_hero():
    root = Path(__file__).resolve().parents[1]
    path = root / "assets/prehnite-riso-green-coral.png"
    assert path.read_bytes()[:4] == bytes((137, 80, 78, 71))
    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.size == (2020, 779)
        rgba = image.convert("RGBA")
        assert rgba.getpixel((0, 0))[3] == 0
        assert rgba.getpixel((2019, 778))[3] == 0
        assert rgba.getpixel((1010, 389))[3] >= 250
        image.verify()
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert 'src="assets/prehnite-riso-green-coral.png"' in readme
    assert 'border-radius: 16px' in readme
    assert not (root / "assets/prehnite-riso-green-coral.webp").exists()
    assert not (root / "assets/prehnite-lockup.svg").exists()
    assert (root / "assets/prehnite-mark.svg").exists()
    assert "prehnite-riso-green-coral.webp" not in readme
    assert "prehnite-lockup.svg" not in readme
