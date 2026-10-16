"""Private input-vs-output inspection: provenance, CSP and safe stage summary."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import zipfile

import pytest
from PIL import Image
from typer.testing import CliRunner

from prehnite.artifacts import ArtifactIntegrityError
from prehnite.cli import app
from prehnite.images import image_info
from prehnite.native_inspection import export_native_inspection
from prehnite.reporting import export_report, package
from prehnite.store import Journal


def fixture(tmp_path, *, prompt_only=False, hash_recorded=True, batch="comparison"):
    workspace = tmp_path / "workspace"
    inputs = tmp_path / "inputs"
    inputs.mkdir(exist_ok=True)
    j = Journal(workspace, batch)
    source = inputs / "source.png"
    Image.new("RGB", (188, 240), "red").save(source)
    selected = j.root / "selected/photos/one.png"
    selected.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (192, 256), "navy").save(selected)
    assets = [{"id": "one", "output": {"image": "photos/one.png", "cutouts": {}}}]
    if prompt_only:
        assets[0]["prompt"] = "PRIVATE PROMPT"
    else:
        assets[0]["source"] = "source.png"
    j.set_fact("manifest", {"assets": assets})
    j.set_fact("results", {"one": {
        "status": "accepted",
        "outputs": ["photos/one.png"],
        "outputs_sha256": {"photos/one.png": image_info(selected)["sha256"]},
    }})
    if hash_recorded and not prompt_only:
        j.set_fact("input_file_sha256", {"one": image_info(source)["sha256"]})
    return j, inputs, source, selected


def test_explicit_original_image_uses_saved_digest_and_unmodified_bytes(tmp_path):
    j, inputs, original, selected = fixture(tmp_path)
    try:
        path = export_native_inspection(j, "one", inputs=inputs)
        markup = path.read_text()
        assert "Original input (SHA256 verified)" in markup
        assert "Selected base" in markup
        assert markup.count('class="panel"') == 2
        assert 'width="188" height="240"' in markup
        assert 'width="192" height="256"' in markup
        assert base64.b64encode(original.read_bytes()).decode("ascii") in markup
        assert base64.b64encode(selected.read_bytes()).decode("ascii") in markup
        assert "Actual pixels (1:1)" in markup
        assert "Alpha checkerboard" in markup
        assert "main:has(#checker:not(:checked))" in markup
        assert "connect-src 'none'" in markup
        assert "<script" not in markup
        assert 'src="https://' not in markup
        assert "PRIVATE PROMPT" not in markup
    finally:
        j.close()


def test_changed_original_is_refused_without_erasing_prior_review(tmp_path):
    j, inputs, original, selected = fixture(tmp_path)
    try:
        path = export_native_inspection(j, "one", inputs=inputs)
        prior = path.read_bytes()
        Image.new("RGB", (188, 240), "yellow").save(original)
        with pytest.raises(ArtifactIntegrityError):
            export_native_inspection(j, "one", inputs=inputs)
        assert path.read_bytes() == prior
    finally:
        j.close()


def test_original_without_historical_digest_cannot_be_labeled_verified(tmp_path):
    j, inputs, _, _ = fixture(tmp_path, hash_recorded=False)
    try:
        assert "Original input" not in export_native_inspection(j, "one").read_text()
        with pytest.raises(ArtifactIntegrityError, match="historical"):
            export_native_inspection(j, "one", inputs=inputs)
    finally:
        j.close()


def test_prompt_only_asset_refuses_original_comparison(tmp_path):
    j, inputs, _, _ = fixture(tmp_path, prompt_only=True)
    try:
        with pytest.raises(ValueError, match="no original source"):
            export_native_inspection(j, "one", inputs=inputs)
        assert "Selected base" in export_native_inspection(j, "one").read_text()
    finally:
        j.close()


def test_original_symlink_outside_authorized_inputs_refused(tmp_path):
    j, inputs, original, _ = fixture(tmp_path)
    try:
        external = tmp_path / "unauthorized-original.png"
        external.write_bytes(original.read_bytes())
        original.unlink()
        try:
            original.symlink_to(external)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks unavailable for this Windows user")
        with pytest.raises(ValueError, match="escapes approved input"):
            export_native_inspection(j, "one", inputs=inputs)
        assert not (j.root / "reviews/one.html").exists()
    finally:
        j.close()


def test_private_stage_drilldown_counts_invocations_without_leaking_ids(tmp_path):
    j, _, _, _ = fixture(tmp_path, prompt_only=True)
    try:
        j.put("one:a1:generation", "generation", "completed",
              provider="demo", model="SECRET_MODEL", request_id="PRIVATE_REMOTE_ID",
              path="C:/Users/secret/input.png", reserved_usd=0.02,
              data={"exception": "PRIVATE_EXCEPTION"})
        attempt = j.begin_attempt("one:a1:generation", "generation", "demo")
        j.finish_attempt(attempt, "completed", 45.6)
        j.put("one:a2:bad", "<img src=x onerror=evil>", "failed",
              provider="https://secret.example", model="PRIVATE_MODEL",
              data={"error": "PRIVATE_EXCEPTION"})
        html = export_native_inspection(j, "one").read_text()
        assert "Local stage observations" in html
        assert "generation</td><td>demo</td><td>completed</td><td>1</td><td>$0.020000" in html
        assert "unknown</td><td>unknown</td><td>failed" in html
        assert "PRIVATE_MODEL" not in html
        assert "PRIVATE_REMOTE_ID" not in html
        assert "PRIVATE_EXCEPTION" not in html
        assert "secret.example" not in html
        assert "Users/secret" not in html
        assert "one:a1:generation" not in html
        assert "<img" in html  # embedded verified output; no injected image tags
        assert "onerror=evil" not in html
    finally:
        j.close()


def test_cli_explicit_inputs_and_no_default_zip_changes(tmp_path):
    j, inputs, _, _ = fixture(tmp_path, batch="cli-source")
    try:
        report = export_report(j)
        original_zip = package(j).read_bytes()
        assert report["asset_results"]["one"]["status"] == "accepted"
    finally:
        j.close()
    run = CliRunner().invoke(app, [
        "inspect", "cli-source", "--asset", "one",
        "--workspace", str(tmp_path / "workspace"), "--inputs", str(inputs)])
    assert run.exit_code == 0, run.output
    root = tmp_path / "workspace/batches/cli-source"
    assert "Original input (SHA256 verified)" in (root / "reviews/one.html").read_text()
    j = Journal(tmp_path / "workspace", "cli-source")
    try:
        assert package(j).read_bytes() == original_zip
        with zipfile.ZipFile(package(j)) as archive:
            assert not any("reviews/" in name for name in archive.namelist())
    finally:
        j.close()


def test_ninety_slots_never_embed_neighboring_original_or_stage(tmp_path):
    j, inputs, _, _ = fixture(tmp_path, batch="ninety-native")
    try:
        manifest = j.fact("manifest")
        manifest["assets"].extend(
            {"id": f"slot-{x:03d}", "prompt": "PRIVATE PROMPT", "output": {
                "image": f"photos/{x:03d}.png", "cutouts": {}}}
            for x in range(2, 91))
        j.set_fact("manifest", manifest)
        j.put("slot-002:a1:generation", "generation", "uncertain",
              provider="fal", request_id="PRIVATE_PENDING_REMOTE")
        text = export_native_inspection(j, "one", inputs=inputs).read_text()
        assert "Original input (SHA256 verified)" in text
        assert "slot-002" not in text
        assert "PRIVATE_PENDING_REMOTE" not in text
        assert "PRIVATE PROMPT" not in text
        assert text.count('class="panel"') == 2
        assert len(text.encode()) < 1_000_000
    finally:
        j.close()
