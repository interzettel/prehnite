"""Native-pixel crop evidence: zero inferred subjects, network calls or AI charges."""
from __future__ import annotations

import hashlib
import json
import shutil

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageOps
from typer.testing import CliRunner

from prehnite.cli import app
from prehnite.crops import make_detail_crops


def patterned(path, *, size=(2160, 3840), mode="RGB"):
    # No full-resolution Python pixel loop; just distinctive known positions.
    im = Image.new(mode, size, (20, 40, 60, 255) if mode == "RGBA" else (20, 40, 60))
    draw = ImageDraw.Draw(im)
    w, h = size
    draw.rectangle((0, 0, 200, 200), fill="red")
    draw.rectangle((w - 201, 0, w - 1, 200), fill="green")
    draw.rectangle((0, h - 201, 200, h - 1), fill="blue")
    draw.rectangle((w - 201, h - 201, w - 1, h - 1), fill="yellow")
    draw.ellipse((w//2 - 100, h//2 - 100, w//2 + 100, h//2 + 100),
                 fill="white")
    im.save(path, "PNG")
    return im


def test_real_4k_native_tiles_are_pixel_identical_without_any_resizing(tmp_path):
    original = tmp_path / "photo.png"
    patterned(original)
    before = original.read_bytes()
    evidence = make_detail_crops(original, tmp_path / "evidence", edge=1024,
                                 anchor=(0.75, 0.33))
    assert len(evidence["crops"]) == 6
    assert (evidence["source_width"], evidence["source_height"]) == (2160, 3840)
    assert evidence["crop_edge"] == 1024
    assert original.read_bytes() == before
    with Image.open(original) as source:
        for entry in evidence["crops"]:
            assert (entry["width"], entry["height"]) == (1024, 1024)
            box = entry["box_xyxy"]
            assert 0 <= box[0] < box[2] <= source.width
            assert 0 <= box[1] < box[3] <= source.height
            with Image.open(tmp_path/"evidence"/entry["file"]) as actual:
                assert actual.size == (1024, 1024)
                expected = source.crop(tuple(box))
                assert ImageChops.difference(actual.convert("RGB"), expected.convert("RGB")).getbbox() is None
            blob = (tmp_path/"evidence"/entry["file"]).read_bytes()
            assert hashlib.sha256(blob).hexdigest() == entry["sha256"]
            assert len(blob) == entry["bytes"]
    assert (tmp_path/"evidence"/"overview.png").is_file()
    assert evidence["overview"]["width"] <= 900
    assert evidence["overview"]["height"] <= 900
    assert evidence["quality_judgment"].startswith("none")


def test_center_and_anchor_coordinates_clamp_to_source_bounds(tmp_path):
    source = tmp_path/"input.png"
    Image.new("RGB", (256, 384), "teal").save(source)
    evidence = make_detail_crops(source, tmp_path/"out", edge=128,
                                 anchor=(0.0, 1.0))
    boxes = {entry["label"]: entry["box_xyxy"] for entry in evidence["crops"]}
    assert boxes["top-left"] == [0, 0, 128, 128]
    assert boxes["top-right"] == [128, 0, 256, 128]
    assert boxes["center"] == [64, 128, 192, 256]
    assert boxes["bottom-left"] == [0, 256, 128, 384]
    assert boxes["bottom-right"] == [128, 256, 256, 384]
    assert boxes["anchor"] == [0, 256, 128, 384]


def test_rerun_is_deterministic_and_manifest_has_no_absolute_source_path(tmp_path):
    source = tmp_path/"private-client-photo.png"
    Image.new("RGB", (480, 720), (1, 2, 3)).save(source)
    output = tmp_path/"out"
    first = make_detail_crops(source, output, edge=256)
    files = sorted(output.iterdir())
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    second = make_detail_crops(source, output, edge=256)
    assert first == second
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in files}
    assert str(tmp_path) not in (output/"crops.json").read_text(encoding="utf-8")
    assert json.loads((output/"crops.json").read_text()) == second


def test_exif_orientation_applied_to_coordinate_frame(tmp_path):
    path = tmp_path/"camera.jpg"
    im = Image.new("RGB", (640, 880), "black")
    ImageDraw.Draw(im).rectangle((0, 0, 130, 130), fill="red")
    exif = Image.Exif()
    exif[274] = 6
    im.save(path, "JPEG", quality=95, exif=exif)
    out = tmp_path/"out"
    result = make_detail_crops(path, out, edge=256)
    assert (result["source_width"], result["source_height"]) == (880, 640)
    with Image.open(path) as original:
        expected = ImageOps.exif_transpose(original).crop(
            tuple(result["crops"][0]["box_xyxy"]))
        with Image.open(out/"top-left.png") as tile:
            assert ImageChops.difference(tile.convert("RGB"), expected.convert("RGB")).getbbox() is None


