"""Untrusted ZIP refusal and no-ground-truth coverage for apparel pilot intake."""
from __future__ import annotations

import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image


def _module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "inspect_apparel_pilot.py"
    spec = importlib.util.spec_from_file_location("inspect_apparel_pilot", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _content(format="JPEG", mode="RGB"):
    buffer = io.BytesIO()
    Image.new(mode, (40, 52), (175, 145, 88)).save(buffer, format=format)
    return buffer.getvalue()


def _archive(root: Path, entries):
    path = root / "pilot.zip"
    with zipfile.ZipFile(path, "w") as zipped:
        for name, content in entries:
            zipped.writestr(name, content)
    return path


def test_inventory_and_source_only_no_false_iou(tmp_path):
    mod = _module()
    prefix = "wearhouse_synthetic_pilot"
    entries = []
    for n in range(1, 51):
        id_ = f"WH-S{n:03d}"
        entries.append((f"{prefix}/{id_}/front.jpg", _content()))
        if n <= 34:
            entries.append((f"{prefix}/{id_}/care_label.jpg", _content()))
    zip_path = _archive(tmp_path, entries)
    target = tmp_path / "private-test-output"
    result = mod.run(zip_path, target)
    assert result["file_count"] == 84
    assert result["roles"] == {"front": 50, "care_label": 34}
    assert result["reference_alpha_count"] == 0
    assert result["mask_iou_available"] is False
    assert result["human_accepted"] == 0
    assert result["candidates_generated"] == 0
    assert result["actual_segmentation_iou"] is None
    assert result["paid_provider_calls"] == 0
    assert zip_path.is_file()
    assert list(target.iterdir()) == [target / "report.json"]
    assert json.loads((target / "report.json").read_text()) == result
    # Never writes a source image into the public repo or private report.
    assert all(x["reference_alpha_present"] is False for x in result["sources"])


@pytest.mark.parametrize("problem,reason", [
    ("traversal", "unexpected_or_encrypted_member"),
    ("unrelated", "unexpected_or_encrypted_member"),
    ("duplicate", "duplicate_product_role"),
    ("bad_format", "unsupported_image_format"),
    ("empty", "unsupported_archive_count"),
    ("bad_bytes", "image_decode_failed"),
])
def test_untrusted_archive_fail_closed_without_output(tmp_path, problem, reason):
    mod = _module()
    entries = [("pilot/WH-S001/front.jpg", _content())]
    if problem == "traversal":
        entries = [("../WH-S001/front.jpg", _content())]
    if problem == "unrelated":
        entries = [("pilot/README.md", b"no image")]
    if problem == "duplicate":
        entries.append(entries[0])
    if problem == "bad_format":
        entries = [("pilot/WH-S001/front.jpg", _content("PNG"))]
    if problem == "bad_bytes":
        entries = [("pilot/WH-S001/front.jpg", b"not a JPEG")]
    if problem == "empty":
        entries = []
    input_zip = _archive(tmp_path, entries)
    destination = tmp_path / "no-output"
    with pytest.raises(mod.PilotRefused, match=reason):
        mod.run(input_zip, destination)
    assert not destination.exists()


def test_no_overwrite_previous_run(tmp_path):
    mod = _module()
    path = _archive(tmp_path, [("WH-S001/front.jpg", _content())])
    output = tmp_path / "report"
    first = mod.run(path, output)
    assert first["candidates_generated"] == 0
    with pytest.raises(mod.PilotRefused, match="destination_must_be_empty"):
        mod.run(path, output)
    assert (output / "report.json").is_file()


def test_excessively_large_or_many_entries_are_refused(tmp_path):
    mod = _module()
    path = _archive(tmp_path, [(f"WH-S{n:03d}/front.jpg", _content())
                                for n in range(1, 202)])
    with pytest.raises(mod.PilotRefused, match="unsupported_archive_count"):
        mod.inventory(path)


def test_optional_baseline_always_remains_unreviewed(tmp_path, monkeypatch):
    mod = _module()
    path = _archive(tmp_path, [("WH-S001/front.jpg", _content())])
    calls = []

    def fake_grabcut(raw):
        calls.append(raw)
        rgb = Image.new("RGB", (40, 52), (190, 160, 125))
        alpha = Image.new("L", rgb.size, 255)
        return rgb, alpha

    monkeypatch.setattr(mod, "_grabcut", fake_grabcut)
    output = tmp_path / "unreviewed"
    report = mod.run(path, output, unreviewed_grabcut=True)
    assert len(calls) == 1
    assert report["candidates_generated"] == 1
    assert report["human_accepted"] == 0
    assert report["actual_segmentation_iou"] is None
    assert report["mask_iou_available"] is False
    assert (output / "unreviewed_masks/WH-S001.png").is_file()
    assert (output / "unreviewed_previews/WH-S001.jpg").is_file()
