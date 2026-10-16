"""Deterministic ZIP receipts remain identical across mtimes and platforms."""
import hashlib
import json
import os
import zipfile

from PIL import Image

from prehnite.engine import Engine
from prehnite.reporting import package
from prehnite.schema import Manifest, Profile


def run_batch(tmp_path):
    manifest = Manifest.model_validate({"id": "zip-contract", "assets": [
        {"id": "one", "prompt": "fixture", "aspect_ratio": "3:4",
         "target_size": [192, 256], "output": {"image": "photos/one.png"}}
    ]})
    profile = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
    })
    engine = Engine(manifest, profile, tmp_path)
    engine.run()
    return engine


def test_zip_bytes_and_metadata_stable_across_mtime_changes(tmp_path):
    engine = run_batch(tmp_path)
    try:
        first = package(engine.journal).read_bytes()
        image = engine.journal.root/"selected/photos/one.png"
        os.utime(image, (1000000000, 1000000000))
        for name in ("report.json", "report.html", "operations.csv", "gallery.html"):
            file = engine.journal.root/name
            if file.exists():
                os.utime(file, (1100000000, 1100000000))
        second = package(engine.journal).read_bytes()
        assert first == second
        with zipfile.ZipFile(engine.journal.root/"prehnite-zip-contract.zip") as archive:
            names = archive.namelist()
            assert names == sorted(names)
            assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in archive.infolist())
            receipt = json.loads(archive.read("_prehnite/archive-manifest.json"))
            assert receipt["schema_version"] == 1
            assert set(receipt["sha256"]) == set(names) - {"_prehnite/archive-manifest.json"}
            for name, digest in receipt["sha256"].items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    finally:
        engine.journal.close()


def test_receipt_covers_report_and_selected_image(tmp_path):
    engine = run_batch(tmp_path)
    try:
        with zipfile.ZipFile(engine.journal.root/"prehnite-zip-contract.zip") as z:
            manifest = json.loads(z.read("_prehnite/archive-manifest.json"))
            assert "photos/one.png" in manifest["sha256"]
            assert "_prehnite/report.json" in manifest["sha256"]
            assert "_prehnite/provenance.json" in manifest["sha256"]
            assert z.testzip() is None
    finally:
        engine.journal.close()
