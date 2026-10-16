"""Zero-network API contract tests for supported fal image-generation workflows.

The fal module and downloader are stubs. They never contact fal.ai or spend
credits. Schemas are version-scoped snapshots, not a live provider certificate.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from prehnite import providers
from prehnite.providers import ESRGAN, FLUX3_IMAGE, FLUX3_KLEIN, Fal, fal_generation_inputs
from prehnite.schema import Endpoint


class FakeHandle:
    def __init__(self, request_id, response):
        self.request_id = request_id
        self.response = response

    def get(self, interval):
        assert interval == 1.0
        return self.response


class FakeFalClient:
    def __init__(self):
        self.submissions = []
        self.lookups = []
        self.uploads = []
        self.output = {"images": [{
            "url": "https://v3b.fal.media/files/mock/generated.png",
            "content_type": "image/png", "width": 192, "height": 256,
        }], "seed": 17, "timings": {"inference": 0.25}}
        self.upscaled = {"image": {
            "url": "https://v3b.fal.media/files/mock/upscaled.png",
            "width": 192, "height": 256}}
        self.masks = {"masks": [{
            "url": "https://v3b.fal.media/files/mock/mask.png"}]}
        self.invalid_id = False

    def submit(self, endpoint, arguments):
        self.submissions.append((endpoint, arguments))
        result = self.upscaled if endpoint == ESRGAN else (
            self.masks if endpoint == "fal-ai/sam-3-1/image" else self.output
        )
        return FakeHandle(None if self.invalid_id else "queue-opaque-1", result)

    def get_handle(self, endpoint, request_id):
        self.lookups.append((endpoint, request_id))
        assert request_id == "queue-opaque-1"
        result = self.upscaled if endpoint == ESRGAN else (
            self.masks if endpoint == "fal-ai/sam-3-1/image" else self.output
        )
        return FakeHandle(request_id, result)

    def upload_file(self, filename):
        self.uploads.append(filename)
        return "https://v3b.fal.media/files/mock/input.png"


@pytest.fixture
def fal_stub(monkeypatch):
    stub = FakeFalClient()
    monkeypatch.setitem(sys.modules, "fal_client", stub)
    monkeypatch.setenv("FAL_KEY", "unit-test-only-not-a-real-key")
    downloads = []

    def save_fixture_image(url, destination):
        assert url.startswith("https://v3b.fal.media/")
        downloads.append(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if "mask.png" in url:
            from PIL import ImageDraw
            mask = Image.new("L", (192, 256), 0)
            ImageDraw.Draw(mask).ellipse((20, 30, 170, 200), fill=255)
            mask.save(destination)
        else:
            Image.new("RGB", (192, 256), "olive").save(destination)

    monkeypatch.setattr(providers, "download_image", save_fixture_image)
    return stub, downloads


@pytest.mark.parametrize("ratio,expected", [
    ("9:16", (1152, 2048)), ("3:4", (1536, 2048)),
    ("4:3", (2048, 1536)), ("16:9", (2048, 1152)),
    ("1:1", (2048, 2048)),
])
def test_klein_2k_image_size_schema(ratio, expected):
    ep = Endpoint(provider="fal", model=FLUX3_KLEIN)
    payload = fal_generation_inputs(ep, "A cafe", ratio, "2k", 8)
    assert payload["image_size"] == dict(zip(("width", "height"), expected))
    assert payload["seed"] == 8
    assert payload["output_format"] == "png"
    assert "resolution" not in payload
    assert "aspect_ratio" not in payload


@pytest.mark.parametrize("tier,factor", [("2k", 1), ("4k", 2)])
def test_klein_tier_doubles_long_edge(tier, factor):
    ep = Endpoint(provider="fal", model=FLUX3_KLEIN)
    payload = fal_generation_inputs(ep, "A cafe", "9:16", tier, 8)
    assert payload["image_size"] == {"width": 1152*factor, "height": 2048*factor}


def test_flux3_image_uses_different_schema_and_does_not_invent_seed_support():
    ep = Endpoint(provider="fal", model=FLUX3_IMAGE)
    payload = fal_generation_inputs(ep, "A mountain", "3:4", "4k", 17)
    assert payload["aspect_ratio"] == "3:4"
    assert payload["resolution"] == "4k"
    assert "image_size" not in payload
    # Full FLUX 3 docs do not currently advertise a seed argument.
    assert "seed" not in payload


@pytest.mark.parametrize("bad_model,bad_ratio,bad_tier", [
    ("fal-ai/some-unknown-model", "3:4", "2k"),
    (FLUX3_KLEIN, "5:9", "2k"),
    (FLUX3_KLEIN, "3:4", "8k"),
])
def test_incompatible_generation_models_or_options_fail_before_submit(
    fal_stub, tmp_path, bad_model, bad_ratio, bad_tier
):
    stub, _ = fal_stub
    with pytest.raises(ValueError):
        Fal().generate("test", bad_ratio, bad_tier, 7, tmp_path/"x.png",
                       Endpoint(provider="fal", model=bad_model))
    assert stub.submissions == []


def test_generation_submission_and_resume_use_one_request(fal_stub, tmp_path):
    stub, downloaded = fal_stub
    ep = Endpoint(provider="fal", model=FLUX3_KLEIN)
    submitted = []
    path = tmp_path/"a.png"
    result = Fal().generate("scene", "9:16", "2k", 17, path, ep, submitted.append)
    assert result.provider_request_id == "queue-opaque-1"
    assert result.metadata["seed"] == 17
    assert submitted == ["queue-opaque-1"]
    assert len(stub.submissions) == 1
    assert len(downloaded) == 1
    assert stub.submissions[0][1]["image_size"] == {"width": 1152, "height": 2048}

    # Resume may perform result retrieval again, never a second submit.
    again = Fal().generate("scene", "9:16", "2k", 17, path, ep,
                           lambda _: pytest.fail("Resubmitted paid request"),
                           "queue-opaque-1")
    assert again.provider_request_id == "queue-opaque-1"
    assert stub.lookups == [(FLUX3_KLEIN, "queue-opaque-1")]
    assert len(stub.submissions) == 1


def test_esrgan_input_contract_and_no_source_upload_on_resume(
    fal_stub, tmp_path
):
    stub, downloaded = fal_stub
    image = tmp_path/"original.png"
    Image.new("RGB", (64, 64), "red").save(image)
    ep = Endpoint(provider="fal", model=ESRGAN, options={"model": "RealESRGAN_x2plus"})
    out = tmp_path/"larger.png"
    Fal().upscale(image, out, ep, lambda _: None)
    assert len(stub.uploads) == 1
    endpoint, payload = stub.submissions[0]
    assert endpoint == ESRGAN
    assert payload == {
        "image_url": "https://v3b.fal.media/files/mock/input.png",
        "scale": 2, "model": "RealESRGAN_x2plus", "output_format": "png",
    }
    Fal().upscale(image, out, ep, resume_id="queue-opaque-1")
    assert len(stub.uploads) == 1
    assert len(stub.submissions) == 1
    assert stub.lookups == [(ESRGAN, "queue-opaque-1")]
    assert len(downloaded) == 2


def test_segment_resume_never_reuploads_private_source(fal_stub, tmp_path):
    stub, _ = fal_stub
    src = tmp_path/"source.png"
    Image.new("RGB", (192, 256), "blue").save(src)
    ep = Endpoint(provider="fal", model="fal-ai/sam-3-1/image")
    Fal().segment(src, "person", tmp_path/"mask.png", ep, lambda _: None)
    assert len(stub.uploads) == 1
    Fal().segment(src, "person", tmp_path/"mask.png", ep,
                  resume_id="queue-opaque-1")
    assert len(stub.uploads) == 1
    assert len(stub.submissions) == 1


def test_missing_key_blocks_upscale_before_upload(fal_stub, monkeypatch, tmp_path):
    stub, _ = fal_stub
    monkeypatch.delenv("FAL_KEY")
    with pytest.raises(RuntimeError, match="FAL_KEY"):
        Fal().upscale(tmp_path/"private.png", tmp_path/"out.png",
                      Endpoint(provider="fal", model=ESRGAN))
    assert stub.uploads == []
    assert stub.submissions == []


def test_missing_remote_request_id_is_ambiguous_not_success(fal_stub, tmp_path):
    stub, _ = fal_stub
    stub.invalid_id = True
    callbacks = []
    with pytest.raises(ValueError, match="request ID"):
        Fal().generate("scene", "3:4", "2k", 4, tmp_path/"x.png",
                       Endpoint(provider="fal", model=FLUX3_KLEIN),
                       callbacks.append)
    assert len(stub.submissions) == 1
    assert callbacks == []


@pytest.mark.parametrize("invalid", [{}, {"images": []},
                                      {"images": [{"invalid": "payload"}]},
                                      {"images": "not-an-image"}, None])
def test_malformed_generation_response_fails_closed(fal_stub, tmp_path, invalid):
    stub, downloaded = fal_stub
    stub.output = invalid
    with pytest.raises(ValueError, match="response|image URL"):
        Fal().generate("scene", "3:4", "2k", 5, tmp_path/"x.png",
                       Endpoint(provider="fal", model=FLUX3_KLEIN))
    assert downloaded == []


@pytest.mark.parametrize("bad_url", [
    "http://v3b.fal.media/file.png",
    "https://fal.media.evil.example/file.png",
    "https://evil.example/file.png",
    "file:///tmp/test.png",
])
def test_artifact_host_allowlist_rejects_untrusted_urls_without_network(tmp_path, bad_url):
    with pytest.raises(ValueError, match="non-fal"):
        providers.download_image(bad_url, tmp_path/"x.png")
    assert not (tmp_path/"x.png").exists()

def test_two_sam_masks_rejected_instead_of_guessing_first(fal_stub, tmp_path):
    stub, downloaded = fal_stub
    source = tmp_path / "source.png"
    Image.new("RGB", (192, 256), "teal").save(source)
    stub.masks = {"masks": [
        {"url": "https://v3b.fal.media/files/mock/mask.png"},
        {"url": "https://v3b.fal.media/files/mock/mask2.png"},
    ]}
    with pytest.raises(ValueError, match="exactly one"):
        Fal().segment(source, "person", tmp_path / "out.png",
                      Endpoint(provider="fal", model="fal-ai/sam-3-1/image"))
    assert downloaded == []


def test_sam_result_records_mask_geometry(fal_stub, tmp_path):
    stub, downloaded = fal_stub
    source = tmp_path / "source.png"
    Image.new("RGB", (192, 256), "teal").save(source)
    outcome = Fal().segment(source, "person", tmp_path / "mask.png",
                            Endpoint(provider="fal", model="fal-ai/sam-3-1/image"))
    assert outcome.metadata["mask_validation"]["width"] == 192
    assert outcome.metadata["mask_validation"]["height"] == 256
    assert len(stub.uploads) == 1
    assert len(downloaded) == 1
