"""Native-pixel inspection: no network, full-resolution evidence, hash-safe output."""
from __future__ import annotations

import base64
import re
import zipfile

import pytest
from PIL import Image, ImageDraw
from typer.testing import CliRunner

from prehnite.artifacts import ArtifactIntegrityError
from prehnite.cli import app
from prehnite.images import image_info
from prehnite.native_inspection import export_native_inspection
from prehnite.reporting import export_report, package
from prehnite.store import Journal


def make_slot(journal, name="slot", *, cutout=True, status="accepted",
              size=(192, 256)):
    selected = journal.root / "selected"
    base = selected / f"photos/{name}.png"
    base.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "navy").save(base)
    outputs = [f"photos/{name}.png"]
    hashes = {outputs[0]: image_info(base)["sha256"]}
    requested = {}
    if cutout:
        co = selected / f"cutouts/{name}.png"
        co.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(image).ellipse((20, 30, size[0] - 20, size[1] - 30),
                                     fill=(255, 120, 40, 255))
        image.save(co)
        outputs.append(f"cutouts/{name}.png")
        hashes[outputs[-1]] = image_info(co)["sha256"]
        requested["subject"] = outputs[-1]
    journal.set_fact("manifest", {"assets": [{
        "id": name, "prompt": "PRIVATE PROMPT, DO NOT EXPORT",
        "output": {"image": outputs[0], "cutouts": requested},
    }]})
    result = {
        "status": status, "outputs": outputs, "outputs_sha256": hashes,
        "reason": "PRIVATE REJECTION DETAIL, DO NOT EXPORT",
    }
    journal.set_fact("results", {name: result})
    return result


def test_inspection_embeds_original_verified_pixels_and_alpha_at_1_to_1(tmp_path):
    j = Journal(tmp_path, "inspection")
    try:
        make_slot(j)
        path = export_native_inspection(j, "slot")
        page = path.read_text()
        assert path == j.root / "reviews" / "slot.html"
        assert 'width="192" height="256"' in page
        assert "Actual pixels (1:1)" in page
        assert "main:has(#actual:checked)" in page
        assert "checker" in page and "Cutout: subject" in page
        assert "SHA256 verified" in page
        assert "connect-src 'none'" in page
        assert "<script" not in page
        assert "http://" not in page and "https://" not in page
        assert "PRIVATE PROMPT" not in page
        assert "PRIVATE REJECTION DETAIL" not in page
        # Original PNG bytes, NOT reencoded thumbnails/crops.
        content = (j.root / "selected/photos/slot.png").read_bytes()
        assert base64.b64encode(content).decode("ascii") in page
        images = re.findall(r'data:image/png;base64,([A-Za-z0-9+/=]+)', page)
        assert len(images) == 2
        assert base64.b64decode(images[0]) == content
        assert "No quality certification" not in page  # lower-case disclaimer
        assert "no quality certification" in page
        assert not (j.root / "analytics.parquet").exists()
    finally:
        j.close()


def test_corrupt_output_refused_and_prior_html_preserved(tmp_path):
    j = Journal(tmp_path, "inspection-corrupt")
    try:
        make_slot(j)
        path = export_native_inspection(j, "slot")
        initial = path.read_bytes()
        (j.root / "selected/cutouts/slot.png").write_bytes(b"corrupted")
        with pytest.raises(ArtifactIntegrityError):
            export_native_inspection(j, "slot")
        assert path.read_bytes() == initial
    finally:
        j.close()


def test_symlink_escape_refused_even_with_matching_hash(tmp_path):
    j = Journal(tmp_path, "inspection-symlink")
    try:
        make_slot(j, cutout=False)
        source = j.root / "selected/photos/slot.png"
        external = tmp_path / "private-outside.png"
        external.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(external)
        except (NotImplementedError, OSError):
            pytest.skip("Symlinks unavailable")
        with pytest.raises(ArtifactIntegrityError, match="escapes batch root"):
            export_native_inspection(j, "slot")
    finally:
        j.close()


def test_rejected_assets_and_path_traversal_cannot_create_html(tmp_path):
    j = Journal(tmp_path, "inspection-reject")
    try:
        make_slot(j, status="rejected")
        with pytest.raises(ValueError, match="accepted base"):
            export_native_inspection(j, "slot")
        with pytest.raises(ValueError):
            export_native_inspection(j, "../bad")
        assert not (j.root / "reviews").exists()
    finally:
        j.close()


def test_failed_cutout_still_allows_valid_base_review(tmp_path):
    j = Journal(tmp_path, "inspection-partial")
    try:
        make_slot(j, cutout=False, status="failed_cutouts")
        page = export_native_inspection(j, "slot").read_text()
        assert page.count('class="panel"') == 1
        assert "Selected base" in page
    finally:
        j.close()


def test_size_cap_rejects_large_embeds_without_partial_write(tmp_path, monkeypatch):
    import prehnite.native_inspection as module
    j = Journal(tmp_path, "inspection-cap")
    try:
        make_slot(j)
        monkeypatch.setattr(module, "MAX_EMBEDDED_BYTES", 100)
        with pytest.raises(ValueError, match="limit"):
            module.export_native_inspection(j, "slot")
        assert not (j.root / "reviews/slot.html").exists()
    finally:
        j.close()


def test_cli_inspect_no_zip_changes_and_single_asset_from_ninety(tmp_path):
    j = Journal(tmp_path, "inspect-ninety")
    try:
        make_slot(j, name="slot-001", cutout=True)
        manifest = j.fact("manifest")
        manifest["assets"].extend(
            {"id": f"slot-{n:03d}", "prompt": "PRIVATE SLOT",
             "aspect_ratio": "1:1"} for n in range(2, 91))
        j.set_fact("manifest", manifest)
        export_report(j)
        baseline = package(j).read_bytes()
    finally:
        j.close()
    runner = CliRunner()
    response = runner.invoke(
        app, ["inspect", "inspect-ninety", "--asset", "slot-001",
              "--workspace", str(tmp_path)])
    assert response.exit_code == 0, response.output
    page = (tmp_path / "batches/inspect-ninety/reviews/slot-001.html").read_text()
    assert "slot-001" in page
    assert "slot-090" not in page
    assert page.count('class="panel"') == 2
    assert len(page.encode()) < 1_000_000
    j = Journal(tmp_path, "inspect-ninety")
    try:
        assert package(j).read_bytes() == baseline
        with zipfile.ZipFile(package(j)) as archive:
            assert not any("/reviews/" in name or name.endswith("slot-001.html")
                           for name in archive.namelist())
    finally:
        j.close()


def test_inspection_refuses_symlinked_review_destination_directory(tmp_path):
    j = Journal(tmp_path, "inspection-review-escape")
    try:
        make_slot(j, cutout=False)
        outside = tmp_path / "outside-folder"
        outside.mkdir()
        link = j.root / "reviews"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (NotImplementedError, OSError):
            pytest.skip("Directory symlinks unavailable")
        with pytest.raises(ArtifactIntegrityError, match="Review destination escapes"):
            export_native_inspection(j, "slot")
        assert not list(outside.iterdir())
    finally:
        j.close()


def test_inspection_refuses_base_output_mismatch_to_manifest(tmp_path):
    j = Journal(tmp_path, "inspection-mismatch")
    try:
        make_slot(j, cutout=False)
        m = j.fact("manifest")
        m["assets"][0]["output"]["image"] = "photos/another-file.png"
        j.set_fact("manifest", m)
        with pytest.raises(ArtifactIntegrityError, match="Base output differs"):
            export_native_inspection(j, "slot")
    finally:
        j.close()
