"""Static offline results gallery, with no browser network and no paid models."""
from __future__ import annotations

import base64
import re
import zipfile

import pytest
from PIL import Image, ImageDraw

from prehnite.artifacts import ArtifactIntegrityError
from prehnite.gallery import export_gallery
from prehnite.images import image_info
from prehnite.reporting import export_report, package
from prehnite.store import Journal


def add_asset(journal, asset_id, *, status="accepted", cutout=False, reason=""):
    path = journal.root/"selected"/f"photos/{asset_id}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (160, 180), "navy").save(path)
    outputs = [f"photos/{asset_id}.png"]
    digests = {outputs[0]: image_info(path)["sha256"]}
    if cutout:
        name = f"cutouts/{asset_id}.png"
        cutout_path = journal.root/"selected"/name
        cutout_path.parent.mkdir(parents=True, exist_ok=True)
        rgba = Image.new("RGBA", (160, 180), (0, 0, 0, 0))
        ImageDraw.Draw(rgba).ellipse((20, 30, 140, 160), fill=(240, 140, 40, 255))
        rgba.save(cutout_path)
        outputs.append(name)
        digests[name] = image_info(cutout_path)["sha256"]
    return {"status": status, "outputs": outputs, "outputs_sha256": digests,
            "reason": reason, "winning_variant": "native_4k",
            "quality_score": None}


def test_gallery_embeds_selected_cutout_and_candidate_with_no_external_resources(tmp_path):
    journal = Journal(tmp_path, "gallery")
    try:
        result = add_asset(journal, "one", cutout=True)
        journal.set_fact("manifest", {"assets": [{"id": "one"}]})
        journal.set_fact("results", {"one": result})
        candidate = journal.root/"intermediates/one/attempt-1/native_4k/final.png"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (160, 180), "salmon").save(candidate)
        report = export_report(journal)
        page = (journal.root/"gallery.html").read_text()
        assert report["asset_results"]["one"]["status"] == "accepted"
        assert "Candidate attempt-1 / native_4k" in page
        assert "Selected: photos/one.png" in page
        assert "Cutout: cutouts/one.png" in page
        assert 'class="thumb checker"' in page
        assert "Content-Security-Policy" in page
        assert "connect-src 'none'" in page
        assert "<script" not in page
        assert "http://" not in page and "https://" not in page
        assert page.count("src=\"data:image/") == 3
        assert len(re.findall(r'data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=]+', page)) == 3
        archive = package(journal)
        with zipfile.ZipFile(archive) as z:
            assert "_prehnite/gallery.html" in z.namelist()
            assert "photos/one.png" in z.namelist()
            assert "cutouts/one.png" in z.namelist()
    finally:
        journal.close()


def test_gallery_escapes_untrusted_asset_name_and_rejection_notes(tmp_path):
    journal = Journal(tmp_path, "escape")
    try:
        evil = '<script>alert("do not run")</script>'
        journal.set_fact("manifest", {"assets": [{"id": evil}]})
        journal.set_fact("results", {evil: {
            "status": "rejected", "outputs": [],
            "reason": '<img src="https://evil.example/collect" onerror="x">',
        }})
        page = export_gallery(journal).read_text()
        assert "&lt;script&gt;" in page
        assert '&lt;img src=&quot;https://evil.example/collect&quot;' in page
        assert "<script>" not in page
        assert "<img src=\"https://evil" not in page
        assert "No accepted deliverables" in page
    finally:
        journal.close()


def test_gallery_fails_closed_when_accepted_file_is_corrupt(tmp_path):
    journal = Journal(tmp_path, "corrupt")
    try:
        result = add_asset(journal, "one")
        journal.set_fact("results", {"one": result})
        original = export_gallery(journal).read_bytes()
        (journal.root/"selected/photos/one.png").write_bytes(b"bad PNG")
        with pytest.raises(ArtifactIntegrityError):
            export_gallery(journal)
        assert (journal.root/"gallery.html").read_bytes() == original
        with pytest.raises(ArtifactIntegrityError):
            package(journal)
    finally:
        journal.close()


def test_gallery_handles_ninety_assets_and_has_mobile_layout(tmp_path):
    journal = Journal(tmp_path, "ninety")
    try:
        ids = [f"asset-{n:03d}" for n in range(90)]
        journal.set_fact("manifest", {"assets": [{"id": aid} for aid in ids]})
        journal.set_fact("results", {aid: add_asset(journal, aid) for aid in ids})
        page = export_gallery(journal).read_text()
        assert "90 assets" in page
        assert "90 accepted" in page
        assert page.count('class="asset"') == 90
        assert page.count('src="data:image/jpeg;base64,') == 90
        assert 'name="viewport"' in page
        assert "grid-template-columns:repeat(auto-fill" in page
        # Inline images are small thumbnails. It is not a single 90x4K export.
        assert len(page.encode()) < 2_000_000
    finally:
        journal.close()


def test_intermediate_preview_is_local_only_and_never_represented_as_verified(tmp_path):
    journal = Journal(tmp_path, "intermediate")
    try:
        journal.set_fact("manifest", {"assets": [{"id": "one"}]})
        journal.set_fact("results", {"one": {"status": "rejected", "outputs": [],
                                            "reason": "Failed the judge"}})
        internal = journal.root/"intermediates/one/attempt-1/enhanced_2k/final.png"
        internal.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (100, 100), "red").save(internal)
        outside = tmp_path/"outside.png"
        Image.new("RGB", (100, 100), "blue").save(outside)
        (internal.parent/"something.png").symlink_to(outside)
        page = export_gallery(journal).read_text()
        assert "Candidate attempt-1 / enhanced_2k" in page
        assert "preview only" in page
        assert "Failed the judge" in page
        assert "outside.png" not in page
    finally:
        journal.close()
