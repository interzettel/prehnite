"""Offline, journal-backed repair for a narrowly verified synthetic product edge.

This intentionally does NOT generalize to portraits, hair, translucent objects,
photographs with complex backgrounds or production cutout acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .artifacts import ArtifactIntegrityError, temporary_sibling, verified_image
from .decision_engine import CandidateState, RepairLimits, decide_candidate
from .images import sha256
from .store import Journal

ALGORITHM = "uniform-product-fringe-v1"
POLICY = "technical-product-demo-v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_PIXELS = 4_000_000
MAX_FRINGE = 4
COLOR_TOLERANCE = 8


class RepairRefused(ValueError):
    """The available evidence cannot support a safe local alpha correction."""


@dataclass(frozen=True)
class FringeDiagnosis:
    background: tuple[int, int, int]
    fringe_pixels: int
    foreground_pixels: int
    source_sha256: str
    mask_sha256: str


def _inputs(source: Path, mask: Path) -> tuple[Image.Image, Image.Image]:
    for path in (source, mask):
        if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
            raise RepairRefused("missing_or_oversized_input")
    try:
        with Image.open(source) as opened:
            if opened.format != "PNG" or opened.mode != "RGB" or opened.getexif().get(274, 1) != 1:
                raise RepairRefused("unsupported_source_encoding_or_orientation")
            if opened.width * opened.height > MAX_PIXELS:
                raise RepairRefused("oversized_source")
            original = opened.copy()
        with Image.open(mask) as opened:
            if opened.format != "PNG" or opened.mode != "L" or opened.size != original.size:
                raise RepairRefused("mask_geometry_or_encoding_invalid")
            if opened.getexif().get(274, 1) != 1:
                raise RepairRefused("oriented_mask_requires_review")
            alpha = opened.copy()
        return original, alpha
    except (OSError, Image.DecompressionBombError) as exc:
        raise RepairRefused("image_decode_failed") from exc


def _fringe(source: Image.Image, alpha: Image.Image) -> tuple[tuple[int, int, int], Image.Image, int]:
    width, height = source.size
    if width < 32 or height < 32:
        raise RepairRefused("image_too_small")
    if alpha.getextrema() == (0, 0):
        raise RepairRefused("mask_empty_unrecoverable")
    if alpha.getextrema() == (255, 255):
        raise RepairRefused("mask_full_frame_unrecoverable")

    # Require a truly isolated target and a perfectly known synthetic-style
    # background around the entire frame. Never infer a background from an
    # arbitrary real photograph, and never use the benchmark reference here.
    boundary = []
    for x in range(width):
        if alpha.getpixel((x, 0)) or alpha.getpixel((x, height - 1)):
            raise RepairRefused("subject_touches_frame")
        boundary.extend((source.getpixel((x, 0)), source.getpixel((x, height - 1))))
    for y in range(1, height - 1):
        if alpha.getpixel((0, y)) or alpha.getpixel((width - 1, y)):
            raise RepairRefused("subject_touches_frame")
        boundary.extend((source.getpixel((0, y)), source.getpixel((width - 1, y))))
    background = boundary[0]
    if any(any(abs(pixel[k] - background[k]) > COLOR_TOLERANCE for k in range(3))
           for pixel in boundary):
        raise RepairRefused("background_not_uniform")

    # Flood-fill only the zero-alpha region connected to the image exterior.
    # The near-exterior band is bounded to four pixels, preventing edits to
    # interior holes or distant similarly colored product details.
    exterior = alpha.point(lambda value: 255 if value == 0 else 0)
    ImageDraw.floodfill(exterior, (0, 0), 128, thresh=0)
    exterior = exterior.point(lambda value: 255 if value == 128 else 0)
    near_exterior = exterior.filter(ImageFilter.MaxFilter(2 * MAX_FRINGE + 1))

    changed = Image.new("L", source.size, 0)
    source_pixels = source.load()
    alpha_pixels = alpha.load()
    exterior_pixels = near_exterior.load()
    changed_pixels = changed.load()
    count = 0
    for y in range(height):
        for x in range(width):
            if not alpha_pixels[x, y] or not exterior_pixels[x, y]:
                continue
            pixel = source_pixels[x, y]
            if all(abs(pixel[k] - background[k]) <= COLOR_TOLERANCE for k in range(3)):
                changed_pixels[x, y] = 255
                count += 1
    return background, changed, count


def diagnose(source: Path, mask: Path) -> FringeDiagnosis:
    image, alpha = _inputs(source, mask)
    background, _, count = _fringe(image, alpha)
    foreground = sum(1 for pixel in alpha.tobytes() if pixel)
    if not count:
        raise RepairRefused("no_verifiable_background_fringe")
    if count > max(1, int(foreground * 0.12)):
        raise RepairRefused("fringe_removal_exceeds_12_percent")
    return FringeDiagnosis(background, count, foreground, sha256(source), sha256(mask))


def _render(source: Path, mask: Path, destination: Path,
            expected: FringeDiagnosis) -> dict:
    if sha256(source) != expected.source_sha256 or sha256(mask) != expected.mask_sha256:
        raise RepairRefused("source_or_mask_changed")
    image, alpha = _inputs(source, mask)
    background, changes, count = _fringe(image, alpha)
    if background != expected.background or count != expected.fringe_pixels:
        raise RepairRefused("diagnosis_changed")
    # Modifies alpha only; foreground RGB and upstream inputs are untouched.
    alpha.paste(0, mask=changes)
    _, _, remaining = _fringe(image, alpha)
    retained = sum(1 for pixel in alpha.tobytes() if pixel)
    if remaining or not retained or count > expected.foreground_pixels * 0.12:
        raise RepairRefused("technical_validation_failed")
    image.putalpha(alpha)
    image.save(destination, format="PNG")
    with Image.open(destination) as result:
        if result.mode != "RGBA" or result.size != image.size or result.getchannel("A").getextrema() == (0, 0):
            raise RepairRefused("invalid_repaired_image")
        if result.convert("RGB").tobytes() != image.convert("RGB").tobytes():
            raise RepairRefused("source_rgb_modified")
    return {"fringe_before": count, "fringe_after": remaining,
            "foreground_before": expected.foreground_pixels,
            "foreground_after": retained, "width": image.width, "height": image.height}


def _operation_id(journal: Journal, asset: str, target: str,
                  diagnosis: FringeDiagnosis) -> str:
    material = {
        "algorithm": ALGORITHM, "policy": POLICY,
        "batch": journal.root.name, "asset": asset, "target": target,
        "source": diagnosis.source_sha256, "mask": diagnosis.mask_sha256,
        "attempt": 1,
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()


def _schema(journal: Journal) -> None:
    journal.db.execute("""
        CREATE TABLE IF NOT EXISTS local_repairs (
          operation_id TEXT PRIMARY KEY,
          asset_id TEXT NOT NULL, target_id TEXT NOT NULL,
          source_sha256 TEXT NOT NULL, mask_sha256 TEXT NOT NULL,
          algorithm TEXT NOT NULL, policy TEXT NOT NULL,
          attempt INTEGER NOT NULL CHECK (attempt=1),
          status TEXT NOT NULL CHECK (status IN ('prepared','running','accepted','review')),
          output_sha256 TEXT, detail TEXT NOT NULL DEFAULT '{}',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    journal.db.commit()


def _state(journal: Journal, operation_id: str, status: str,
           output_sha256: str | None, detail: dict) -> None:
    if status not in ("running", "accepted", "review"):
        raise ValueError("Unsupported repair state")
    journal.db.execute("BEGIN IMMEDIATE")
    try:
        row = journal.db.execute(
            "SELECT status FROM local_repairs WHERE operation_id=?", (operation_id,)
        ).fetchone()
        if row is None or row["status"] == "accepted":
            raise ArtifactIntegrityError("Repair receipt missing or already accepted")
        journal.db.execute("""
            UPDATE local_repairs SET status=?, output_sha256=?, detail=?,
            updated_at=CURRENT_TIMESTAMP WHERE operation_id=?
        """, (status, output_sha256, json.dumps(detail, sort_keys=True), operation_id))
        journal.db.commit()
    except BaseException:
        journal.db.rollback()
        raise


def _receipt(journal: Journal, operation_id: str) -> dict:
    row = journal.db.execute(
        "SELECT * FROM local_repairs WHERE operation_id=?", (operation_id,)
    ).fetchone()
    return dict(row)


def run_product_repair(journal: Journal, source: Path, mask: Path, *,
                       asset_id: str, target_id: str, cohort: str = "product",
                       accepted_output_exists: bool = False,
                       remote_charge_uncertain: bool = False,
                       awaiting_provider_submission: bool = False) -> dict:
    """One durable *logical* attempt; crash replay may recompute local pixels.

    No provider, model, network access or accepted deliverable is contacted.
    The resulting file remains an isolated TECHNICALLY accepted demo candidate;
    the normal production Engine is not automatically updated.
    """
    if not isinstance(journal, Journal) or any(
            not isinstance(value, str) or not _ID.fullmatch(value)
            for value in (asset_id, target_id)):
        raise ValueError("Unsafe asset/target ID or journal")
    if cohort != "product":
        return {"status": "human_review", "reason": "portrait_or_other_cohort_unsupported",
                "would_spend_usd": 0}
    if (accepted_output_exists or remote_charge_uncertain or awaiting_provider_submission):
        return {"status": "human_review", "reason": "accepted_or_remote_state_unsafe",
                "would_spend_usd": 0}
    with journal.exclusive():
        if (journal.root / "selected").exists():
            return {"status": "human_review", "reason": "existing_selected_artifacts",
                    "would_spend_usd": 0}
        try:
            diagnosis = diagnose(source, mask)
        except RepairRefused as exc:
            return {"status": "human_review", "reason": str(exc), "would_spend_usd": 0}
        policy = RepairLimits(allow_local_mask_repair=True,
                              allow_technical_auto_rejection=False,
                              maximum_local_repairs=1,
                              maximum_total_stage_attempts=2)
        plan = decide_candidate(CandidateState(
            cohort="product", technical_issue="alpha_edge_contamination",
            stage="cutout", stage_attempts=0, local_repairs_used=0), policy)
        if plan.action != "repair_local_mask":
            return {"status": "human_review", "reason": plan.reason_code,
                    "would_spend_usd": 0}
        _schema(journal)
        op_id = _operation_id(journal, asset_id, target_id, diagnosis)
        # A changed input must not reset the one-repair cap per target.
        other = journal.db.execute(
            "SELECT operation_id FROM local_repairs WHERE asset_id=? AND target_id=? AND operation_id<>?",
            (asset_id, target_id, op_id)
        ).fetchone()
        if other is not None:
            return {"status": "human_review", "reason": "target_repair_attempt_exhausted",
                    "would_spend_usd": 0}
        output = journal.root / "repairs" / op_id / "repaired.png"
        journal.db.execute("BEGIN IMMEDIATE")
        try:
            journal.db.execute("""
                INSERT OR IGNORE INTO local_repairs(
                  operation_id,asset_id,target_id,source_sha256,mask_sha256,
                  algorithm,policy,attempt,status
                ) VALUES (?,?,?,?,?,?,?,?,?)
            """, (op_id, asset_id, target_id, diagnosis.source_sha256,
                  diagnosis.mask_sha256, ALGORITHM, POLICY, 1, "prepared"))
            journal.db.commit()
        except BaseException:
            journal.db.rollback()
            raise
        record = _receipt(journal, op_id)
        if record["status"] == "accepted":
            verified_image(output, record["output_sha256"])
            return {"status": "technically_accepted", "reason": "verified_replay",
                    "operation_id": op_id, "output": str(output),
                    "output_sha256": record["output_sha256"],
                    "metrics": json.loads(record["detail"]), "would_spend_usd": 0}
        if record["status"] == "review":
            return {"status": "human_review", "reason": json.loads(record["detail"]).get("reason", "prior_review"),
                    "operation_id": op_id, "would_spend_usd": 0}
        _state(journal, op_id, "running", None, {"reason": plan.reason_code})
        try:
            with temporary_sibling(output) as candidate:
                metrics = _render(source, mask, candidate, diagnosis)
                digest = sha256(candidate)
                if output.exists():
                    # Crash after atomic publication, before SQLite acknowledgment.
                    # Only adopt exactly reproducible bytes; never clobber a
                    # foreign, tampered or previously accepted file.
                    verified_image(output, digest)
                else:
                    os.replace(candidate, output)
                verified_image(output, digest)
            if sha256(source) != diagnosis.source_sha256 or sha256(mask) != diagnosis.mask_sha256:
                raise RepairRefused("upstream_changed_during_publish")
            _state(journal, op_id, "accepted", digest, metrics)
            return {"status": "technically_accepted", "reason": "verified_local_refinement",
                    "operation_id": op_id, "output": str(output),
                    "output_sha256": digest, "metrics": metrics, "would_spend_usd": 0}
        except (RepairRefused, OSError, ValueError) as exc:
            # Preserve any staged file for audit; never automatically accept it.
            detail = {"reason": str(exc)[:200]}
            _state(journal, op_id, "review", None, detail)
            return {"status": "human_review", "reason": detail["reason"],
                    "operation_id": op_id, "would_spend_usd": 0}
