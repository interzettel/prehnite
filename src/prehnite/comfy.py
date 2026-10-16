"""ComfyUI API adapter (local process; workflow authored separately in ComfyUI).

Requires a workflow exported in API format and explicit node/input mappings.
No ComfyUI, model weights or GPL code is bundled in Prehnite.
"""
from __future__ import annotations

import copy
import json
import os
import math
import re
import uuid
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from .artifacts import temporary_sibling
from .images import image_info
from .schema import relative_name
from PIL import Image

MAX_IMAGE_BYTES = 100_000_000
MAX_DECODED_PIXELS = 24_000_000

from .providers import Result
from .schema import Endpoint


SIZES = {
    "9:16": (1152, 2048), "3:4": (1536, 2048),
    "4:3": (2048, 1536), "16:9": (2048, 1152),
    "1:1": (2048, 2048),
}


def graph_file(endpoint: Endpoint) -> dict:
    name = endpoint.options.get("workflow")
    if not isinstance(name, str) or not name.endswith(".json"):
        raise ValueError("ComfyUI requires a workflow JSON filename in options.workflow")
    if "/" in name or "\\" in name or name.startswith("."):
        raise ValueError("Workflow name must be a file inside PREHNITE_WORKFLOWS")
    root = Path(os.environ.get("PREHNITE_WORKFLOWS", "./workflows")).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"ComfyUI API workflow not found: {name}")
    graph = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or not graph:
        raise ValueError("Not an API-format ComfyUI workflow")
    return graph


def put_node(graph: dict, node: str | int | None, key: str, value) -> None:
    if node is None or str(node) not in graph:
        raise ValueError(f"ComfyUI graph requires valid node for {key}")
    inputs = graph[str(node)].get("inputs")
    if not isinstance(inputs, dict) or key not in inputs:
        raise ValueError(f"ComfyUI node {node} has no '{key}' input")
    inputs[key] = value


def _base_url(endpoint: Endpoint) -> str:
    raw = str(endpoint.options.get("base_url", "http://127.0.0.1:8188")).rstrip("/")
    url = urlparse(raw)
    if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost"):
        raise ValueError("ComfyUI can connect only to local HTTP loopback")
    return raw


