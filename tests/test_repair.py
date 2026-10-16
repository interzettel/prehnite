"""Offline regression coverage for the first bounded Prehnite repair loop."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter

from prehnite.artifacts import ArtifactIntegrityError
from prehnite.images import sha256
from prehnite.repair import ALGORITHM, diagnose, run_product_repair
from prehnite.store import Journal
import prehnite.repair as repair


def images(tmp_path: Path) -> tuple[Path, Path]:
    image = Image.new("RGB", (160, 160), "#4aaf87")
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(image).rectangle((45, 34, 112, 126), fill="#e8b17d")
    ImageDraw.Draw(mask).rectangle((45, 34, 112, 126), fill=255)
    defective = mask.filter(ImageFilter.MaxFilter(5))
    source = tmp_path / "source.png"
    alpha = tmp_path / "mask.png"
    image.save(source)
    defective.save(alpha)
    return source, alpha


def execute(tmp_path, *, source=None, mask=None, **kwargs):
    source, mask = (source, mask) if source is not None else images(tmp_path)
    journal = Journal(tmp_path, "offline-repair-test")
    try:
        options = {"asset_id": "product-001", "target_id": "cup", **kwargs}
        return run_product_repair(journal, source, mask, **options)
    finally:
        journal.close()


def test_product_repair_removes_known_fringe_preserves_inputs_and_replays(tmp_path):
    source, mask = images(tmp_path)
    before = sha256(source), sha256(mask)
    detected = diagnose(source, mask)
    assert detected.fringe_pixels > 0
    first = execute(tmp_path, source=source, mask=mask)
    assert first["status"] == "technically_accepted"
    assert first["reason"] == "verified_local_refinement"
    assert first["metrics"]["fringe_before"] == detected.fringe_pixels
    assert first["metrics"]["fringe_after"] == 0
    assert first["would_spend_usd"] == 0
    assert (sha256(source), sha256(mask)) == before
    with Image.open(first["output"]) as im, Image.open(mask) as old:
        assert im.mode == "RGBA"
        assert im.size == (160, 160)
        assert im.getchannel("A").tobytes() != old.tobytes()
        with Image.open(source) as original:
            assert im.convert("RGB").tobytes() == original.tobytes()
    second = execute(tmp_path, source=source, mask=mask)
    assert second["reason"] == "verified_replay"
    assert second["output_sha256"] == first["output_sha256"]
    assert second["operation_id"] == first["operation_id"]
    db = sqlite3.connect(tmp_path / "batches/offline-repair-test/state.sqlite3")
    assert db.execute("SELECT COUNT(*) FROM local_repairs").fetchone()[0] == 1
    assert db.execute("SELECT status FROM local_repairs").fetchone()[0] == "accepted"
    db.close()


def test_portrait_and_unsafe_remote_or_accepted_state_refuse_without_attempt(tmp_path):
    source, mask = images(tmp_path)
    for flags, reason in [
        ({"cohort": "portrait"}, "portrait_or_other_cohort_unsupported"),
        ({"accepted_output_exists": True}, "accepted_or_remote_state_unsafe"),
        ({"remote_charge_uncertain": True}, "accepted_or_remote_state_unsafe"),
        ({"awaiting_provider_submission": True}, "accepted_or_remote_state_unsafe"),
    ]:
        out = execute(tmp_path, source=source, mask=mask, **flags)
        assert out["status"] == "human_review"
        assert out["reason"] == reason
        assert out["would_spend_usd"] == 0
    db = sqlite3.connect(tmp_path / "batches/offline-repair-test/state.sqlite3")
    rows = db.execute("SELECT name FROM sqlite_master WHERE name='local_repairs'").fetchall()
    assert rows == []
    db.close()


@pytest.mark.parametrize("variant,reason", [
    ("empty", "mask_empty_unrecoverable"),
    ("full", "mask_full_frame_unrecoverable"),
    ("touches_frame", "subject_touches_frame"),
    ("nonuniform", "background_not_uniform"),
    ("no_fringe", "no_verifiable_background_fringe"),
    ("bad_encoding", "mask_geometry_or_encoding_invalid"),
])
def test_fails_closed_on_unverifiable_masks(tmp_path, variant, reason):
    source, mask = images(tmp_path)
    if variant == "empty":
        Image.new("L", (160, 160), 0).save(mask)
    if variant == "full":
        Image.new("L", (160, 160), 255).save(mask)
    if variant == "touches_frame":
        with Image.open(mask) as im:
            altered = im.copy()
        altered.putpixel((0, 0), 255)
        altered.save(mask)
    if variant == "nonuniform":
        with Image.open(source) as im:
            altered = im.copy()
        altered.putpixel((0, 0), (0, 0, 0))
        altered.save(source)
    if variant == "no_fringe":
        with Image.open(source) as im:
            altered = im.copy()
        with Image.open(mask) as m:
            # Recolor every masked pixel to a foreground color; no verified
            # background-colored pixel remains to repair.
            for y in range(160):
                for x in range(160):
                    if m.getpixel((x, y)):
                        altered.putpixel((x, y), (245, 101, 72))
        altered.save(source)
    if variant == "bad_encoding":
        with Image.open(mask) as im:
            im.convert("RGB").save(mask)
    out = execute(tmp_path, source=source, mask=mask)
    assert out["status"] == "human_review"
    assert out["reason"] == reason


def test_tampered_accepted_image_refuses_reuse_and_never_overwrites(tmp_path):
    source, mask = images(tmp_path)
    accepted = execute(tmp_path, source=source, mask=mask)
    output = Path(accepted["output"])
    output.write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError):
        execute(tmp_path, source=source, mask=mask)
    assert output.read_bytes() == b"tampered"


def test_crash_after_publish_recovers_same_operation_without_new_attempt(tmp_path, monkeypatch):
    source, mask = images(tmp_path)
    normal = repair._state
    tripped = False

    def kill_after_publish(journal, operation_id, status, digest, detail):
        nonlocal tripped
        if status == "accepted" and not tripped:
            tripped = True
            raise KeyboardInterrupt("simulated hard-kill after publish before receipt")
        return normal(journal, operation_id, status, digest, detail)

    monkeypatch.setattr(repair, "_state", kill_after_publish)
    with pytest.raises(KeyboardInterrupt):
        execute(tmp_path, source=source, mask=mask)
    monkeypatch.setattr(repair, "_state", normal)
    result = execute(tmp_path, source=source, mask=mask)
    assert result["status"] == "technically_accepted"
    db = sqlite3.connect(tmp_path / "batches/offline-repair-test/state.sqlite3")
    assert db.execute("SELECT COUNT(*),MIN(attempt),MAX(status) FROM local_repairs").fetchone() == (1, 1, "accepted")
    db.close()


def test_crash_before_publish_resumes_same_operation(tmp_path, monkeypatch):
    source, mask = images(tmp_path)
    original = repair._render
    tripped = False

    def kill_before_publish(*args, **kwargs):
        nonlocal tripped
        if not tripped:
            tripped = True
            raise KeyboardInterrupt("simulated hard-kill before publish")
        return original(*args, **kwargs)

    monkeypatch.setattr(repair, "_render", kill_before_publish)
    with pytest.raises(KeyboardInterrupt):
        execute(tmp_path, source=source, mask=mask)
    monkeypatch.setattr(repair, "_render", original)
    result = execute(tmp_path, source=source, mask=mask)
    assert result["status"] == "technically_accepted"
    db = sqlite3.connect(tmp_path / "batches/offline-repair-test/state.sqlite3")
    assert db.execute("SELECT COUNT(*) FROM local_repairs").fetchone()[0] == 1
    db.close()


def test_selected_deliverables_and_invalid_ids_are_protected(tmp_path):
    source, mask = images(tmp_path)
    root = tmp_path / "batches/offline-repair-test/selected"
    root.mkdir(parents=True)
    out = execute(tmp_path, source=source, mask=mask)
    assert out["reason"] == "existing_selected_artifacts"
    root.rmdir()
    with pytest.raises(ValueError):
        execute(tmp_path, source=source, mask=mask, target_id="../escape")


def test_demo_generates_reference_independent_report_and_portrait_review(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "repair_demo.py"
    spec = importlib.util.spec_from_file_location("repair_demo", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    first = module.run(tmp_path)
    assert first["product_iou_after"] > first["product_iou_before"]
    assert first["product_iou_after"] == 1.0
    report = json.loads(Path(first["json"]).read_text())
    assert report["provider_requests"] == 0
    assert report["actual_paid_usd"] == 0
    assert report["logical_attempt_count"] == 1
    assert report["portrait"]["status"] == "human_review"
    assert report["product"]["metrics"]["fringe_after"] == 0
    content = Path(first["html"]).read_text()
    assert "data:image/png;base64," in content
    assert "One repair. No regeneration." in content
    second = module.run(tmp_path)
    assert second["product_iou_after"] == first["product_iou_after"]
    replay = json.loads(Path(second["json"]).read_text())
    assert replay["product"]["reason"] == "verified_replay"

def test_multiple_product_instances_must_be_selected_by_human(tmp_path):
    image = Image.new("RGB", (160, 160), "#4aaf87")
    alpha = Image.new("L", image.size, 0)
    for bounds in ((22, 44, 63, 111), (97, 47, 139, 118)):
        ImageDraw.Draw(image).rectangle(bounds, fill="#e8b17d")
        ImageDraw.Draw(alpha).rectangle(bounds, fill=255)
    source, mask = tmp_path / "two-products.png", tmp_path / "two-masks.png"
    image.save(source)
    alpha.filter(ImageFilter.MaxFilter(5)).save(mask)
    result = execute(tmp_path, source=source, mask=mask)
    assert result["status"] == "human_review"
    assert result["reason"] == "multiple_mask_islands_require_selection"


def test_changed_input_sha_cannot_reset_single_target_attempt_cap(tmp_path):
    from PIL.PngImagePlugin import PngInfo
    source, mask = images(tmp_path)
    initial = execute(tmp_path, source=source, mask=mask)
    assert initial["status"] == "technically_accepted"
    with Image.open(mask) as old:
        metadata = PngInfo()
        metadata.add_text("synthetic_revision", "same pixels different bytes")
        old.save(mask, pnginfo=metadata)
    result = execute(tmp_path, source=source, mask=mask)
    assert result["status"] == "human_review"
    assert result["reason"] == "target_repair_attempt_exhausted"
    db = sqlite3.connect(tmp_path / "batches/offline-repair-test/state.sqlite3")
    assert db.execute("SELECT COUNT(*) FROM local_repairs").fetchone()[0] == 1
    db.close()
