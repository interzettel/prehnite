"""Read-only reviewed-image handoff evidence: source + original review + typed receipt.

An operator-created JSON attestation does not establish human identity or
automatic model/segmentation quality. It only pins the exact bytes and claimed
human approval for one new source-only local batch.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .images import image_info, sha256
from .manifest import resolve_input
from .schema import Manifest, Profile


MAX_RECEIPT_BYTES = 64 * 1024


def verify_handoff(manifest: Manifest, profile: Profile, inputs: Path) -> dict:
    """Fail closed before creating a journal, performing inference or uploading."""
    handoff = manifest.handoff
    if handoff is None:
        raise ValueError("No reviewed-source handoff specified")
    asset = manifest.assets[0]
    if (len(manifest.assets) != 1 or not asset.source or asset.prompt
            or len(asset.targets) != 1 or manifest.id == handoff.source_batch):
        raise ValueError("Handoff requires one reviewed source and a new batch ID")
    if (profile.variants or profile.generation.provider != "disabled"
            or profile.upscale.provider != "disabled"
            or profile.segmentation.provider != "comfyui"
            or profile.judge.provider != "disabled"):
        raise ValueError("Handoff requires source-only local ComfyUI cutout, no generation/judge")
    if (profile.policy.maximum_attempts != 1
            or profile.policy.uncertain != "reject"
            or profile.policy.local_repair_mode != "disabled"):
        raise ValueError("Handoff forbids retries, uncertainty bypass and automatic repair")
    if (profile.costs.allow_paid or profile.costs.allow_cloud_uploads
            or profile.costs.max_usd != 0 or profile.costs.estimates_usd
            or profile.cache.enabled or profile.cache.allow_paid):
        raise ValueError("Handoff forbids paid/cloud/cache policy")
    if not profile.segmentation.options.get("target_node"):
        raise ValueError("Reviewed cutout needs an explicit target_node")
    if not profile.segmentation.options.get("output_node"):
        raise ValueError("Reviewed cutout needs an explicit output_node")
    if asset.source in (handoff.review_receipt, handoff.review_document):
        raise ValueError("Image source and review evidence must be different files")
    source = resolve_input(inputs, asset.source)
    original_review = resolve_input(inputs, handoff.review_document)
    receipt_path = resolve_input(inputs, handoff.review_receipt)
    original_sha = sha256(source)
    if original_sha != handoff.candidate_sha256:
        raise ValueError("Reviewed source SHA256 mismatch; cannot advance candidate")
    info = image_info(source)
    if (info["width"], info["height"]) != tuple(asset.target_size):
        raise ValueError("Reviewed source has wrong native geometry")
    if original_review.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Original human review document exceeds bounded size")
    if sha256(original_review) != handoff.review_document_sha256:
        raise ValueError("Original human review document SHA256 mismatch")
    if not (0 < receipt_path.stat().st_size <= MAX_RECEIPT_BYTES):
        raise ValueError("Structured handoff receipt is empty or oversized")
    if sha256(receipt_path) != handoff.review_receipt_sha256:
        raise ValueError("Structured handoff receipt SHA256 mismatch")
    try:
        evidence = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Structured handoff receipt must be valid UTF-8 JSON") from exc
    expected = {
        "schema_version": 1,
        "source_batch": handoff.source_batch,
        "candidate_sha256": handoff.candidate_sha256,
        "original_review_sha256": handoff.review_document_sha256,
        "verdict": "accepted_for_next_stage",
        "target_phrase": handoff.target_phrase,
        "include": handoff.include,
        "exclude": handoff.exclude,
    }
    if evidence != expected:
        raise ValueError("Human review receipt disagrees with pinned handoff claims")
    return {
        "schema_version": 1,
        "source_batch": handoff.source_batch,
        "candidate_sha256": handoff.candidate_sha256,
        "review_receipt_sha256": handoff.review_receipt_sha256,
        "original_review_sha256": handoff.review_document_sha256,
        "verdict": "accepted_for_next_stage",
        "target_phrase": handoff.target_phrase,
        "include": handoff.include,
        "exclude": handoff.exclude,
        "generation_skipped": True,
        "human_reviewed_source": True,
        "automatic_quality_verified": False,
        "segmentation_quality_verified": False,
        "operator_attested_not_independently_authenticated": True,
    }
