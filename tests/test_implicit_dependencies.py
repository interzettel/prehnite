"""Fail-closed operator-declared implicit model file evidence, no GPU or installs."""
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from prehnite.engine import Engine
from prehnite.implicit_dependencies import verify_implicit_dependencies
from prehnite.manifest import validate_job
from prehnite.schema import Manifest
from test_reviewed_source_handoff import packet


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


@pytest.fixture
def declared(packet, tmp_path):
    inputs, manifest, profile, workspace, _ = packet
    root = tmp_path / "private-models"
    files = {
        "dino/groundingdino_swint_ogc.pth": ("groundingdino_weights", "weight"),
        "sam2/sam2.1_hiera_base_plus.pt": ("sam2_weights", "weight"),
        "bert/model.safetensors": ("bert_weights", "weight"),
        "dino/GroundingDINO_SwinT_OGC.cfg.py": ("groundingdino_config", "config"),
        "bert/config.json": ("bert_config", "config"),
        "bert/vocab.txt": ("bert_vocab", "tokenizer"),
        "bert/tokenizer.json": ("bert_tokenizer", "tokenizer"),
    }
    rows = []
    for filename, (role, kind) in files.items():
        path = root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((role + "::synthetic-checkpoint-not-real").encode())
        rows.append({
            "role": role, "kind": kind, "path": filename,
            "sha256": digest(path),
            "source_url": "https://example.org/official-weights",
            "source_revision": "a" * 40,
            "license_url": "https://example.org/model-license",
        })
    spec = inputs / "implicit-dependencies.json"
    spec.write_text(json.dumps({"schema_version": 1, "files": rows}, sort_keys=True), encoding="utf-8")
    manifest.handoff.implicit_manifest = spec.name
    manifest.handoff.implicit_manifest_sha256 = digest(spec)
    return inputs, manifest, profile, workspace, root, spec, rows


def test_strict_preflight_hashes_full_operator_declared_stack_without_gpu(declared):
    inputs, manifest, profile, workspace, root, spec, rows = declared
    validate_job(manifest, profile, inputs, root)
    assert not workspace.exists()
    claim = verify_implicit_dependencies(spec, root, manifest.handoff.implicit_manifest_sha256)
    assert claim["file_count"] == 7
    assert claim["coverage"] == "operator_declared_implicit_only"
    assert claim["runtime_loaded_bytes_verified"] is False
    assert claim["graph_coverage_verified"] is False
    assert all("path" not in record for record in claim["files"])
    assert {x["role"] for x in claim["files"]} == {x["role"] for x in rows}


def test_missing_dependency_root_refuses_to_open_batch(declared):
    inputs, manifest, profile, workspace, root, spec, rows = declared
    with pytest.raises(ValueError, match="dependencies-root"):
        Engine(manifest, profile, workspace, inputs=inputs)
    assert not workspace.exists()


@pytest.mark.parametrize("change", [
    "modified_weight", "modified_tokenizer", "missing_config", "manifest_mismatch",
    "undeclared_file", "bad_source_revision", "path_traversal", "duplicate_role",
    "invalid_source_url", "wrong_license_url",
])
def test_bad_implicit_dependency_claims_fail_before_journal(declared, change):
    inputs, manifest, profile, workspace, root, spec, rows = declared
    if change == "modified_weight":
        (root / rows[0]["path"]).write_bytes(b"changed weight")
    elif change == "modified_tokenizer":
        (root / rows[-1]["path"]).write_bytes(b"changed tokenizer")
    elif change == "missing_config":
        (root / rows[3]["path"]).unlink()
    elif change == "manifest_mismatch":
        spec.write_text(spec.read_text() + " ")
    else:
        if change == "undeclared_file":
            rows[0]["path"] = "dino/not-authorized.pth"
        elif change == "bad_source_revision":
            rows[0]["source_revision"] = "main"
        elif change == "path_traversal":
            rows[0]["path"] = "../escape.pth"
        elif change == "duplicate_role":
            rows[0]["role"] = rows[1]["role"]
        elif change == "invalid_source_url":
            rows[0]["source_url"] = "http://127.0.0.1/model"
        elif change == "wrong_license_url":
            rows[0]["license_url"] = "file:///license"
        spec.write_text(json.dumps({"schema_version": 1, "files": rows}))
        manifest.handoff.implicit_manifest_sha256 = digest(spec)
    with pytest.raises((ValueError, FileNotFoundError, OSError)):
        Engine(manifest, profile, workspace, inputs=inputs, dependency_root=root)
    assert not workspace.exists()


def test_source_only_cutout_receipt_pins_dependencies_without_claiming_quality(
        declared, monkeypatch):
    inputs, manifest, profile, workspace, root, spec, rows = declared
    calls = []
    def fake_cutout(self, asset, selected, name, attempt, target_output, *, target_prompt=None):
        calls.append((name, target_prompt))
        target_output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (768, 1024), (1, 2, 3, 0)).save(target_output)
    monkeypatch.setattr(Engine, "cutout", fake_cutout)
    engine = Engine(manifest, profile, workspace, inputs=inputs, dependency_root=root)
    try:
        report = engine.run()
        assert calls == [("table-lamp", "table lamp")]
        handoff = report["human_review_handoff"]
        assert handoff["implicit_dependency_attestation"]["file_count"] == 7
        assert handoff["implicit_dependency_attestation"]["runtime_loaded_bytes_verified"] is False
        assert report["asset_results"]["desk-lamp"]["status"] == "review_pending"
        assert report["asset_results"]["desk-lamp"]["cutout_quality_verified"] is False
        (root / rows[0]["path"]).write_bytes(b"tampered after run")
        with pytest.raises(ValueError, match="SHA256 mismatch"):
            engine.run()
        assert len(calls) == 1
    finally:
        engine.journal.close()


def test_changed_declared_bytes_after_engine_setup_rejected_before_segmentation(
        declared, monkeypatch):
    inputs, manifest, profile, workspace, root, spec, rows = declared
    engine = Engine(manifest, profile, workspace, inputs=inputs, dependency_root=root)
    calls = []
    monkeypatch.setattr(Engine, "cutout", lambda *args, **kwargs: calls.append(1))
    try:
        (root / rows[-1]["path"]).write_bytes(b"bad")
        with pytest.raises(ValueError, match="SHA256 mismatch"):
            engine.run()
        assert calls == []
    finally:
        engine.journal.close()


def test_old_reviewed_source_manifest_is_backward_compatible(packet):
    inputs, manifest, profile, workspace, _ = packet
    validate_job(manifest, profile, inputs)
    assert manifest.handoff.implicit_manifest is None
    assert not workspace.exists()


def test_refuses_dependency_root_without_manifest(packet, tmp_path):
    inputs, manifest, profile, workspace, _ = packet
    with pytest.raises(ValueError, match="without a pinned implicit manifest"):
        validate_job(manifest, profile, inputs, tmp_path)


def test_symlinked_dependency_refused_when_platform_allows(declared, tmp_path):
    inputs, manifest, profile, workspace, root, spec, rows = declared
    original = root / rows[0]["path"]
    copy = tmp_path / "outside-model.pth"
    copy.write_bytes(original.read_bytes())
    original.unlink()
    try:
        original.symlink_to(copy)
    except OSError:
        pytest.skip("Windows symlink privileges unavailable")
    with pytest.raises(ValueError, match="Symlinked"):
        validate_job(manifest, profile, inputs, root)
    assert not workspace.exists()
