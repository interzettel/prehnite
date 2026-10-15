from pathlib import Path
import json
import pytest

from prehnite.comfy import _base_url, graph_file, put_node
from prehnite.schema import Endpoint


def endpoint(**opts):
    return Endpoint(provider="comfyui", model="test", options=opts)


def test_restricts_remote_comfyui():
    with pytest.raises(ValueError):
        _base_url(endpoint(base_url="http://evil.example.com:8188"))


def test_workflow_path_is_allowlisted(monkeypatch, tmp_path):
    monkeypatch.setenv("PREHNITE_WORKFLOWS", str(tmp_path))
    (tmp_path/"test.json").write_text(json.dumps({
        "1": {"inputs": {"text": "old"}}}))
    graph = graph_file(endpoint(workflow="test.json"))
    put_node(graph, "1", "text", "new")
    assert graph["1"]["inputs"]["text"] == "new"
    with pytest.raises(ValueError):
        graph_file(endpoint(workflow="../another.json"))


def test_missing_input_rejected():
    with pytest.raises(ValueError):
        put_node({"3": {"inputs": {"seed": 1}}}, "3", "width", 512)
