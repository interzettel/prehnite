"""Offline API graph and localhost queue contracts for user-supplied ComfyUI.

These deliberately incomplete graph fixtures verify node mappings, not real
ComfyUI execution, checkpoint availability or RTX GPU feasibility.
"""
from __future__ import annotations

import io
from contextlib import contextmanager
from urllib.parse import urlencode
from pathlib import Path

import pytest
from PIL import Image

from prehnite.comfy import Comfy
from prehnite.schema import Endpoint

FIXTURES = Path(__file__).parent / "fixtures" / "comfy"


PROMPT_ID = "00000000-0000-4000-8000-000000000123"


class FakeResponse:
    def __init__(self, *, data=None, content=b""):
        self.data = data
        self.content = content
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self):
        yield self.content

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


class LocalComfyQueue:
    def __init__(self, png):
        self.png = png
        self.posts = []
        self.gets = []
        self.prompt_id = PROMPT_ID

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, *, json=None, files=None, data=None):
        self.posts.append((url, json, files is not None, data))
        if url.endswith("/prompt"):
            assert isinstance(json, dict) and "prompt" in json
            assert json.get("prompt_id") == PROMPT_ID
            return FakeResponse(data={"prompt_id": self.prompt_id})
        if url.endswith("/upload/image"):
            assert files and data["overwrite"] == "false"
            return FakeResponse(data={"name": "uploaded-input.png"})
        raise AssertionError(f"Unexpected mock POST: {url}")

    @contextmanager
    def stream(self, method, url, *, params=None, timeout=None):
        assert method == "GET" and url.endswith("/view")
        assert params["filename"] == "rendered.png"
        self.gets.append(url + "?" + urlencode(params))
        yield FakeResponse(content=self.png)

    def get(self, url, *, timeout=None):
        self.gets.append(url)
        if "/history/" in url:
            return FakeResponse(data={self.prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {"42": {"images": [{
                    "filename": "rendered.png", "subfolder": "", "type": "output"
                }]}}}})
        if "/view?" in url:
            return FakeResponse(content=self.png)
        raise AssertionError(f"Unexpected mock GET: {url}")


@pytest.fixture
def api(monkeypatch):
    image = Image.new("RGB", (128, 128), "plum")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    state = LocalComfyQueue(buf.getvalue())
    monkeypatch.setenv("PREHNITE_WORKFLOWS", str(FIXTURES))
    monkeypatch.setattr("prehnite.comfy.httpx.Client", lambda **kwargs: state)
    monkeypatch.setattr("prehnite.comfy.uuid.uuid4", lambda: PROMPT_ID)
    return state


def endpoint(kind: str, **opts):
    return Endpoint(provider="comfyui", model="user-owned-local-workflow",
                    options={"workflow": kind + "_api.json", **opts})


@pytest.mark.parametrize("ratio,tier,expected", [
    ("3:4", "2k", (1536, 2048)),
    ("9:16", "4k", (2304, 4096)),
    ("1:1", "4k", (4096, 4096)),
])
def test_generation_graph_maps_prompt_seed_and_requested_dimensions(
    api, tmp_path, ratio, tier, expected
):
    ep = endpoint("generate", prompt_node="6", seed_node="3", size_node="5")
    ids = []
    path = tmp_path / "photo.png"
    result = Comfy().generate("A cat at the window", ratio, tier, 129,
                              path, ep, ids.append)
    assert ids == [PROMPT_ID]
    assert result.provider_request_id == PROMPT_ID
    prompt_post = [item for item in api.posts if item[0].endswith("/prompt")]
    assert len(prompt_post) == 1
    graph = prompt_post[0][1]["prompt"]
    assert graph["6"]["inputs"]["text"] == "A cat at the window"
    assert graph["3"]["inputs"]["seed"] == 129
    assert (graph["5"]["inputs"]["width"], graph["5"]["inputs"]["height"]) == expected
    with Image.open(path) as image:
        assert image.size == (128, 128)  # Fixture isn't actual generated 4K.


@pytest.mark.parametrize("missing", ["prompt_node", "seed_node", "size_node"])
def test_invalid_generation_graph_mapping_fails_before_post(api, tmp_path, missing):
    mapping = {"prompt_node": "6", "seed_node": "3", "size_node": "5"}
    mapping.pop(missing)
    with pytest.raises(ValueError, match="valid node"):
        Comfy().generate("test", "3:4", "2k", 7, tmp_path/"out.png",
                         endpoint("generate", **mapping))
    assert api.posts == []