def test_alpha_channel_survives_native_png_crops(tmp_path):
    path = tmp_path/"rgba.png"
    im = Image.new("RGBA", (256, 256), (45, 80, 100, 20))
    ImageDraw.Draw(im).rectangle((10, 15, 70, 85), fill=(255, 100, 50, 255))
    im.save(path)
    make_detail_crops(path, tmp_path/"out", edge=128)
    with Image.open(tmp_path/"out"/"top-left.png") as crop:
        assert crop.mode == "RGBA"
        assert crop.getpixel((0, 0)) == (45, 80, 100, 20)
        assert crop.getpixel((20, 30)) == (255, 100, 50, 255)


@pytest.mark.parametrize("edge,anchor", [
    (0, None), (64, None), (2049, None), (True, None), (123.2, None),
    (128, (float("nan"), 0.5)), (128, (0.5, float("inf"))),
    (128, (-0.01, 0.4)), (128, (0.5, 1.01)), (128, (True, 0.2)),
])
def test_bad_crop_geometry_fails_before_publishing(tmp_path, edge, anchor):
    photo = tmp_path/"photo.png"
    Image.new("RGB", (256, 256), "red").save(photo)
    target = tmp_path/"output"
    with pytest.raises(ValueError):
        make_detail_crops(photo, target, edge=edge, anchor=anchor)
    assert not target.exists()


def test_short_side_cannot_be_upscaled_silently(tmp_path):
    source = tmp_path/"source.png"
    Image.new("RGB", (300, 160), "red").save(source)
    with pytest.raises(ValueError, match="no upscaling"):
        make_detail_crops(source, tmp_path/"out", edge=256)


def test_source_cannot_be_overwritten_by_generated_crop(tmp_path):
    source = tmp_path/"top-left.png"
    Image.new("RGB", (256, 256), "red").save(source)
    old = source.read_bytes()
    with pytest.raises(ValueError, match="replace the source"):
        make_detail_crops(source, tmp_path, edge=128)
    assert source.read_bytes() == old


def test_existing_crop_survives_png_encoding_failure(monkeypatch, tmp_path):
    from prehnite import crops
    source = tmp_path/"src.png"
    Image.new("RGB", (512, 512), "red").save(source)
    target = tmp_path/"out"
    make_detail_crops(source, target, edge=128)
    baseline = (target/"top-left.png").read_bytes()
    original = crops._write_png
    def fail_on_second(image, destination):
        if destination.name == "top-left.png":
            raise OSError("simulated PNG save failure")
        return original(image, destination)
    monkeypatch.setattr(crops, "_write_png", fail_on_second)
    with pytest.raises(OSError):
        make_detail_crops(source, target, edge=128)
    assert (target/"top-left.png").read_bytes() == baseline


def test_crops_cli_succeeds_without_model_or_network(tmp_path):
    photo = tmp_path/"photo.png"
    Image.new("RGB", (320, 420), "navy").save(photo)
    folder = tmp_path/"out"
    runner = CliRunner()
    result = runner.invoke(app, ["crops", str(photo), "--output", str(folder),
                                "--edge", "128", "--anchor-x", "0.4",
                                "--anchor-y", "0.6"])
    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["native_crops"] == 6
    assert (folder/"crops.json").exists()


def test_crops_cli_rejects_half_anchor(tmp_path):
    photo = tmp_path/"photo.png"
    Image.new("RGB", (320, 420), "navy").save(photo)
    result = CliRunner().invoke(app, ["crops", str(photo), "--output",
                                      str(tmp_path/"out"), "--anchor-x", "0.5"])
    assert result.exit_code != 0
    assert not (tmp_path/"out").exists()


def test_verified_tiles_are_safe_for_future_judge_adapters(tmp_path):
    from prehnite.crops import verified_crop_paths
    source = tmp_path/"photo.png"
    Image.new("RGB", (300, 400), "red").save(source)
    output = tmp_path/"out"
    make_detail_crops(source, output, edge=128)
    tiles = verified_crop_paths(output, source=source)
    assert set(tiles) == {"top-left", "top-right", "center",
                          "bottom-left", "bottom-right"}
    assert all(path.is_file() for path in tiles.values())
    Image.new("RGB", (128, 128), "blue").save(tiles["center"])
    with pytest.raises(ValueError, match="Corrupt crop evidence"):
        verified_crop_paths(output, source=source)


def test_crop_loader_rejects_path_manipulation_and_changed_source(tmp_path):
    from prehnite.crops import verified_crop_paths
    source = tmp_path/"photo.png"
    Image.new("RGB", (300, 400), "red").save(source)
    output = tmp_path/"out"
    make_detail_crops(source, output, edge=128)
    Image.new("RGB", (300, 400), "green").save(source)
    with pytest.raises(ValueError, match="Source image changed"):
        verified_crop_paths(output, source=source)
    data = json.loads((output/"crops.json").read_text())
    data["crops"][0]["file"] = "../secret.png"
    (output/"crops.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Unexpected crop evidence name"):
        verified_crop_paths(output)
