"""Offline integrity regressions. No provider network requests or paid tokens."""
from __future__ import annotations

import hashlib
import zipfile

import pytest
from PIL import Image

from prehnite.artifacts import ArtifactIntegrityError, atomic_resize
from prehnite.engine import Engine
from prehnite.providers import Result
from prehnite.reporting import package
from prehnite.schema import Endpoint, Manifest, Profile


def job(*, cutout=False):
    asset = {"id": "asset", "prompt": "fixture", "aspect_ratio": "3:4",
             "target_size": [192, 256], "output": {"image": "images/asset.png"}}
    if cutout:
        asset["targets"] = ["foreground"]
        asset["output"]["cutouts"] = {"foreground": "cutouts/foreground.png"}
    manifest = Manifest.model_validate({"id": "atomic", "assets": [asset]})
    profile = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "segmentation": ({"provider": "demo", "model": "synthetic"}
                         if cutout else {"provider": "disabled"}),
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
    })
    return manifest, profile


def paid_job(tmp_path):
    manifest, profile = job()
    settings = profile.model_copy(update={"costs": profile.costs.model_copy(
        update={"allow_paid": True, "allow_cloud_uploads": True,
                "max_usd": 0.5, "estimates_usd": {"generation:2k": 0.04}})})
    return Engine(manifest, settings, tmp_path)


def fake_image(temp, request_id):
    Image.new("RGB", (192, 256), "green").save(temp)
    return Result(temp, request_id, {"mock": True})


def test_stage_commits_only_fully_decodable_bytes_and_hash(tmp_path):
    engine = paid_job(tmp_path)
    destination = tmp_path/"remote.png"
    seen = []
    try:
        def invoke(on_submit, resume, staged):
            assert not destination.exists()
            assert staged.suffix == ".png"
            on_submit("existing-queue-1")
            seen.append(1)
            return fake_image(staged, "existing-queue-1")
        engine.stage("remote", "generation", Endpoint(provider="fal", model="mock"),
                     destination, invoke, "generation:2k")
        entry = engine.journal.get("remote")
        assert entry["data"]["artifact_sha256"] == hashlib.sha256(
            destination.read_bytes()).hexdigest()
        assert entry["data"]["artifact_bytes"] == destination.stat().st_size
        engine.stage("remote", "generation", Endpoint(provider="fal", model="mock"),
                     destination, lambda *args: pytest.fail("Cache was replayed"),
                     "generation:2k")
        assert seen == [1]
    finally:
        engine.journal.close()


def test_interrupted_remote_write_keeps_existing_accepted_file(tmp_path):
    engine = paid_job(tmp_path)
    destination = tmp_path/"remote.png"
    Image.new("RGB", (192, 256), "red").save(destination)
    previous = destination.read_bytes()
    engine.journal.put("remote", "generation", "submitted",
                       request_id="queue-1", provider="fal", model="mock",
                       reserved_usd=0.04)
    def interrupted(on_submit, resume, staged):
        assert resume == "queue-1"
        staged.write_bytes(b"partial PNG with no valid header")
        raise TimeoutError("crash while retrieving remote output")
    try:
        with pytest.raises(TimeoutError):
            engine.stage("remote", "generation", Endpoint(provider="fal", model="mock"),
                         destination, interrupted, "generation:2k")
        assert destination.read_bytes() == previous
        assert engine.journal.get("remote")["status"] == "submitted"
        assert not list(tmp_path.glob(".prehnite-*.png"))
    finally:
        engine.journal.close()


def test_digest_mismatch_on_completed_paid_task_resumes_id_not_resubmits(tmp_path):
    engine = paid_job(tmp_path)
    destination = tmp_path/"remote.png"
    calls = []
    try:
        def first(on_submit, resume, staged):
            on_submit("queue-1")
            return fake_image(staged, "queue-1")
        ep = Endpoint(provider="fal", model="mock")
        engine.stage("remote", "generation", ep, destination, first, "generation:2k")
        with Image.new("RGB", (192, 256), "blue") as other:
            other.save(destination)  # Valid image; wrong bytes.
        def recover(on_submit, resume, staged):
            assert resume == "queue-1"
            calls.append(resume)
            return fake_image(staged, resume)
        engine.stage("remote", "generation", ep, destination,
                     recover, "generation:2k")
        assert calls == ["queue-1"]
        assert engine.journal.reserved() == pytest.approx(0.04)
        assert engine.journal.get("remote")["data"]["artifact_sha256"] == hashlib.sha256(
            destination.read_bytes()).hexdigest()
    finally:
        engine.journal.close()


