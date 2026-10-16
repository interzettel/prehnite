"""ComfyUI queue/restart hardening tests through an in-memory HTTP transport.

No ComfyUI server, external network, model weights or GPU is required.
"""
from __future__ import annotations

import io
import json
import itertools
from pathlib import Path

import httpx
import pytest
from PIL import Image

import prehnite.comfy as comfy
from prehnite.comfy import Comfy
from prehnite.schema import Endpoint

ID = "a45aab1e-ea83-46f9-ac38-5bb22ec9ec19"


def sample_png():
    image = Image.new("RGB", (64, 80), "plum")
    memory = io.BytesIO()
    image.save(memory, "PNG")
    return memory.getvalue()


class Queue:
    def __init__(self):
        self.posts = []
        self.gets = []
        self.history = {"status": {"status_str": "success"}, "outputs": {
            "42": {"images": [{"filename": "done.png", "subfolder": "",
                                "type": "output"}]}}}
        self.png = sample_png()
        self.headers = {}
        self.fail_submit = False

    def __call__(self, request):
        self.gets.append(str(request.url))
        if request.url.path == "/prompt":
            body = json.loads(request.content)
            self.posts.append(body)
            assert body["prompt_id"] == ID
            if self.fail_submit:
                raise httpx.ConnectError("Connection lost after potential submit")
            return httpx.Response(200, json={"prompt_id": ID})
        if request.url.path == "/history/" + ID:
            return httpx.Response(200, json=({ID: self.history}
                                             if self.history is not None else {}))
        if request.url.path == "/view":
            return httpx.Response(200, headers=self.headers, content=self.png)
        raise AssertionError(f"Unexpected local HTTP request {request.url}")


@pytest.fixture
def fake(monkeypatch):
    queue = Queue()
    real_client = httpx.Client
    monkeypatch.setattr(comfy.httpx, "Client",
                        lambda **kw: real_client(transport=httpx.MockTransport(queue), **kw))
    monkeypatch.setattr(comfy.uuid, "uuid4", lambda: ID)
    return queue


def ep(**options):
    return Endpoint(provider="comfyui", model="owner-workflow",
                    options={"timeout_seconds": 0.05, **options})


def test_queue_id_is_journaled_before_http_and_recovery_never_reposts(fake, tmp_path):
    fake.fail_submit = True
    recorded = []
    output = tmp_path / "image.png"
    with pytest.raises(httpx.ConnectError):
        Comfy()._render({"1": {"inputs": {}}}, ep(), output, recorded.append)
    assert recorded == [ID]
    assert len(fake.posts) == 1
    assert fake.posts[0]["prompt_id"] == recorded[0]
    fake.fail_submit = False
    recovered = Comfy()._render(None, ep(), output, lambda _: pytest.fail("requeued"), ID)
    assert recovered.provider_request_id == ID
    assert len(fake.posts) == 1
    with Image.open(output) as result:
        assert result.size == (64, 80)


def test_resume_does_not_require_deleted_graph_fixture(fake, tmp_path, monkeypatch):
    monkeypatch.setenv("PREHNITE_WORKFLOWS", str(tmp_path))
    result = Comfy().generate("any", "3:4", "2k", 5,
                              tmp_path / "out.png",
                              ep(workflow="deleted.json"),
                              resume_id=ID)
    assert result.provider_request_id == ID
    assert fake.posts == []


@pytest.mark.parametrize("state", ["error", "failed", "interrupted",
                                     "cancelled", "canceled", "aborted"])
def test_terminal_bad_history_states_never_requeue(fake, tmp_path, state):
    fake.history = {"status": {"status_str": state}, "outputs": {}}
    with pytest.raises(RuntimeError, match=state):
        Comfy()._render(None, ep(), tmp_path / "x.png", resume_id=ID)
    assert fake.posts == []


def test_pending_history_timeout_never_requeues(fake, tmp_path, monkeypatch):
    fake.history = None
    clocks = itertools.count(0, 0.02)
    monkeypatch.setattr(comfy.time, "monotonic", lambda: next(clocks))
    monkeypatch.setattr(comfy.time, "sleep", lambda _: None)
    with pytest.raises(TimeoutError, match="resume using prompt ID"):
        Comfy()._render(None, ep(), tmp_path / "x.png", resume_id=ID)
    assert fake.posts == []
    assert len([u for u in fake.gets if "/history/" in u]) >= 2


def test_success_without_image_is_error_not_infinite_poll(fake, tmp_path):
    fake.history = {"status": {"status_str": "success"}, "outputs": {}}
    with pytest.raises(ValueError, match="exactly one"):
        Comfy()._render(None, ep(), tmp_path / "x.png", resume_id=ID)


def test_output_node_resolves_multi_output_ambiguity(fake, tmp_path):
    fake.history["outputs"]["43"] = {"images": [
        {"filename": "other.png", "subfolder": "", "type": "output"}]}
    with pytest.raises(ValueError, match="exactly one"):
        Comfy()._render(None, ep(), tmp_path / "x.png", resume_id=ID)
    result = Comfy()._render(None, ep(output_node="42"), tmp_path / "x.png", resume_id=ID)
    assert result.provider_request_id == ID


@pytest.mark.parametrize("filename,subfolder,kind", [
    ("../escape.png", "", "output"),
    ("bad\\name.png", "", "output"),
    ("valid.png", "../private", "output"),
    ("valid.png", "C:/secret", "output"),
    ("valid.png", "", "input"),
    ("valid.svg", "", "output"),
])
def test_invalid_file_descriptors_rejected_without_fetch(fake, tmp_path,
                                                          filename, subfolder, kind):
    fake.history["outputs"]["42"]["images"] = [{
        "filename": filename, "subfolder": subfolder, "type": kind}]
    with pytest.raises(ValueError):
        Comfy()._render(None, ep(), tmp_path / "x.png", resume_id=ID)
    assert not any("/view?" in s for s in fake.gets)


def test_large_output_content_length_rejected_without_publishing(fake, tmp_path):
    fake.headers = {"Content-Length": "100000001"}
    out = tmp_path / "x.png"
    with pytest.raises(ValueError, match="too large"):
        Comfy()._render(None, ep(), out, resume_id=ID)
    assert not out.exists()


def test_stream_byte_limit_and_existing_output_preserved(fake, monkeypatch, tmp_path):
    fake.png = sample_png()
    monkeypatch.setattr(comfy, "MAX_IMAGE_BYTES", 8)
    out = tmp_path / "x.png"
    old = sample_png()
    out.write_bytes(old)
    with pytest.raises(ValueError, match="too large"):
        Comfy()._render(None, ep(), out, resume_id=ID)
    assert out.read_bytes() == old
    assert not list(tmp_path.glob(".prehnite-*.png"))


def test_invalid_image_payload_is_never_published(fake, tmp_path):
    fake.png = b"not image data"
    out = tmp_path / "image.png"
    with pytest.raises((OSError, ValueError)):
        Comfy()._render(None, ep(), out, resume_id=ID)
    assert not out.exists()
    assert not list(tmp_path.glob(".prehnite-*.png"))


@pytest.mark.parametrize("bad", ["../../etc/passwd", "foo?bar", "", "wrong/id"])
def test_unsafe_resume_id_rejected_before_network(fake, tmp_path, bad):
    with pytest.raises(ValueError, match="prompt ID"):
        Comfy()._render(None, ep(), tmp_path / "x.png", resume_id=bad)
    assert fake.gets == []
