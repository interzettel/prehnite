"""Opt-in Engine.cutout repair is journal-backed and strictly review-only."""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter

from prehnite.artifacts import ArtifactIntegrityError
from prehnite.engine import Engine
from prehnite.images import sha256
from prehnite.schema import Asset, Endpoint, Output, Profile, QualityPolicy
from prehnite.store import Journal
import prehnite.repair as repair


def fixture(tmp_path, *, mode="stage_for_review", material="opaque"):
    original = Image.new("RGB", (160, 160), "#4aaf87")
    alpha = Image.new("L", original.size, 0)
    ImageDraw.Draw(original).rectangle((45, 34, 112, 126), fill="#e8b17d")
    ImageDraw.Draw(alpha).rectangle((45, 34, 112, 126), fill=255)
    defect = alpha.filter(ImageFilter.MaxFilter(5))
    journal = Journal(tmp_path, "review-cutout-batch")
    chosen = journal.root / "selected" / "source.png"
    chosen.parent.mkdir(parents=True, exist_ok=True)
    original.save(chosen)
    source_mask = tmp_path / "provider-mask.png"
    defect.save(source_mask)
    target = journal.root / "selected" / "cup.png"
    asset = Asset(id="opaque-1", source="source.png", target_size=(160, 160),
                  aspect_ratio="1:1", targets=["cup"], output=Output(
                      image="source.png", cutouts={"cup": "cup.png"}),
                  cutout_materials={"cup":material} if material is not None else {})
    profile = Profile(variants=["native_4k"],
                      segmentation=Endpoint(provider="demo", model="synthetic"),
                      policy=QualityPolicy(local_repair_mode=mode))
    engine = object.__new__(Engine)
    engine.profile, engine.journal = profile, journal
    engine.job_token, engine._run_lock_held = None, False
    calls = []
    def fake_stage(key, stage, endpoint, output, invoke, price_key="", cache_request=None):
        calls.append(key)
        output.parent.mkdir(parents=True, exist_ok=True)
        if not output.exists():
            shutil.copyfile(source_mask, output)
        return output
    engine.stage = fake_stage
    return engine, asset, chosen, source_mask, target, calls


def test_stages_proven_candidate_but_never_auto_accepts_or_mutates_selected(tmp_path):
    engine, asset, selected, provided_mask, target, calls = fixture(tmp_path)
    initial = sha256(selected), sha256(provided_mask)
    try:
        with pytest.raises(ValueError, match="staged for human review"):
            engine.cutout(asset, selected, "cup", 1, target)
        assert len(calls) == 1  # zero extra segmentation/provider requests
        assert (sha256(selected), sha256(provided_mask)) == initial
        assert not target.exists()
        row = engine.journal.get("opaque-1:cutout:cup:local_review")
        assert row["status"] == "review" and row["provider"] == "local"
        assert row["reserved_usd"] == 0
        evidence = row["data"]
        assert evidence["human_visual_acceptance"] is False
        assert evidence["result_status"] == "technically_accepted"
        candidate = Path(evidence["candidate_path"])
        assert candidate.is_file() and "repairs" in candidate.parts
        assert sha256(candidate) == evidence["candidate_sha256"]
        assert evidence["technical_metrics"]["fringe_after"] == 0
        assert evidence["would_spend_usd"] == 0
        with Image.open(candidate) as result:
            assert result.mode == "RGBA"
        with pytest.raises(ValueError, match="staged for human review"):
            engine.cutout(asset, selected, "cup", 1, target)
        new = engine.journal.get("opaque-1:cutout:cup:local_review")["data"]
        assert new["reason"] == "verified_replay"
        assert new["operation_id"] == evidence["operation_id"]
        assert new["candidate_sha256"] == evidence["candidate_sha256"]
        assert engine.journal.db.execute(
            "SELECT COUNT(*) FROM local_repairs").fetchone()[0] == 1
        assert not target.exists()
    finally:
        engine.journal.close()


def test_selected_source_can_run_under_existing_engine_lock_without_deadlock(tmp_path):
    engine, asset, selected, _, target, _ = fixture(tmp_path)
    try:
        with engine.journal.exclusive():
            engine._run_lock_held = True
            with pytest.raises(ValueError, match="staged for human review"):
                engine.cutout(asset, selected, "cup", 1, target)
        assert not target.exists()
    finally:
        engine._run_lock_held = False
        engine.journal.close()


