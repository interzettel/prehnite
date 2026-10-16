"""No-network TypeSafe Jev 1.14 request plan and documented-response fixture reader.

This module constructs an INERT request example and parses mocked official
response shapes. It has no HTTP client, API key, retry logic or dispatch API.
Vendor image/Box features remain experimental, never production acceptance.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

from .typed_visual import (
    MODEL, ImageReceipt, Preflight, _KEY, validate_questions, Question,
    MAX_REQUEST_BYTES,
)


@dataclass(frozen=True)
class VendorQuestion:
    key: str
    kind: str
    instructions: str
    # Descriptions for Choice (option,label), ordered level descriptions for Score.
    options: tuple[tuple[str, str], ...] = ()
    levels: tuple[str, ...] = ()
    presence_key: str | None = None

    def __post_init__(self):
        if not _KEY.fullmatch(self.key) or self.kind not in ("noul", "choice", "score", "box"):
            raise ValueError("Invalid typed question identifier or kind")
        if (not isinstance(self.instructions, str) or
                not 10 <= len(self.instructions) <= 400 or
                any(ord(c) < 32 for c in self.instructions)):
            raise ValueError("Use one bounded, explicit atomic question")
        if self.kind == "choice":
            if (not 2 <= len(self.options) <= 12 or self.levels or
                    any(not isinstance(k, str) or not _KEY.fullmatch(k) or
                        not isinstance(v, str) or not 1 <= len(v) <= 120
                        for k, v in self.options) or
                    len(set(k for k, _ in self.options)) != len(self.options)):
                raise ValueError("Choice requires 2–12 unique bounded criteria")
        elif self.options:
            raise ValueError("Choice criteria only for Choice questions")
        if self.kind == "score":
            if not 2 <= len(self.levels) <= 10 or any(
                    not isinstance(s, str) or not 1 <= len(s) <= 120 for s in self.levels):
                raise ValueError("Score requires 2–10 distinct described levels")
        elif self.levels:
            raise ValueError("Score levels only for Score questions")
        if self.kind == "box":
            if not self.presence_key or not _KEY.fullmatch(self.presence_key):
                raise ValueError("Box needs a Noul presence-gate identifier")
        elif self.presence_key:
            raise ValueError("Presence gating only applies to Box")


def validate_vendor_questions(questions: tuple[VendorQuestion, ...]) -> None:
    if not isinstance(questions, tuple) or not 1 <= len(questions) <= 12:
        raise ValueError("Requires 1–12 official-format questions")
    by_key = {q.key: q.kind for q in questions}
    if len(by_key) != len(questions):
        raise ValueError("Duplicate question identifiers")
    for q in questions:
        if q.kind == "box" and by_key.get(q.presence_key) != "noul":
            raise ValueError("Box must be tied to a Noul presence question")


@dataclass(frozen=True)
class RequestFixture:
    model: str
    request_json: dict = field(repr=False)
    proposed_headers: dict = field(repr=False)
    serialized_bytes: int
    estimated_expanded_bytes: int
    asset_sha256: str
    status: str = "offline_fixture_never_dispatched"


def build_offline_request_fixture(
        receipt: ImageReceipt, permit: Preflight,
        questions: tuple[VendorQuestion, ...]) -> RequestFixture:
    """Inert documentation fixture. NOT an authorization to send to TypeSafe."""
    validate_vendor_questions(questions)
    if (permit.status != "local_preflight_only_no_dispatch" or permit.model != MODEL
            or permit.image_sha256 != receipt.prepared_sha256
            or permit.question_count != len(questions)
            or hashlib.sha256(receipt.data).hexdigest() != receipt.prepared_sha256):
        raise ValueError("No valid image/permit binding for inert request")
    internal = tuple(
        Question(q.key, q.kind,
                 options=tuple(k for k, _ in q.options),
                 presence_key=q.presence_key)
        for q in questions)
    validate_questions(internal)
    asset_ref = "asset_" + receipt.prepared_sha256[:28]
    qmap: dict[str, dict] = {}
    for q in questions:
        question = {"type": q.kind, "instructions": q.instructions}
        if q.kind == "choice":
            question["criteria"] = dict(q.options)
        elif q.kind == "score":
            question["criteria"] = list(q.levels)
        qmap[q.key] = question
    # There is one literal image asset reference only, in state.image.
    # Question instructions refer to the STATE FIELD `image`; never insert
    # asset_ref again (every additional replacement incurs image tokens).
    raw = {
        "model": MODEL, "state": {"image": asset_ref},
        "assets": {asset_ref: {"type": "image", "format": receipt.format,
                              "data_base64": base64.b64encode(receipt.data).decode("ascii")}},
        "questions": qmap,
    }
    payload = json.dumps(raw, separators=(",", ":"), ensure_ascii=True)
    wire_size = len(payload.encode("utf-8"))
    # The API may re-encode image content, increasing expanded size.
    # The x2 media allowance is a *local estimate*, not provider accounting.
    expanded = wire_size + receipt.byte_count * 2
    if wire_size > MAX_REQUEST_BYTES or expanded > MAX_REQUEST_BYTES:
        raise ValueError("Inert expanded request estimate exceeds 32 MiB")
    headers = {"TypeSafe-Danger-Zone-Images": "true"}
    if permit.experimental_long_context:
        headers["TypeSafe-Danger-Zone-Long-Context"] = "true"
    return RequestFixture(MODEL, raw, headers, wire_size, expanded,
                          receipt.prepared_sha256)


def _prob(number: object, label: str) -> float:
    if type(number) not in (float, int) or not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f"{label} must be finite between 0 and 1")
    return float(number)


def _distribution(value: object, expected_keys: set[str]) -> dict[str, float]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ValueError("Unexpected option probability distribution")
    dist = {key: _prob(v, "probability") for key, v in value.items()}
    if abs(sum(dist.values()) - 1.0) > 0.001:
        raise ValueError("Probabilities do not sum to one")
    return dist


def parse_official_mock_response(
        questions: tuple[VendorQuestion, ...],
        response: object, *, presence_threshold: float = 0.85,
        max_input_tokens: int | None = None) -> dict:
    """Parse offline synthetic fixtures shaped after documented TypeSafe JSON.

    Noul outputs the YES probability (NOT a Boolean). Score outputs the mean
    over configured integer level positions (NOT a normalized 0..1 rubric).
    Box is always returned by Jev; downstream hides it if presence is low.
    """
    validate_vendor_questions(questions)
    threshold = _prob(presence_threshold, "presence_threshold")
    if not isinstance(response, dict) or set(response) != {"model", "answers", "usage"}:
        raise ValueError("Unexpected Jev root response shape")
    if response["model"] != MODEL:
        raise ValueError("Response model revision differs from pinned Jev")
    answers, usage = response["answers"], response["usage"]
    if not isinstance(answers, dict) or set(answers) != {q.key for q in questions}:
        raise ValueError("Wrong or missing Jev answer IDs")
    if (not isinstance(usage, dict) or set(usage) != {"input_tokens", "output_tokens"}
            or any(type(v) is not int or v < 0 for v in usage.values())):
        raise ValueError("Invalid Jev token usage")
    if (max_input_tokens is not None and (type(max_input_tokens) is not int
            or usage["input_tokens"] > max_input_tokens)):
        raise ValueError("Observed tokens exceed reserved input ceiling")
    normalized: dict[str, dict] = {}
    by_key = {q.key: q for q in questions}
    for q in questions:
        item = answers[q.key]
        if not isinstance(item, dict) or item.get("type") != q.kind:
            raise ValueError("Jev answer kind mismatch")
        if q.kind == "noul":
            if set(item) != {"type", "noul"}:
                raise ValueError("Noul must return probability only")
            normalized[q.key] = {"type": "noul",
                                 "yes_probability": _prob(item["noul"], "noul")}
        elif q.kind == "choice":
            if set(item) != {"type", "choice", "confidence", "probabilities"}:
                raise ValueError("Choice response fields differ from documented shape")
            choices = {key for key, _ in q.options}
            probs = _distribution(item["probabilities"], choices)
            label = item["choice"]
            if not isinstance(label, str) or label not in choices or (
                    probs[label] < max(probs.values()) - 0.001):
                raise ValueError("Selected option inconsistent with distribution")
            normalized[q.key] = {
                "type": "choice", "selected": label,
                "probabilities": probs, "confidence": _prob(item["confidence"], "confidence")}
        elif q.kind == "score":
            if set(item) != {"type", "score", "confidence", "legend", "probabilities"}:
                raise ValueError("Score response fields differ from documented shape")
            keys = {str(i) for i in range(len(q.levels))}
            dist = _distribution(item["probabilities"], keys)
            if not isinstance(item["legend"], dict) or item["legend"] != {
                    str(i): level for i, level in enumerate(q.levels)}:
                raise ValueError("Score legend differs from declared levels")
            score = item["score"]
            if type(score) not in (int, float) or not math.isfinite(score):
                raise ValueError("Invalid Score numeric position")
            expected = sum(int(k) * p for k, p in dist.items())
            # API examples round level-weighted score to two decimals.
            if not 0 <= score <= len(q.levels)-1 or abs(float(score)-expected) > 0.02:
                raise ValueError("Score inconsistent with level distribution")
            normalized[q.key] = {"type": "score", "position": float(score),
                                 "level_probabilities": dist,
                                 "confidence": _prob(item["confidence"], "confidence")}
        else:
            if set(item) != {"type", "box", "confidence"}:
                raise ValueError("Box response fields differ from documented shape")
            box = item["box"]
            if not isinstance(box, dict) or set(box) != {"left","top","right","bottom"}:
                raise ValueError("Box must contain documented four edges")
            values = {k: _prob(v, "box edge") for k,v in box.items()}
            if not (values["left"] < values["right"] and values["top"] < values["bottom"]):
                raise ValueError("Invalid normalized Box edges")
            gate = answers[q.presence_key]
            if not isinstance(gate, dict) or set(gate) != {"type", "noul"}:
                raise ValueError("Box presence gate is malformed")
            presence = _prob(gate["noul"], "presence")
            normalized[q.key] = {
                "type":"box", "box":values if presence >= threshold else None,
                "masked_due_to_presence": presence < threshold,
                "presence_yes_probability": presence,
                "confidence":_prob(item["confidence"],"confidence"),
            }
    return {"schema_version": 1, "status":"offline_vendor_response_fixture_only",
            "model": MODEL, "automatic_acceptance_authorized": False,
            "confidence_calibrated_on_our_images": False,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "answers": normalized}
