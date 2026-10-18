"""#159 resource observations feeding #161 cutout QA without authorization."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from prehnite.cutout_quality import run_cutout_qa
from prehnite.resource_readiness import ReadinessPolicy, evaluate_readiness

MIB = 1024 * 1024


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(*, available: int = 4096, commit_used: int = 100,
             commit_limit: int = 1000, vram_free: int = 4096,
             ram_status: str = "observed", nvidia_status: str = "observed"):
    return {
        "ram": {
            "status": ram_status,
            "available_bytes": available * MIB,
            "commit_status": "observed",
            "commit_used_bytes": commit_used * MIB,
            "commit_limit_bytes": commit_limit * MIB,
            "source": "test",
            "commit_source": "test",
        },
        "accelerators": {
            "nvidia": {
                "status": nvidia_status,
                "source": "test",
                "devices": [{
                    "index": 0,
                    "vram_free_bytes": vram_free * MIB,
                    "vram_status": "observed",
                }],
            }
        },
    }


def write_observation(tmp_path: Path, name: str, snapshots) -> Path:
    path = tmp_path / f"{name}.json"
    report = evaluate_readiness(
        snapshots,
        ReadinessPolicy(min_available_ram_mib=1024, max_commit_percent=80,
                        min_free_vram_mib=1024),
    )
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def write_cutout_fixture(tmp_path: Path):
    source = tmp_path / "source.png"
    image = Image.new("RGB", (96, 128), (240, 230, 220))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 20, 72, 70), fill=(220, 190, 130))
    draw.rectangle((44, 70, 52, 110), fill=(120, 95, 70))
    draw.ellipse((20, 105, 78, 126), fill=(110, 85, 62))
    image.save(source)
    mask = tmp_path / "mask.png"
    m = Image.new("L", (96, 128), 0)
    d = ImageDraw.Draw(m)
    d.rectangle((24, 20, 72, 70), fill=255)
    d.rectangle((44, 70, 52, 110), fill=255)
    d.ellipse((20, 105, 78, 126), fill=255)
    m.save(mask)
    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps({
        "1": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
        "4": {"class_type": "Segment", "inputs": {"image": ["1", 0], "prompt": "widget"}},
        "6": {"class_type": "SaveImage", "inputs": {"images": ["4", 0]}},
    }), encoding="utf-8")
    model = tmp_path / "model.pth"
    model.write_bytes(b"integration-fixture-model")
    recipe = {
        "schema_version": 1,
        "source": {"name": "source.png", "sha256": digest(source)},
        "target": {"id": "widget", "phrase": "a single widget",
                   "include": ["widget body"], "exclude": ["background"]},
        "workflow": {"path": "workflow.json", "sha256": digest(workflow),
                      "input_node": "1", "target_node": "4",
                      "target_input": "prompt", "output_node": "6"},
        "models": [{"role": "detector", "path": "model.pth",
                    "sha256": digest(model)}],
        "alpha_candidates": [{"id": "candidate-a", "sigma_px": 0.65}],
        "qa": {"max_partial_alpha_fraction": 0.10},
    }
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    return source, mask, recipe_path


@pytest.mark.parametrize(("name", "snapshots", "expected"), [
    ("pass", [snapshot()], "passed"),
    ("blocked", [snapshot(available=0)], "blocked"),
    ("unknown", [snapshot(nvidia_status="unknown")], "unverified"),
])
def test_resource_observation_flows_into_cutout_qa(tmp_path, name, snapshots, expected):
    source, mask, recipe_path = write_cutout_fixture(tmp_path)
    observation = write_observation(tmp_path, name, snapshots)
    report_path = run_cutout_qa(
        recipe_path, source=source, mask=mask, workflow_root=tmp_path,
        models_root=tmp_path, output_dir=tmp_path / f"out-{name}",
        resource_readiness=observation,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["stages"]["resource_readiness"]["status"] == expected
    assert report["resource_observation"]["observation_status"] == name
    assert report["resource_observation"]["startup_authorized"] is False
    # Neither resource passing nor mask decoding may masquerade as inference.
    assert report["stages"]["dependency_compatibility"]["status"] == "unverified"
    assert report["stages"]["technical_execution"]["status"] == "unverified"
    assert report["visual_acceptance"] == "not_recorded"
    assert report["owner_final_acceptance"] == "not_recorded"
