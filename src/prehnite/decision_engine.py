"""Local-first, provider-neutral decision evidence and bounded action policy.

No provider transport, credentials, hidden billing, inference, or asset mutation.
Experimental model judgments are not calibrated by virtue of being typed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from .judges import Verdict

_SAFE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_SUBJECT = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_HEX = re.compile(r"^[a-f0-9]{64}$")
Kind = Literal["presence_probability", "category_choice", "rubric_score",
               "bounding_box", "technical_flag"]
Action = Literal["accept", "reject_candidate", "repair_local_mask", "human_review"]
_TKNOWN = frozenset({
    "mask_empty", "mask_full_frame", "alpha_edge_contamination",
    "image_geometry_invalid", "wrong_image_encoding", "subject_instance_ambiguous",
    "none",
})
_REPAIRABLE = frozenset({"alpha_edge_contamination"})
_HARD_REJECT = frozenset({"mask_full_frame", "image_geometry_invalid",
                          "wrong_image_encoding"})
_PROVIDERS = ("jev", "openai-compatible", "anthropic", "local")


def _prob(value: object) -> float:
    if type(value) not in (int, float):
        raise ValueError("Probability/rubric score must be a JSON number, not Boolean")
    number = float(value)
    if not 0 <= number <= 1 or number != number:
        raise ValueError("Probability/rubric score outside finite [0,1]")
    return number


@dataclass(frozen=True)
class ModelCapabilities:
    provider: str
    model: str
    kinds: tuple[str, ...]
    media: tuple[str, ...]
    external_upload: bool
    experimental: bool
    declares_calibrated_confidence: bool = False

    def __post_init__(self) -> None:
        if self.provider not in _PROVIDERS:
            raise ValueError("Unknown decision model provider")
        if (not isinstance(self.model, str) or not _SAFE.fullmatch(self.model)
                or not self.kinds or len(set(self.kinds)) != len(self.kinds)
                or any(k not in ("presence_probability", "category_choice",
                                 "rubric_score", "bounding_box", "technical_flag")
                       for k in self.kinds)):
            raise ValueError("Invalid model or typed capabilities")
        if (not self.media or len(set(self.media)) != len(self.media)
                or any(m not in ("text", "still_image", "frame_sequence") for m in self.media)):
            raise ValueError("Invalid supported input media")
        if any(type(x) is not bool for x in (
                self.external_upload, self.experimental, self.declares_calibrated_confidence)):
            raise ValueError("Capabilities must explicitly declare Booleans")
        # Supplier confidence does not confer independently verified calibration.
        if self.declares_calibrated_confidence:
            raise ValueError("Provider capability cannot self-certify calibration")
        if self.provider == "local" and self.external_upload:
            raise ValueError("Local judge cannot require external image upload")


CAPABILITIES = {
    "jev": ModelCapabilities(
        "jev", "jev-1_14_0",
        ("presence_probability", "category_choice", "rubric_score", "bounding_box"),
        ("text", "still_image"), True, True),
    "openai-compatible": ModelCapabilities(
        "openai-compatible", "mock_structured_v1",
        ("presence_probability", "category_choice", "rubric_score"),
        ("text", "still_image"), True, False),
    "anthropic": ModelCapabilities(
        "anthropic", "mock_pairwise_v1", ("rubric_score",),
        ("text", "still_image"), True, False),
    "local": ModelCapabilities(
        "local", "technical_v1", ("technical_flag",),
        ("text", "still_image"), False, False),
}


@dataclass(frozen=True)
class DecisionEvidence:
    provider: str
    model: str
    kind: Kind
    value: bool | float | str | tuple[float, float, float, float]
    subject: str
    image_sha256: str
    calibrated: bool = False
    status: Literal["observed", "abstained"] = "observed"

    def __post_init__(self) -> None:
        if not isinstance(self.subject, str) or not _SUBJECT.fullmatch(self.subject):
            raise ValueError("Unsafe decision subject")
        if not isinstance(self.image_sha256, str) or not _HEX.fullmatch(self.image_sha256):
            raise ValueError("Missing SHA256-bound visual evidence")
        cap = CAPABILITIES.get(self.provider)
        if (cap is None or self.model != cap.model or self.kind not in cap.kinds):
            raise ValueError("Decision kind unsupported by declared provider revision")
        if type(self.calibrated) is not bool or self.calibrated:
            # Future true calibration requires an independently reviewed receipt
            # and a separately reviewed, versioned change to this gate.
            raise ValueError("Unverified calibration is not accepted")
        if self.status == "abstained":
            if self.value != "abstain":
                raise ValueError("Abstained observation must carry explicit abstain")
            return
        if self.status != "observed":
            raise ValueError("Unknown decision evidence status")
        if self.kind in ("presence_probability", "rubric_score"):
            _prob(self.value)
        elif self.kind == "technical_flag":
            if type(self.value) is not bool:
                raise ValueError("Technical check must be an actual Boolean")
        elif self.kind == "category_choice":
            if type(self.value) is not str or not _SAFE.fullmatch(self.value):
                raise ValueError("Category must be one bounded safe label")
        else:
            if (not isinstance(self.value, tuple) or len(self.value) != 4):
                raise ValueError("Bounding box must be four normalized coordinates")
            x0, y0, x1, y1 = (_prob(v) for v in self.value)
            if not x0 < x1 or not y0 < y1:
                raise ValueError("Invalid normalized bounding-box edges")


def require_capability(provider: str, *, kind: str, media: str,
                       cloud_upload_authorized: bool = False) -> ModelCapabilities:
    cap = CAPABILITIES.get(provider)
    if cap is None or kind not in cap.kinds or media not in cap.media:
        raise ValueError("Unsupported decision-model capability; abstain/fail closed")
    if cap.external_upload and not cloud_upload_authorized:
        raise PermissionError("Cloud decision model requires explicit image-upload approval")
    return cap


def normalized_mock_evidence(provider: str, *, response: dict,
                             subject: str, image_sha256: str) -> DecisionEvidence:
    """Convert mocked, validated output shapes only; no provider IO.

    Jev response comes from parse_official_mock_response(), which returns
    uncalibrated yes probabilities and ordinal score positions. We ONLY map
    Noul probabilities, never convert a Score or Box into a probability.
    """
    if not isinstance(response, dict):
        raise ValueError("No typed response")
    cap = CAPABILITIES.get(provider)
    if cap is None:
        raise ValueError("Unsupported decision provider")
    if provider == "jev":
        if (response.get("status") != "offline_vendor_response_fixture_only"
                or response.get("model") != "jev-1.14.0"
                or response.get("automatic_acceptance_authorized") is not False):
            raise ValueError("Jev fixture must be validated with the official parser")
        answers = response.get("answers")
        answer = answers.get(subject) if isinstance(answers, dict) else None
        if not isinstance(answer, dict) or answer.get("type") != "noul":
            raise ValueError("Only exact Noul probability can be normalized here")
        value = _prob(answer.get("yes_probability"))
        return DecisionEvidence(provider, cap.model, "presence_probability",
                                value, subject, image_sha256)
    if provider == "openai-compatible":
        # This is a Prehnite-generated local fixture, NOT an OpenAI API schema.
        if (set(response) != {"schema_version", "status", "question", "kind", "value"}
                or response["schema_version"] != 1
                or response["status"] != "offline_fixture_no_provider"):
            raise ValueError("Incorrect internal mock fixture shape")
        if response["question"] != subject or response["kind"] not in cap.kinds:
            raise ValueError("Mock question/provider capability mismatch")
        return DecisionEvidence(provider, cap.model, response["kind"],
                                response["value"], subject, image_sha256)
    if provider == "anthropic":
        if not isinstance(response.get("verdict"), Verdict):
            raise ValueError("Anthropic fixture requires validated rubric Verdict")
        verdict = response["verdict"]
        if verdict.winner != subject or subject not in verdict.scores:
            raise ValueError("Rubric winner must refer to tested subject")
        return DecisionEvidence(provider, cap.model, "rubric_score",
                                _prob(verdict.scores[subject]), subject, image_sha256)
    if set(response) != {"checked", "passed"} or response["checked"] != subject:
        raise ValueError("Local technical fixture malformed")
    return DecisionEvidence(provider, cap.model, "technical_flag",
                            response["passed"], subject, image_sha256)


@dataclass(frozen=True)
class RepairLimits:
    allow_technical_auto_rejection: bool = False
    allow_local_mask_repair: bool = False
    maximum_local_repairs: int = 1
    maximum_total_stage_attempts: int = 2
    maximum_additional_paid_usd: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if (type(self.allow_technical_auto_rejection) is not bool
                or type(self.allow_local_mask_repair) is not bool):
            raise ValueError("Automatic policy opt-ins must be explicit Booleans")
        if (type(self.maximum_local_repairs) is not int or
                not 0 <= self.maximum_local_repairs <= 3
                or type(self.maximum_total_stage_attempts) is not int or
                not 1 <= self.maximum_total_stage_attempts <= 5):
            raise ValueError("Bounded local repair and stage caps required")
        if (not isinstance(self.maximum_additional_paid_usd, Decimal)
                or not self.maximum_additional_paid_usd.is_finite()
                or self.maximum_additional_paid_usd != Decimal("0")):
            raise ValueError("This offline repair engine cannot authorize paid inference")


@dataclass(frozen=True)
class CandidateState:
    cohort: Literal["product", "portrait"]
    technical_issue: str
    stage: Literal["segmentation", "cutout", "generation", "judge"]
    stage_attempts: int
    local_repairs_used: int
    accepted_output_exists: bool = False
    remote_charge_uncertain: bool = False
    awaiting_provider_submission: bool = False
    model_evidence: tuple[DecisionEvidence, ...] = ()

    def __post_init__(self) -> None:
        if self.technical_issue not in _TKNOWN:
            raise ValueError("Unknown technical issue; no automatic action")
        if (type(self.stage_attempts) is not int or self.stage_attempts < 0
                or type(self.local_repairs_used) is not int or self.local_repairs_used < 0
                or any(type(x) is not bool for x in (
                    self.accepted_output_exists, self.remote_charge_uncertain,
                    self.awaiting_provider_submission))):
            raise ValueError("Invalid stage/attempt state")
        if not isinstance(self.model_evidence, tuple) or any(
                not isinstance(item, DecisionEvidence) for item in self.model_evidence):
            raise ValueError("Malformed decision evidence")


@dataclass(frozen=True)
class DecisionPlan:
    action: Action
    reason_code: str
    requires_human: bool
    would_spend_usd: Decimal = Decimal("0")
    mutates_accepted_asset: bool = False
    source: str = "deterministic_offline_policy_v1"


def decide_candidate(state: CandidateState, limits: RepairLimits) -> DecisionPlan:
    """Fail-closed bounded local action plan for one *unaccepted* candidate.

    Produces an action PLAN; does not touch images or submit provider calls.
    The operational repair executor must journal a unique attempt and
    revalidate all preconditions before performing one local refinement.
    """
    def review(reason: str) -> DecisionPlan:
        return DecisionPlan("human_review", reason, True)
    if not isinstance(state, CandidateState) or not isinstance(limits, RepairLimits):
        raise TypeError("Invalid candidate/limits")
    if state.remote_charge_uncertain or state.awaiting_provider_submission:
        return review("billing_or_submission_uncertain")
    if state.accepted_output_exists:
        return review("preserve_accepted_output")
    if state.stage_attempts >= limits.maximum_total_stage_attempts:
        return review("maximum_stage_attempts_reached")
    # Model output alone may advise a person, but is uncalibrated and cannot
    # trigger irreversible rejection or repeated paid generation.
    if any(e.status == "abstained" for e in state.model_evidence):
        return review("model_abstained")
    if state.technical_issue == "subject_instance_ambiguous":
        return review("multiple_subjects_require_selection")
    if state.technical_issue == "mask_empty":
        return review("empty_mask_needs_new_segmentation_or_human")
    if state.technical_issue in _REPAIRABLE:
        if state.stage not in ("segmentation", "cutout"):
            return review("wrong_stage_for_local_repair")
        if (limits.allow_local_mask_repair and
                state.local_repairs_used < limits.maximum_local_repairs):
            return DecisionPlan("repair_local_mask", "bounded_nonpaid_alpha_refinement", False)
        if limits.allow_technical_auto_rejection:
            return DecisionPlan("reject_candidate", "technical_repair_exhausted", False)
        return review("local_repair_not_authorized_or_exhausted")
    if state.technical_issue in _HARD_REJECT:
        if limits.allow_technical_auto_rejection:
            return DecisionPlan("reject_candidate", "deterministic_invalid_candidate", False)
        return review("automatic_rejection_not_authorized")
    # No evidence for accepting a candidate based on model probability.
    if state.technical_issue == "none" and state.model_evidence:
        return review("uncalibrated_visual_decision")
    return review("no_verified_acceptance_evidence")