def test_unknown_and_complex_materials_abstain_without_local_attempt(tmp_path):
    for material in (None, "hair", "glass", "fabric", "translucent", "unknown"):
        workspace = tmp_path / str(material)
        engine, asset, selected, _, target, calls = fixture(workspace, material=material)
        try:
            with pytest.raises(ValueError, match="material_not_qualified"):
                engine.cutout(asset, selected, "cup", 1, target)
            assert len(calls) == 1
            assert not target.exists()
            assert engine.journal.db.execute(
                "SELECT name FROM sqlite_master WHERE name='local_repairs'").fetchall() == []
        finally:
            engine.journal.close()


def test_existing_output_is_protected_before_any_segmentation(tmp_path):
    engine, asset, selected, _, target, calls = fixture(tmp_path)
    try:
        target.write_bytes(b"previously-accepted-cutout")
        with pytest.raises(ArtifactIntegrityError, match="cannot be overwritten"):
            engine.cutout(asset, selected, "cup", 1, target)
        assert target.read_bytes() == b"previously-accepted-cutout"
        assert calls == []
    finally:
        engine.journal.close()


def test_default_mode_remains_existing_technical_flow(tmp_path):
    engine, asset, selected, _, target, calls = fixture(tmp_path, mode="disabled")
    try:
        result = engine.cutout(asset, selected, "cup", 1, target)
        assert result["status"] == "accepted"
        assert target.is_file()
        assert len(calls) == 1
        assert engine.journal.get("opaque-1:cutout:cup:local_review") is None
        assert engine.journal.db.execute(
            "SELECT name FROM sqlite_master WHERE name='local_repairs'").fetchall() == []
    finally:
        engine.journal.close()


def test_source_without_uniform_background_abstains_and_preserves_artifacts(tmp_path):
    engine, asset, selected, _, target, _ = fixture(tmp_path)
    try:
        with Image.open(selected) as old:
            modified = old.copy()
        modified.putpixel((0, 0), (0, 0, 0))
        modified.save(selected)
        digest = sha256(selected)
        with pytest.raises(ValueError, match="staged for human review"):
            engine.cutout(asset, selected, "cup", 1, target)
        row = engine.journal.get("opaque-1:cutout:cup:local_review")["data"]
        assert row["result_status"] == "human_review"
        assert row["reason"] == "background_not_uniform"
        assert "candidate_path" not in row
        assert not target.exists() and sha256(selected) == digest
    finally:
        engine.journal.close()


def test_output_replay_after_crash_does_not_create_second_paid_or_local_attempt(tmp_path, monkeypatch):
    engine, asset, selected, _, target, calls = fixture(tmp_path)
    original = repair._state
    injected = [False]
    def crash_after_publishing(journal, operation_id, status, digest, detail):
        if status == "accepted" and not injected[0]:
            injected[0] = True
            raise KeyboardInterrupt("crash before receipt")
        return original(journal, operation_id, status, digest, detail)
    try:
        monkeypatch.setattr(repair, "_state", crash_after_publishing)
        with pytest.raises(KeyboardInterrupt, match="crash"):
            engine.cutout(asset, selected, "cup", 1, target)
        monkeypatch.setattr(repair, "_state", original)
        with pytest.raises(ValueError, match="staged for human review"):
            engine.cutout(asset, selected, "cup", 1, target)
        assert len(calls) == 2  # cached segmentation stage, not resubmitted remotely
        assert engine.journal.db.execute(
            "SELECT COUNT(*) FROM local_repairs").fetchone()[0] == 1
        assert not target.exists()
        assert engine.journal.get("opaque-1:cutout:cup:local_review")["data"]["reason"] == "verified_local_refinement"
    finally:
        monkeypatch.setattr(repair, "_state", original)
        engine.journal.close()


def test_reject_invalid_material_declarations_and_nondefault_policy():
    with pytest.raises(ValueError, match="unknown target"):
        Asset(id="sample", source="input.png", target_size=(160, 160),
              aspect_ratio="1:1", targets=["cup"],
              cutout_materials={"portrait":"opaque"},
              output=Output(image="source.png", cutouts={"cup":"cup.png"}))
    with pytest.raises(ValueError, match="local_repair_mode"):
        QualityPolicy(local_repair_mode="auto_publish")