def test_missing_digest_and_remote_id_fails_closed(tmp_path):
    engine = paid_job(tmp_path)
    destination = tmp_path/"remote.png"
    Image.new("RGB", (192, 256), "red").save(destination)
    engine.journal.put("remote", "generation", "completed", provider="fal",
                       model="mock", path=str(destination), reserved_usd=0.04)
    try:
        with pytest.raises(RuntimeError, match="no recoverable provider ID"):
            engine.stage("remote", "generation", Endpoint(provider="fal", model="mock"),
                         destination, lambda *args: pytest.fail("Unsafe submit"),
                         "generation:2k")
    finally:
        engine.journal.close()


def test_provider_cannot_publish_outside_stage_target(tmp_path):
    engine = paid_job(tmp_path)
    destination = tmp_path/"remote.png"
    wrong = tmp_path/"wrong.png"
    def misbehaving(on_submit, resume, staged):
        Image.new("RGB", (192, 256), "red").save(wrong)
        return Result(wrong, "queue-1")
    try:
        with pytest.raises(ValueError, match="atomic staging"):
            engine.stage("remote", "generation", Endpoint(provider="fal", model="mock"),
                         destination, misbehaving, "generation:2k")
        assert not destination.exists()
        assert not list(tmp_path.glob(".prehnite-*.png"))
    finally:
        engine.journal.close()


def test_atomic_resize_keeps_old_file_on_local_failure(monkeypatch, tmp_path):
    original, destination = tmp_path/"src.png", tmp_path/"dest.png"
    Image.new("RGB", (192, 256), "red").save(original)
    Image.new("RGB", (192, 256), "green").save(destination)
    old = destination.read_bytes()
    def fail(source, staged, size):
        staged.write_bytes(b"partial")
        raise OSError("interrupted encoding")
    monkeypatch.setattr("prehnite.artifacts.resize_to", fail)
    with pytest.raises(OSError):
        atomic_resize(original, destination, (192, 256))
    assert destination.read_bytes() == old
    assert not list(tmp_path.glob(".prehnite-*.png"))


@pytest.mark.parametrize("variant", ["valid_but_different", "truncated", "deleted"])
def test_tampered_selected_output_cannot_be_archived_or_trusted(tmp_path, variant):
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        first = engine.run()
        assert first["asset_results"]["asset"]["status"] == "accepted"
        selected = engine.journal.root/"selected/images/asset.png"
        archive = engine.journal.root/"prehnite-atomic.zip"
        untouched_zip = archive.read_bytes()
        if variant == "valid_but_different":
            Image.new("RGB", (192, 256), "violet").save(selected)
        elif variant == "truncated":
            selected.write_bytes(b"not a PNG")
        else:
            selected.unlink()
        with pytest.raises(ArtifactIntegrityError):
            package(engine.journal)
        assert archive.read_bytes() == untouched_zip  # Atomic ZIP update.
        again = engine.run()
        assert again["asset_results"]["asset"]["status"] == "error"
        assert again["asset_results"]["asset"]["integrity_error"]
        with zipfile.ZipFile(archive) as z:
            assert "images/asset.png" not in z.namelist()
            assert z.testzip() is None
    finally:
        engine.journal.close()


def test_corrupt_named_cutout_is_rejected_without_regeneration(tmp_path):
    manifest, profile = job(cutout=True)
    engine = Engine(manifest, profile, tmp_path)
    try:
        report = engine.run()
        assert report["asset_results"]["asset"]["status"] == "accepted"
        selected = engine.journal.root/"selected/cutouts/foreground.png"
        selected.write_bytes(b"bad mask output")
        with pytest.raises(ArtifactIntegrityError):
            package(engine.journal)
        again = engine.run()
        assert again["asset_results"]["asset"]["status"] == "error"
        with zipfile.ZipFile(engine.journal.root/"prehnite-atomic.zip") as z:
            assert "cutouts/foreground.png" not in z.namelist()
    finally:
        engine.journal.close()


def test_no_provenance_digests_may_not_pass_export(tmp_path):
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        engine.run()
        prior = engine.journal.fact("results")
        prior["asset"]["outputs_sha256"] = {}
        engine.journal.set_fact("results", prior)
        with pytest.raises(ArtifactIntegrityError, match="Missing SHA256"):
            package(engine.journal)
    finally:
        engine.journal.close()


def test_atomic_zip_failure_preserves_last_good_archive(monkeypatch, tmp_path):
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        engine.run()
        archive = engine.journal.root/"prehnite-atomic.zip"
        baseline = archive.read_bytes()
        import prehnite.reporting as reporting
        original = reporting._zip_add
        def fail_on_asset(archive, name, body):
            if name == "images/asset.png":
                raise OSError("disk full mid-archive")
            return original(archive, name, body)
        monkeypatch.setattr(reporting, "_zip_add", fail_on_asset)
        with pytest.raises(OSError):
            package(engine.journal)
        assert archive.read_bytes() == baseline
        assert not list(engine.journal.root.glob(".prehnite-*.zip"))
    finally:
        engine.journal.close()
