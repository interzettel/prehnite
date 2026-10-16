"""Reproducible offline evaluation of typed binary visual-judge probabilities.

Only supplied, labeled observations. No model inference, HTTP, image loading
or human review is performed by this module. Numbers are descriptive,
not certification that an experimental provider is calibrated.
"""
from __future__ import annotations

import json
import math
import re
from decimal import Decimal
from pathlib import Path

from .artifacts import atomic_text
from .typed_visual import PRICE_USD_PER_MILLION_INPUT_TOKENS

SCHEMA_VERSION = 1
_COHORT = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_ALLOWED_INPUT_KEYS = frozenset({
    "yes_probability", "gold_yes", "cohort", "reserved_input_tokens",
})


def _numeric(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Binary probability must be finite in [0,1]")
    return float(value)


def _wilson(successes: int, total: int) -> list[float] | None:
    if total <= 0:
        return None
    z = 1.959963984540054
    q = successes / total
    denom = 1 + z*z/total
    center = (q + z*z/(2*total)) / denom
    margin = z*math.sqrt(q*(1-q)/total + z*z/(4*total*total))/denom
    return [round(max(0, center-margin), 6), round(min(1, center+margin), 6)]


def evaluate_binary_visual_gold(
        observations: list[dict], *,
        declared_source: str, lower: float = 0.2, upper: float = 0.8,
        price_usd_per_million: Decimal = PRICE_USD_PER_MILLION_INPUT_TOKENS,
) -> dict:
    """Evaluate Noul yes probabilities vs supplied binary labels.

    The caller declares label provenance; this function does not independently
    certify whether a human inspected an image. Never use fixture scores as
    production-quality or actual provider-billing evidence.
    """
    if declared_source not in ("synthetic_fixture", "caller_declared_human_gold"):
        raise ValueError("Explicit synthetic or caller-declared gold provenance required")
    try:
        lo, hi = _numeric(lower), _numeric(upper)
    except ValueError as exc:
        raise ValueError("Invalid calibration thresholds") from exc
    if not 0 <= lo < 0.5 < hi <= 1:
        raise ValueError("Require disjoint negative/abstain/positive thresholds")
    if not isinstance(observations, list) or not 1 <= len(observations) <= 100_000:
        raise ValueError("Provide 1–100000 labeled observations")
    if (not isinstance(price_usd_per_million, Decimal)
            or not price_usd_per_million.is_finite()
            or price_usd_per_million <= 0):
        raise ValueError("Positive Decimal quoted price required")
    cleaned = []
    all_tokens_known = True
    total_tokens = 0
    for raw in observations:
        if not isinstance(raw, dict) or set(raw) != _ALLOWED_INPUT_KEYS:
            raise ValueError("Invalid or privacy-unsafe gold observation shape")
        p = _numeric(raw["yes_probability"])
        label = raw["gold_yes"]
        cohort = raw["cohort"]
        tokens = raw["reserved_input_tokens"]
        if type(label) is not bool:
            raise ValueError("Gold label must be an exact Boolean")
        if not isinstance(cohort, str) or not _COHORT.fullmatch(cohort):
            raise ValueError("Cohort is not an allowlisted aggregate label")
        if tokens is None:
            all_tokens_known = False
        elif type(tokens) is not int or not 0 <= tokens <= 262_000:
            raise ValueError("Invalid per-image reserved-token ceiling")
        else:
            total_tokens += tokens
        action = "accept" if p >= hi else ("reject" if p <= lo else "abstain")
        cleaned.append((p, label, cohort, action))

    n = len(cleaned)
    brier = sum((p-int(y))**2 for p,y,_,_ in cleaned)/n
    # Reliability bins contain model confidence for its top binary prediction.
    # Report observed categorical correctness, not correctness for an image grade.
    bins = [{"count":0,"confidence_sum":0.0,"correct":0} for _ in range(10)]
    for p,y,_,_ in cleaned:
        top=max(p,1-p)
        ix=min(9,int(top*10))
        item=bins[ix]
        item["count"]+=1
        item["confidence_sum"]+=top
        item["correct"]+=int((p>=0.5)==y)
    reliability = []
    ece = 0.0
    for i,item in enumerate(bins):
        count=item["count"]
        if count:
            mean=item["confidence_sum"]/count
            accuracy=item["correct"]/count
            ece+=(count/n)*abs(mean-accuracy)
        else:
            mean=accuracy=None
        reliability.append({
            "bin":i,"count":count,
            "mean_confidence":round(mean,8) if mean is not None else None,
            "observed_accuracy":round(accuracy,8) if accuracy is not None else None,
        })
    accepted=sum(action=="accept" for *_,action in cleaned)
    rejected=sum(action=="reject" for *_,action in cleaned)
    abstained=n-accepted-rejected
    false_accepted=sum(action=="accept" and not y for _,y,_,action in cleaned)
    false_rejected=sum(action=="reject" and y for _,y,_,action in cleaned)
    correct_actions=sum((action=="accept" and y) or (action=="reject" and not y)
                        for _,y,_,action in cleaned)
    reserved_usd = (Decimal(total_tokens)*price_usd_per_million/Decimal(1_000_000)
                    if all_tokens_known else None)
    cost_per_correct = (reserved_usd/Decimal(correct_actions)
                        if reserved_usd is not None and correct_actions else None)
    groups = {}
    for _,y,cohort,action in cleaned:
        group=groups.setdefault(cohort,{"count":0,"accepted":0,"rejected":0,
                                       "abstained":0,"false_accepts":0,"false_rejects":0})
        group["count"]+=1
        group["accepted"]+=int(action=="accept")
        group["rejected"]+=int(action=="reject")
        group["abstained"]+=int(action=="abstain")
        group["false_accepts"]+=int(action=="accept" and not y)
        group["false_rejects"]+=int(action=="reject" and y)

    return {
        "schema_version":SCHEMA_VERSION,
        "purpose":"descriptive_binary_noul_gold_evaluation_not_quality_certification",
        "label_provenance":declared_source,
        "label_provenance_verified_independently":False,
        "human_aesthetic_quality_certified":False,
        "inference_executed_by_evaluator":False,
        "actual_provider_invoice_usd":None,
        "quoted_price_usd_per_million_input_tokens":str(price_usd_per_million),
        "thresholds":{"reject_at_or_below":lo,"accept_at_or_above":hi},
        "examples":n,
        "accepted":accepted,"rejected":rejected,"abstained":abstained,
        "coverage":round((accepted+rejected)/n,8),
        "false_accepts":false_accepted,"false_rejects":false_rejected,
        "false_accept_rate_of_accepted":(
            round(false_accepted/accepted,8) if accepted else None),
        "false_reject_rate_of_rejected":(
            round(false_rejected/rejected,8) if rejected else None),
        "false_accept_rate_wilson95_of_accepted":_wilson(false_accepted,accepted),
        "false_reject_rate_wilson95_of_rejected":_wilson(false_rejected,rejected),
        "correct_nonabstaining_decisions":correct_actions,
        "brier_score":round(brier,8),
        "expected_calibration_error_10bin":round(ece,8),
        "reliability_bins":reliability,
        "cohorts":dict(sorted(groups.items())),
        "small_sample_warning":(n<100 or any(g["count"]<20 for g in groups.values())),
        "all_token_reservations_known":all_tokens_known,
        "total_reserved_input_tokens":total_tokens if all_tokens_known else None,
        "quoted_reserved_usd_estimate":str(reserved_usd) if reserved_usd is not None else None,
        "quoted_reserved_usd_per_correct_decision_estimate":(
            str(cost_per_correct) if cost_per_correct is not None else None),
    }


def write_aggregate_gold_report(path: Path, report: dict) -> Path:
    """Opt-in aggregate-only JSON. Never serializes individual images/labels."""
    if report.get("schema_version") != SCHEMA_VERSION or "brier_score" not in report:
        raise ValueError("Invalid aggregate evaluation report")
    target=Path(path)
    if target.suffix.lower() != ".json":
        raise ValueError("Evaluation export must use a .json destination")
    atomic_text(target,json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
    return target
