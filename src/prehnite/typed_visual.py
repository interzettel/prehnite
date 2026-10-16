"""Offline-only Jev-inspired typed visual evaluation contracts (#109).

No TypeSafe SDK, API key, HTTP transport or provider wire payload here. This
preflight and mocked adapter explicitly CANNOT perform paid inference.
"""
from __future__ import annotations

import hashlib
import io
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageOps

from .artifacts import ArtifactIntegrityError
from .schema import relative_name

MODEL = "jev-1.14.0"
PRICE_USD_PER_MILLION_INPUT_TOKENS = Decimal("0.042")  # Quote; verify before live use.
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_REQUEST_BYTES = 32 * 1024 * 1024
MAX_SOURCE_PIXELS = 24_000_000
MIN_DIMENSION = 280
MAX_DIMENSION = 1568
DEFAULT_CONTEXT_LIMIT = 64_000
EXPERIMENTAL_CONTEXT_LIMIT = 262_000
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True)
class Question:
    """Internal stable question format, NOT the TypeSafe wire/SDK schema."""

    key: str
    kind: str  # noul | choice | score | box
    options: tuple[str, ...] = ()
    presence_key: str | None = None

    def __post_init__(self):
        if not _KEY.fullmatch(self.key):
            raise ValueError("Unsafe visual question key")
        if self.kind not in ("noul", "choice", "score", "box"):
            raise ValueError("Unsupported visual question kind")
        if self.kind == "choice":
            if (not 2 <= len(self.options) <= 12 or len(set(self.options)) != len(self.options)
                    or any(not _KEY.fullmatch(opt) for opt in self.options)):
                raise ValueError("Choice requires 2–12 distinct safe labels")
        elif self.options:
            raise ValueError("Options are only supported for Choice")
        if self.kind == "box":
            if not self.presence_key or not _KEY.fullmatch(self.presence_key):
                raise ValueError("Box requires a presence-gating Noul question")
        elif self.presence_key is not None:
            raise ValueError("Only Box can depend on a presence question")


def validate_questions(questions: tuple[Question, ...]) -> None:
    if not isinstance(questions, tuple) or not 1 <= len(questions) <= 12:
        raise ValueError("Expected 1–12 typed questions")
    keys = [q.key for q in questions]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate visual question keys")
    kinds = {q.key: q.kind for q in questions}
    for question in questions:
        if question.kind == "box" and kinds.get(question.presence_key) != "noul":
            raise ValueError("Box must reference a Noul question in this request")


@dataclass(frozen=True)
class ImageReceipt:
    """Locally sanitized still-image bytes; never log/share without consent."""

    source_sha256: str
    prepared_sha256: str
    width: int
    height: int
    format: str
    byte_count: int
    data: bytes = field(repr=False)