class Comfy:
    """Queue/history API, explicit workflow node mappings and persistent prompt IDs."""

    def _render(self, graph: dict | None, endpoint: Endpoint, output: Path,
                on_submit=None, resume_id=None) -> Result:
        base = _base_url(endpoint)
        timeout = float(endpoint.options.get("timeout_seconds", 2400))
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 86400:
            raise ValueError("ComfyUI timeout_seconds must be within (0, 86400]")
        start = time.monotonic()
        # An ID is created AND journaled *before* the request can reach a
        # local ComfyUI queue. If the connection dies midway, resume looks up
        # this same ID. A missing history record is never a reason to requeue.
        prompt_id = str(resume_id) if resume_id else str(uuid.uuid4())
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", prompt_id):
            raise ValueError("Invalid ComfyUI prompt ID")
        with httpx.Client(timeout=40) as client:
            if not resume_id:
                if not graph:
                    raise ValueError("ComfyUI requires an API workflow to submit")
                if on_submit:
                    on_submit(prompt_id)
                response = client.post(
                    base + "/prompt",
                    json={"prompt": graph, "prompt_id": prompt_id},
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or data.get("prompt_id") != prompt_id:
                    raise ValueError("ComfyUI queue response did not confirm the requested prompt ID")
            while True:
                response = client.get(base + "/history/" + prompt_id)
                response.raise_for_status()
                content = response.json()
                if not isinstance(content, dict):
                    raise ValueError("ComfyUI history response must be an object")
                history = content.get(prompt_id)
                if history is not None:
                    if not isinstance(history, dict):
                        raise ValueError("Invalid ComfyUI history record")
                    status = history.get("status", {})
                    if not isinstance(status, dict):
                        raise ValueError("Invalid ComfyUI execution status")
                    state = status.get("status_str")
                    if state in ("error", "failed", "interrupted", "cancelled", "canceled", "aborted"):
                        raise RuntimeError(f"ComfyUI prompt {prompt_id} ended with {state}")
                    if state == "success" or status.get("completed") is True:
                        outputs = history.get("outputs", {})
                        if not isinstance(outputs, dict):
                            raise ValueError("Invalid ComfyUI output mapping")
                        output_node = endpoint.options.get("output_node")
                        if output_node is not None:
                            if not isinstance(output_node, (str, int)):
                                raise ValueError("ComfyUI output_node must be a node ID")
                            outputs = {str(output_node): outputs.get(str(output_node))}
                        images = []
                        for value in outputs.values():
                            if not isinstance(value, dict):
                                raise ValueError("Invalid ComfyUI image output")
                            entries = value.get("images", [])
                            if not isinstance(entries, list):
                                raise ValueError("Invalid ComfyUI images list")
                            images.extend(entries)
                        if len(images) != 1:
                            raise ValueError("ComfyUI must return exactly one selected image")
                        file = images[0]
                        if not isinstance(file, dict):
                            raise ValueError("Invalid ComfyUI file descriptor")
                        filename = file.get("filename")
                        subfolder = file.get("subfolder", "")
                        filetype = file.get("type", "output")
                        if (not isinstance(filename, str) or
                                relative_name(filename) != filename or
                                "/" in filename or
                                not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))):
                            raise ValueError("Unsafe ComfyUI output filename")
                        if not isinstance(subfolder, str) or (subfolder and
                                relative_name(subfolder) != subfolder):
                            raise ValueError("Unsafe ComfyUI output subfolder")
                        if filetype != "output":
                            raise ValueError("ComfyUI only accepts saved output images")
                        # Streaming keeps an unexpectedly large local image from
                        # consuming arbitrary memory. The output is published
                        # only after full Pillow decoding and size validation.
                        with temporary_sibling(output) as staged:
                            size = 0
                            with client.stream(
                                "GET", base + "/view",
                                params={"filename": filename, "subfolder": subfolder,
                                        "type": filetype},
                                timeout=120,
                            ) as download:
                                download.raise_for_status()
                                header = download.headers.get("content-length")
                                if header is not None and int(header) > MAX_IMAGE_BYTES:
                                    raise ValueError("ComfyUI output is too large")
                                with staged.open("wb") as sink:
                                    for block in download.iter_bytes():
                                        size += len(block)
                                        if size > MAX_IMAGE_BYTES:
                                            raise ValueError("ComfyUI output is too large")
                                        sink.write(block)
                            info = image_info(staged)
                            if info["width"] * info["height"] > MAX_DECODED_PIXELS:
                                raise ValueError("ComfyUI output exceeds the decoded pixel limit")
                            with Image.open(staged) as decoded:
                                decoded.load()
                            os.replace(staged, output)
                        return Result(output, prompt_id,
                                      {"comfyui_prompt_id": prompt_id,
                                       "workflow": endpoint.options.get("workflow")})
                    if state not in (None, "pending", "running", "queued", "executing"):
                        raise ValueError(f"Unknown ComfyUI execution status: {state!r}")
                if time.monotonic() - start >= timeout:
                    raise TimeoutError("ComfyUI prompt still pending; resume using prompt ID")
                time.sleep(min(1.5, timeout))

    def generate(self, prompt: str, aspect_ratio: str, tier: str, seed: int,
                 output: Path, endpoint: Endpoint, on_submit=None,
                 resume_id=None) -> Result:
        graph = None if resume_id else graph_file(endpoint)
        if not resume_id:
            options = endpoint.options
            put_node(graph, options.get("prompt_node"), "text", prompt)
            put_node(graph, options.get("seed_node"), str(options.get("seed_input", "seed")),
                     seed)
            w, h = SIZES[aspect_ratio]
            if tier == "4k":
                w, h = w * 2, h * 2
            put_node(graph, options.get("size_node"), "width", w)
            put_node(graph, options.get("size_node"), "height", h)
        return self._render(graph, endpoint, output, on_submit, resume_id)

    def _upload(self, source: Path, endpoint: Endpoint) -> str:
        base = _base_url(endpoint)
        with httpx.Client(timeout=120) as client:
            with source.open("rb") as f:
                response = client.post(base + "/upload/image",
                                       files={"image": (source.name, f, "image/png")},
                                       data={"overwrite": "false", "type": "input"})
            response.raise_for_status()
            result = response.json()
            if not result.get("name"):
                raise ValueError("ComfyUI did not return uploaded image name")
            return str(result["name"])

    def upscale(self, source: Path, output: Path, endpoint: Endpoint,
                on_submit=None, resume_id=None) -> Result:
        graph = None if resume_id else graph_file(endpoint)
        if not resume_id:
            # Check the graph mapping before uploading private bytes, even to
            # localhost. The adapter should fail before observable side effects.
            put_node(graph, endpoint.options.get("input_node"), "image", "__preflight__")
            name = self._upload(source, endpoint)
            put_node(graph, endpoint.options.get("input_node"), "image", name)
        return self._render(graph, endpoint, output, on_submit, resume_id)

    def segment(self, source: Path, target: str, output: Path, endpoint: Endpoint,
                on_submit=None, resume_id=None) -> Result:
        graph = None if resume_id else graph_file(endpoint)
        if not resume_id:
            # Fail fast on *both* node mappings before sending an image upload.
            put_node(graph, endpoint.options.get("input_node"), "image", "__preflight__")
            put_node(graph, endpoint.options.get("target_node"), "text", target)
            name = self._upload(source, endpoint)
            put_node(graph, endpoint.options.get("input_node"), "image", name)
        return self._render(graph, endpoint, output, on_submit, resume_id)
