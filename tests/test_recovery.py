from pathlib import Path

import pytest
from PIL import Image

from prehnite.engine import Engine
from prehnite.schema import Endpoint, Manifest, Profile


def profile():
    return Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
        "costs": {"allow_paid": True, "allow_cloud_uploads": True,
                  "max_usd": 0.10,
                  "estimates_usd": {"generation:2k": 0.02}},
    })


def sample():
    return Manifest.model_validate({"id": "recovery", "assets": [
        {"id": "fixture", "prompt": "test", "aspect_ratio": "3:4",
         "target_size": [192, 256], "output": {"image": "fixture.png"}}
    ]})


def test_ambiguous_remote_submit_is_not_billed_twice(tmp_path):
    engine = Engine(sample(), profile(), tmp_path)
    ep = Endpoint(provider="fal", model="mock-remote")
    invoked = []
    def timeout(on_submit, resume, staged_output):
        invoked.append(1)
        raise TimeoutError("Network connection lost before receipt")
    with pytest.raises(TimeoutError):
        engine.stage("x", "generation", ep, tmp_path/"x.png",
                     timeout, "generation:2k")
    assert engine.journal.get("x")["status"] == "uncertain"
    with pytest.raises(RuntimeError, match="Ambiguous"):
        engine.stage("x", "generation", ep, tmp_path/"x.png",
                     timeout, "generation:2k")
    assert len(invoked) == 1
    assert engine.journal.reserved() == 0.02
    engine.journal.close()


def test_existing_input_skips_generation(tmp_path):
    source_root = tmp_path/"inputs"
    source_root.mkdir()
    Image.new("RGB", (192, 256), "red").save(source_root/"original.png")
    m = Manifest.model_validate({"id": "existing", "assets": [
        {"id": "one", "source": "original.png", "aspect_ratio": "3:4",
         "target_size": [192, 256], "output": {"image": "photo.jpg"}}
    ]})
    p = profile()
    engine = Engine(m, p, tmp_path, source_root)
    report = engine.run()
    assert report["asset_results"]["one"]["status"] == "accepted"
    assert not any(x["stage"] == "generation" for x in report["operations_detail"])
    engine.journal.close()