def test_upscale_validates_mapping_before_upload_and_reuses_prompt_id(api, tmp_path):
    input_path = tmp_path / "input.png"
    Image.new("RGB", (64, 64), "orange").save(input_path)
    ep = endpoint("upscale", input_node="10")
    result = Comfy().upscale(input_path, tmp_path / "out.png", ep)
    assert result.provider_request_id == PROMPT_ID
    assert len([x for x in api.posts if x[0].endswith("/upload/image")]) == 1
    post = next(x for x in api.posts if x[0].endswith("/prompt"))
    assert post[1]["prompt"]["10"]["inputs"]["image"] == "uploaded-input.png"
    api.posts.clear()
    Comfy().upscale(input_path, tmp_path/"out.png", ep, resume_id=PROMPT_ID)
    assert api.posts == []  # Resume checks history, never a new upload/submit.


def test_invalid_upscale_mapping_never_uploads_private_source(api, tmp_path):
    src = tmp_path / "private.png"
    Image.new("RGB", (64, 64), "gold").save(src)
    with pytest.raises(ValueError, match="valid node"):
        Comfy().upscale(src, tmp_path/"output.png",
                        endpoint("upscale", input_node="missing"))
    assert api.posts == []


def test_segmentation_maps_target_before_upload(api, tmp_path):
    src = tmp_path / "private.png"
    Image.new("RGB", (64, 64), "gold").save(src)
    Comfy().segment(src, "chair", tmp_path/"mask.png",
                    endpoint("segment", input_node="20", target_node="21"))
    post = next(x for x in api.posts if x[0].endswith("/prompt"))
    assert post[1]["prompt"]["20"]["inputs"]["image"] == "uploaded-input.png"
    assert post[1]["prompt"]["21"]["inputs"]["text"] == "chair"


@pytest.mark.parametrize("incorrect", [
    {"input_node": "missing", "target_node": "21"},
    {"input_node": "20", "target_node": "missing"},
])
def test_invalid_segment_nodes_cannot_trigger_upload(api, tmp_path, incorrect):
    src = tmp_path/"private.png"
    Image.new("RGB", (64, 64), "gold").save(src)
    with pytest.raises(ValueError, match="valid node"):
        Comfy().segment(src, "chair", tmp_path/"out.png",
                        endpoint("segment", **incorrect))
    assert api.posts == []


def test_comfy_rejects_workflow_outside_allowed_fixture_directory(api, tmp_path):
    bad = endpoint("generate", prompt_node="6", seed_node="3", size_node="5")
    bad.options["workflow"] = "../private.json"
    with pytest.raises(ValueError, match="Workflow name"):
        Comfy().generate("test", "3:4", "2k", 10, tmp_path/"out.png", bad)
    assert api.posts == []


@pytest.mark.parametrize("target_input,class_type", [
    ("prompt", "GroundingDinoSAM2Segment"),
    ("value", "PrimitiveString"),
])
def test_segmentation_uses_explicit_real_target_field_before_upload(
        api, tmp_path, monkeypatch, target_input, class_type):
    import json
    graphs = tmp_path / "workflow"
    graphs.mkdir()
    template = json.loads((FIXTURES / "segment_api.json").read_text())
    template["21"] = {"class_type": class_type, "inputs": {target_input: "old"}}
    (graphs / "segment_api.json").write_text(json.dumps(template), encoding="utf-8")
    monkeypatch.setenv("PREHNITE_WORKFLOWS", str(graphs))
    source = tmp_path / "private.png"
    Image.new("RGB", (64, 64), "navy").save(source)
    Comfy().segment(source, "ceramic lamp", tmp_path / "mask.png",
                    endpoint("segment", input_node="20", target_node="21",
                             target_input=target_input))
    assert len([x for x in api.posts if x[0].endswith("/upload/image")]) == 1
    sent = next(x[1]["prompt"] for x in api.posts if x[0].endswith("/prompt"))
    assert sent["21"]["inputs"][target_input] == "ceramic lamp"


@pytest.mark.parametrize("field", ["filename_prefix", "image", "", 5, True])
def test_invalid_or_disallowed_target_input_never_uploads(api, tmp_path, field):
    source = tmp_path / "private.png"
    Image.new("RGB", (64, 64), "navy").save(source)
    with pytest.raises(ValueError, match="target_input must be"):
        Comfy().segment(source, "lamp", tmp_path / "mask.png",
                        endpoint("segment", input_node="20", target_node="21",
                                 target_input=field))
    assert api.posts == []


def test_target_field_mismatch_refuses_private_upload(api, tmp_path):
    source = tmp_path / "private.png"
    Image.new("RGB", (64, 64), "navy").save(source)
    with pytest.raises(ValueError, match="no 'prompt' input"):
        Comfy().segment(source, "lamp", tmp_path / "mask.png",
                        endpoint("segment", input_node="20", target_node="21",
                                 target_input="prompt"))
    assert api.posts == []