def prepare_still_image(root: Path, relative_path: str, source_sha256: str) -> ImageReceipt:
    """Re-encode one verified authorized still; EXIF/ICC metadata is not forwarded.

    ICC-tagged sources fail closed rather than silently changing color meaning.
    The caller must obtain the recorded source hash from the owner's journal.
    """
    if not isinstance(source_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", source_sha256):
        raise ArtifactIntegrityError("Missing historical image SHA256")
    base = Path(root).resolve()
    path = (base / relative_name(relative_path)).resolve()
    if not path.is_relative_to(base):
        raise ArtifactIntegrityError("Image escapes authorized input directory")
    if not path.is_file() or path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError("Source image absent or exceeds 16 MiB source limit")
    original = path.read_bytes()
    if hashlib.sha256(original).hexdigest() != source_sha256:
        raise ArtifactIntegrityError("Image changed since source fingerprint")
    with Image.open(io.BytesIO(original)) as image:
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("Animated images and native video are unsupported")
        if image.width * image.height > MAX_SOURCE_PIXELS:
            raise ValueError("Source image exceeds 24 MP safety limit")
        if image.info.get("icc_profile"):
            raise ValueError("ICC-tagged source requires an explicit color conversion policy")
        upright = ImageOps.exif_transpose(image)
        if upright.mode not in ("RGB", "RGBA", "L", "P"):
            raise ValueError("Unsupported source pixel mode")
        if max(upright.size) > MAX_DIMENSION:
            upright.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
        if min(upright.size) < MIN_DIMENSION:
            raise ValueError("Image too narrow for Jev's minimum 280px dimensions")
        is_alpha = upright.mode == "RGBA" or (
            upright.mode == "P" and "transparency" in upright.info)
        mode = "RGBA" if is_alpha else "RGB"
        # Explicitly construct fresh pixels: avoids copying EXIF, comments,
        # GPS coordinates, filenames and other image metadata to output.
        clean = Image.new(mode, upright.size)
        clean.paste(upright.convert(mode))
        output = io.BytesIO()
        fmt = "png" if is_alpha else "jpg"
        if is_alpha:
            clean.save(output, format="PNG", optimize=False)
        else:
            clean.save(output, format="JPEG", quality=85, progressive=False,
                       optimize=False)
    data = output.getvalue()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Prepared image exceeds 16 MiB")
    return ImageReceipt(
        source_sha256=source_sha256,
        prepared_sha256=hashlib.sha256(data).hexdigest(),
        width=clean.width, height=clean.height,
        format=fmt, byte_count=len(data), data=data,
    )


@dataclass(frozen=True)
class Preflight:
    """No transport is provided. A permit is not approval for an HTTP request."""

    model: str
    image_sha256: str
    question_count: int
    input_token_ceiling: int
    reserved_usd: Decimal
    experimental_images: bool
    experimental_long_context: bool
    status: str = "local_preflight_only_no_dispatch"


def preflight(
        image: ImageReceipt, questions: tuple[Question, ...], *,
        allow_paid: bool = False,
        allow_cloud_uploads: bool = False,
        allow_experimental_images: bool = False,
        allow_experimental_box: bool = False,
        allow_long_context: bool = False,
        input_token_ceiling: int | None = None,
        max_usd: Decimal = Decimal("0"),
        price_usd_per_million: Decimal = PRICE_USD_PER_MILLION_INPUT_TOKENS,
        model: str = MODEL,
) -> Preflight:
    """Fail-closed local cost and privacy preflight; no API use or billing."""
    validate_questions(questions)
    if model != MODEL:
        raise ValueError("Use a pinned experimental Jev model revision")
    if not (allow_paid and allow_cloud_uploads and allow_experimental_images):
        raise PermissionError("Explicit paid, cloud and danger-zone image opt-ins required")
    if any(q.kind == "box" for q in questions) and not allow_experimental_box:
        raise PermissionError("Experimental Box requires separate opt-in")
    if type(input_token_ceiling) is not int or input_token_ceiling <= 0:
        raise ValueError("Provide an explicit conservative input-token ceiling")
    if input_token_ceiling > (EXPERIMENTAL_CONTEXT_LIMIT if allow_long_context
                             else DEFAULT_CONTEXT_LIMIT):
        raise ValueError("Token ceiling exceeds opt-in context limit")
    if not isinstance(max_usd, Decimal) or not max_usd.is_finite() or max_usd <= 0:
        raise ValueError("User must authorize a finite positive Decimal USD budget")
    if (not isinstance(price_usd_per_million, Decimal)
            or not price_usd_per_million.is_finite()
            or price_usd_per_million <= 0):
        raise ValueError("Explicit finite positive pricing is required")
    if (not isinstance(image, ImageReceipt)
            or image.byte_count != len(image.data)
            or image.byte_count > MAX_IMAGE_BYTES
            or image.width not in range(MIN_DIMENSION, MAX_DIMENSION + 1)
            or image.height not in range(MIN_DIMENSION, MAX_DIMENSION + 1)
            or image.format not in ("jpg", "png")
            or hashlib.sha256(image.data).hexdigest() != image.prepared_sha256):
        raise ArtifactIntegrityError("Prepared image invalid or corrupted")
    # Single distinct image, referenced only once in a hypothetical state.
    # Future wire adapter MUST independently account for expanded requests,
    # model tokenization, response errors and reservations before dispatch.
    if image.byte_count + 4096 > MAX_REQUEST_BYTES:
        raise ValueError("Request body exceeds conservative limit")
    reserved = (Decimal(input_token_ceiling) * price_usd_per_million
                / Decimal(1_000_000))
    if reserved > max_usd:
        raise PermissionError("Owner's USD ceiling does not cover conservative reservation")
    return Preflight(MODEL, image.prepared_sha256, len(questions),
                     input_token_ceiling, reserved, True, allow_long_context)


def _number(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    result = float(value)
    if not 0 <= result <= 1:
        raise ValueError(f"{label} must be between 0 and 1")
    return result


def parse_mock_answers(questions: tuple[Question, ...], raw: object) -> dict:
    """Strict internal mocked response; NOT a claim about vendor wire payload.

    Even a provider-generated confidence is not a verified probability or an
    acceptance instruction. Box coordinates are normalized x0,y0,x1,y1.
    """
    validate_questions(questions)
    if not isinstance(raw, dict) or set(raw) != {q.key for q in questions}:
        raise ValueError("Mock answers must cover every question exactly")
    answer: dict = {}
    for question in questions:
        entry = raw[question.key]
        if not isinstance(entry, dict) or set(entry) != {"value", "confidence"}:
            raise ValueError("Mock answer has unexpected or missing fields")
        confidence = _number(entry["confidence"], "uncalibrated confidence")
        value = entry["value"]
        if question.kind == "noul":
            if type(value) is not bool:
                raise ValueError("Noul requires an exact boolean")
        elif question.kind == "choice":
            if not isinstance(value, str) or value not in question.options:
                raise ValueError("Choice must match a declared label")
        elif question.kind == "score":
            value = _number(value, "rubric score")
        else:
            present = raw[question.presence_key]["value"]
            if type(present) is not bool:
                raise ValueError("Box presence gate must be boolean")
            if not present:
                if value is not None:
                    raise ValueError("Absent object cannot have a Box")
            else:
                if (not isinstance(value, list) or len(value) != 4):
                    raise ValueError("Present Box requires four normalized coordinates")
                x0, y0, x1, y1 = [_number(v, "Box coordinate") for v in value]
                if not (x0 < x1 and y0 < y1):
                    raise ValueError("Box edges must be ordered and nonzero")
                value = [x0, y0, x1, y1]
        answer[question.key] = {
            "kind": question.kind, "value": value,
            "uncalibrated_confidence": confidence,
            "human_verified": False,
        }
    return {"schema_version": 1,
            "status": "mock_evaluation_only_no_provider_dispatch",
            "provider": "jev", "model": MODEL,
            "automatic_acceptance_authorized": False,
            "answers": answer}
