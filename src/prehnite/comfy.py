"""ComfyUI API adapter (local process; workflow authored separately in ComfyUI).

Requires a workflow exported in API format and explicit node/input mappings.
No ComfyUI, model weights or GPL code is bundled in Prehnite.
"""
from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx
from PIL import Image

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

    def _render(self, graph: dict, endpoint: Endpoint, output: Path,
                on_submit=None, resume_id=None) -> Result:
        base = _base_url(endpoint)
        timeout = float(endpoint.options.get("timeout_seconds", 2400))
        start = time.monotonic()
        with httpx.Client(timeout=40) as client:
            if resume_id:
                prompt_id = resume_id
            else:
                response = client.post(base + "/prompt", json={"prompt": graph})
                response.raise_for_status()
                data = response.json()
                prompt_id = data.get("prompt_id")
                if not prompt_id:
                    raise ValueError(f"ComfyUI rejected graph: {data}")
                if on_submit:
                    on_submit(str(prompt_id))
            while True:
                response = client.get(base + "/history/" + str(prompt_id))
                response.raise_for_status()
                history = response.json().get(str(prompt_id))
                if history:
                    status = history.get("status", {})
                    if status.get("status_str") == "error":
                        raise RuntimeError("ComfyUI reported execution failure")
                    images = []
                    for value in history.get("outputs", {}).values():
                        images.extend(value.get("images", []))
                    if images:
                        file = images[0]
                        query = urlencode({"filename": file["filename"],
                                           "subfolder": file.get("subfolder", ""),
                                           "type": file.get("type", "output")})
                        r = client.get(base + "/view?" + query, timeout=120)
                        r.raise_for_status()
                        if len(r.content) > 100_000_000:
                            raise ValueError("ComfyUI output is too large")
                        output.parent.mkdir(parents=True, exist_ok=True)
                        output.write_bytes(r.content)
                        with Image.open(output) as im:
                            im.verify()
                        return Result(output, str(prompt_id),
                                      {"comfyui_prompt_id": str(prompt_id),
                                       "workflow": endpoint.options.get("workflow")})
                if time.monotonic() - start > timeout:
                    raise TimeoutError("ComfyUI prompt still pending; resume using prompt ID")
                time.sleep(1.5)

    def generate(self, prompt: str, aspect_ratio: str, tier: str, seed: int,
                 output: Path, endpoint: Endpoint, on_submit=None,
                 resume_id=None) -> Result:
        graph = graph_file(endpoint)
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
        graph = graph_file(endpoint)
        if not resume_id:
            # Check the graph mapping before uploading private bytes, even to
            # localhost. The adapter should fail before observable side effects.
            put_node(graph, endpoint.options.get("input_node"), "image", "__preflight__")
            name = self._upload(source, endpoint)
            put_node(graph, endpoint.options.get("input_node"), "image", name)
        return self._render(graph, endpoint, output, on_submit, resume_id)

    def segment(self, source: Path, target: str, output: Path, endpoint: Endpoint,
                on_submit=None, resume_id=None) -> Result:
        graph = graph_file(endpoint)
        if not resume_id:
            # Fail fast on *both* node mappings before sending an image upload.
            put_node(graph, endpoint.options.get("input_node"), "image", "__preflight__")
            put_node(graph, endpoint.options.get("target_node"), "text", target)
            name = self._upload(source, endpoint)
            put_node(graph, endpoint.options.get("input_node"), "image", name)
        return self._render(graph, endpoint, output, on_submit, resume_id)
