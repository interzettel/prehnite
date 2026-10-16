"""Privacy-safe, deterministic provenance from zero-cost demo batches."""
from __future__ import annotations

import hashlib
import json

import pytest
from PIL import Image

from prehnite.artifacts import ArtifactIntegrityError
from prehnite.engine import Engine
from prehnite.provenance import build_provenance, export_provenance
from prehnite.schema import Manifest, Profile


def job(*, source=False, batch_id="trace-batch"):
    asset = {
        "id": "sample", "aspect_ratio": "3:4", "target_size": [192, 256],
        "output": {"image": "approved/portrait.png"},
    }
    if source:
        asset["source"] = "private-original.png"
    else:
        asset["prompt"] = "PRIVATE CLIENT PROMPT about a unique unreleased product"
    manifest = Manifest.model_validate({"id": batch_id, "assets": [asset]})
    profile = Profile.model_validate({
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "variants": ["native_4k"],
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
    })
    return manifest, profile


def test_prompt_provenance_has_output_hash_and_trace_without_private_text(tmp_path):
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        report = engine.run()
        assert report["asset_results"]["sample"]["status"] == "accepted"
        path = engine.journal.root / "provenance.json"
        assert path.is_file()
        first = path.read_bytes()
        raw = first.decode("utf-8")
        assert "PRIVATE CLIENT PROMPT" not in raw
        assert str(tmp_path) not in raw
        assert "FAL_KEY" not in raw
        data = json.loads(raw)
        assert data["schema_version"] == 1
        assert data["configuration_sha256"] == engine.journal.fact("configuration_sha256")
        assert data["cost_is_actual_invoice"] is False
        assert data["cost_estimated_or_reserved_usd"] == 0
        row = data["inputs_and_outputs"][0]
        assert row["input_kind"] == "prompt"
        assert row["prompt_sha256"] == hashlib.sha256(
            manifest.assets[0].prompt.encode()).hexdigest()
        assert row["input_sha256"] is None
        assert row["outputs"][0]["name"] == "approved/portrait.png"
        selected = engine.journal.root / "selected/approved/portrait.png"
        assert row["outputs"][0]["sha256"] == hashlib.sha256(
            selected.read_bytes()).hexdigest()
        assert row["outputs"][0]["width"] == 192
        assert row["outputs"][0]["height"] == 256
        assert row["visual_quality_verified"] is False
        assert row["stages"]
        generate = next(stage for stage in row["stages"]
                        if stage["stage"] == "generation")
        assert generate["provider"] == "demo"
        assert generate["model"] == "synthetic"
        assert generate["requested_seed"] == (
            int(hashlib.sha256(b"sample").hexdigest()[:8], 16))
        assert generate["artifact_sha256"]
        assert not any("path" in key for key in generate)
        assert engine.run()["asset_results"]["sample"]["status"] == "accepted"
        assert path.read_bytes() == first
        export_provenance(engine.journal)
        assert path.read_bytes() == first
    finally:
        engine.journal.close()


def test_original_input_bytes_hashed_and_private_path_not_exported(tmp_path):
    sources = tmp_path / "inputs"
    sources.mkdir()
    Image.new("RGB", (192, 256), "darkblue").save(sources / "private-original.png")
    manifest, profile = job(source=True)
    engine = Engine(manifest, profile, tmp_path, sources)
    try:
        engine.run()
        document = json.loads((engine.journal.root / "provenance.json").read_text())
        row = document["inputs_and_outputs"][0]
        assert row["input_kind"] == "original"
        assert row["input_sha256"] == hashlib.sha256(
            (sources/"private-original.png").read_bytes()).hexdigest()
        assert row["source_reference_sha256"] == hashlib.sha256(
            b"private-original.png").hexdigest()
        assert row["prompt_sha256"] is None
        assert "private-original.png" not in json.dumps(document)
        assert str(sources.resolve()) not in json.dumps(document)
    finally:
        engine.journal.close()


def test_original_input_modification_is_rejected_during_same_engine_resume(tmp_path):
    sources = tmp_path / "inputs"
    sources.mkdir()
    path = sources / "private-original.png"
    Image.new("RGB", (192, 256), "orange").save(path)
    manifest, profile = job(source=True)
    engine = Engine(manifest, profile, tmp_path, sources)
    try:
        engine.run()
        Image.new("RGB", (192, 256), "purple").save(path)
        with pytest.raises(ArtifactIntegrityError, match="Original input bytes changed"):
            engine.run()
        # Existing accepted output and manifest must remain unchanged.
        assert engine.journal.fact("results")["sample"]["status"] == "accepted"
    finally:
        engine.journal.close()


def test_original_input_modification_is_rejected_for_reopened_batch(tmp_path):
    sources = tmp_path/"inputs"
    sources.mkdir()
    path = sources/"private-original.png"
    Image.new("RGB", (192, 256), "red").save(path)
    manifest, profile = job(source=True)
    engine = Engine(manifest, profile, tmp_path, sources)
    engine.run()
    engine.journal.close()
    Image.new("RGB", (192, 256), "yellow").save(path)
    with pytest.raises(ArtifactIntegrityError, match="Original input bytes changed"):
        Engine(manifest, profile, tmp_path, sources)


def test_tampered_accepted_image_cannot_be_written_into_provenance(tmp_path):
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        engine.run()
        path = engine.journal.root/"selected/approved/portrait.png"
        Image.new("RGB", (192, 256), "green").save(path)
        with pytest.raises(ArtifactIntegrityError, match="SHA256 mismatch"):
            export_provenance(engine.journal)
    finally:
        engine.journal.close()


def test_request_id_is_only_exported_as_sha256_not_literal(tmp_path):
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        engine.run()
        generation = next(t for t in engine.journal.tasks() if t["stage"] == "generation")
        engine.journal.put(generation["task_key"], "generation", "completed",
                           request_id="SECRET_QUEUE_REMOTE_REQUEST_4291",
                           provider=generation["provider"], model=generation["model"],
                           path=generation["path"], data=generation["data"])
        doc = build_provenance(engine.journal)
        raw = json.dumps(doc)
        assert "SECRET_QUEUE_REMOTE_REQUEST_4291" not in raw
        stage = next(s for s in doc["inputs_and_outputs"][0]["stages"]
                     if s["stage"] == "generation")
        assert stage["request_id_sha256"] == hashlib.sha256(
            b"SECRET_QUEUE_REMOTE_REQUEST_4291").hexdigest()
    finally:
        engine.journal.close()
