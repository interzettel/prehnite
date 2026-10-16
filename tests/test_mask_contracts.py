"""Reject misleading masks without stretching or misreading color channels."""
import pytest
from PIL import Image, ImageDraw
from prehnite.images import make_cutout, validate_segmentation_mask


@pytest.fixture
def source(tmp_path):
    file = tmp_path / "source.png"
    Image.new("RGB", (192, 256), "orange").save(file)
    return file


def test_accepts_single_grayscale_mask_at_matching_aspect_ratio(source, tmp_path):
    path = tmp_path / "mask.png"
    mask = Image.new("L", (96, 128), 0)
    ImageDraw.Draw(mask).rectangle((20, 30, 70, 105), fill=255)
    mask.save(path)
    checked = validate_segmentation_mask(source, path)
    assert checked["width"] == 192 and checked["height"] == 256
    output = tmp_path / "cutout.png"
    meta = make_cutout(source, path, output)
    assert 0 < meta["coverage"] < 1
    with Image.open(output) as result:
        assert result.mode == "RGBA" and result.size == (192, 256)


def test_rgba_alpha_is_authoritative_when_transparent(source, tmp_path):
    path = tmp_path / "mask.png"
    alpha = Image.new("L", (192, 256), 0)
    ImageDraw.Draw(alpha).rectangle((25, 30, 170, 240), fill=255)
    mask = Image.new("RGBA", (192, 256), (255, 0, 0, 0))
    mask.putalpha(alpha)
    mask.save(path)
    assert validate_segmentation_mask(source, path)["alpha_extrema"] == (0, 255)
    result = make_cutout(source, path, tmp_path / "result.png")
    assert result["alpha_extrema"] == (0, 255)


def test_grayscale_rgb_mask_is_accepted(source, tmp_path):
    path = tmp_path / "mask.png"
    mask = Image.new("L", (192, 256), 0)
    ImageDraw.Draw(mask).ellipse((20, 30, 155, 205), fill=255)
    mask.convert("RGB").save(path)
    assert make_cutout(source, path, tmp_path / "result.png")["coverage"] > 0


@pytest.mark.parametrize("mode", ["empty", "full", "wrong_ratio", "colorized"])
def test_invalid_sam_mask_is_rejected_before_cutout(source, tmp_path, mode):
    path = tmp_path / "mask.png"
    if mode == "wrong_ratio":
        mask = Image.new("L", (256, 256), 0)
        ImageDraw.Draw(mask).rectangle((10, 10, 100, 100), fill=255)
    elif mode == "colorized":
        mask = Image.new("RGB", (192, 256), (255, 0, 0))
    else:
        mask = Image.new("L", (192, 256), 0 if mode == "empty" else 255)
    mask.save(path)
    with pytest.raises(ValueError, match="aspect ratios|Colored mask|Empty or entire"):
        validate_segmentation_mask(source, path)
    with pytest.raises(ValueError):
        make_cutout(source, path, tmp_path / "result.png")
    assert not (tmp_path / "result.png").exists()


def test_wrong_fal_segmentation_model_rejected_before_upload(monkeypatch, source, tmp_path):
    from prehnite.providers import Fal
    from prehnite.schema import Endpoint
    monkeypatch.delenv("FAL_KEY", raising=False)
    with pytest.raises(ValueError, match="Unsupported fal segmentation"):
        Fal().segment(source, "person", tmp_path/"mask.png",
                      Endpoint(provider="fal", model="fal-ai/sam3.1"))
