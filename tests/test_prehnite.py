import zipfile
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from pydantic import ValidationError
from prehnite.engine import Engine
from prehnite.images import make_cutout
from prehnite.schema import Manifest, Profile

def manifest():
    return {"id": "test", "assets": [
        {"id": "a", "prompt": "test", "aspect_ratio": "3:4",
         "target_size": [192, 256], "output": {"image": "photos/a.jpg"}},
        {"id": "b", "prompt": "test", "aspect_ratio": "9:16",
         "target_size": [144, 256], "output": {"image": "photos/b.png"}}
    ]}

@pytest.mark.parametrize("path", ["../x.png", "/x.png", "C:/x.png",
                                  "a//x.png", "./x.png", "a\\x.png"])
def test_unsafe_path(path):
    m = manifest()
    m["assets"][0]["output"]["image"] = path
    with pytest.raises(ValidationError):
        Manifest.model_validate(m)

def test_duplicates_rejected():
    m = manifest()
    m["assets"][1]["output"]["image"] = "photos/a.jpg"
    with pytest.raises(ValidationError):
        Manifest.model_validate(m)

def test_offline_batch_and_resume(tmp_path: Path):
    m = Manifest.model_validate(manifest())
    p = Profile.model_validate({
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "demo", "model": "pillow"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
    })
    engine = Engine(m, p, tmp_path)
    first = engine.run()
    assert len(first["asset_results"]) == 2
    assert all(a["status"] == "accepted" for a in first["asset_results"].values())
    assert first["cost_estimated_or_reserved_usd"] == 0
    count = first["operations"]
    with zipfile.ZipFile(engine.journal.root/"prehnite-test.zip") as z:
        assert "photos/a.jpg" in z.namelist()
        assert "photos/b.png" in z.namelist()
        assert z.testzip() is None
    assert engine.run()["operations"] == count
    engine.journal.close()

def test_cutout(tmp_path):
    src, mask = tmp_path/"src.png", tmp_path/"mask.png"
    Image.new("RGB", (64, 64), "red").save(src)
    m = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(m).ellipse((10, 10, 50, 50), fill=255)
    m.save(mask)
    assert 0 < make_cutout(src, mask, tmp_path/"out.png")["coverage"] < 1

def test_full_mask_rejected(tmp_path):
    src, mask = tmp_path/"src.png", tmp_path/"mask.png"
    Image.new("RGB", (64, 64), "red").save(src)
    Image.new("L", (64, 64), 255).save(mask)
    with pytest.raises(ValueError):
        make_cutout(src, mask, tmp_path/"out.png")
