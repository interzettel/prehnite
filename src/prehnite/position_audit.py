"""Controlled A/B vs B/A audit for judge positional preference.

This module never performs inference. Callers inject a review callback, which
must use exactly the supplied order, unchanged prompt, and fixed rubric.
The two invocations may still be stochastic, so a single pair is NOT a
calibrated model-bias estimate or a statistical significance test.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .artifacts import atomic_text
from .judges import Verdict, check_verdict

PROTOCOL = "prehnite.position-audit.v1"
LABELS = ("A", "B")
Reviewer = Callable[[dict[str, Path], str | None, str], Verdict | dict]


@dataclass(frozen=True)
class Comparison:
    """Same rubric and prompt applied to the same two distinct images."""

    pair_id: str
    first_id: str
    first_image: Path
    second_id: str
    second_image: Path
    prompt: str | None
    rubric: str


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_verdict(value: Verdict | dict) -> Verdict:
    if isinstance(value, Verdict):
        raw = {"winner": value.winner, "scores": value.scores,
               "reason": value.reason}
    else:
        raw = value
    return check_verdict(raw, LABELS)


def audit_pair(pair: Comparison, judge: Reviewer) -> dict:
    """Run fixed A/B then B/A; remap positions back to stable candidate IDs.

    No caching or reuse of previous judge results: both orders are separately
    evaluated. A changing file is rejected, not silently compared.
    """
    if (not pair.pair_id.strip() or not pair.first_id.strip() or
            not pair.second_id.strip() or pair.first_id == pair.second_id):
        raise ValueError("Audit requires a pair ID and distinct stable candidate IDs")
    if not pair.rubric.strip():
        raise ValueError("Audit requires one nonempty fixed rubric")
    if pair.prompt is not None and not isinstance(pair.prompt, str):
        raise ValueError("Audit prompt must be text or None")
    candidates = {pair.first_id: Path(pair.first_image),
                  pair.second_id: Path(pair.second_image)}
    if candidates[pair.first_id].resolve() == candidates[pair.second_id].resolve():
        raise ValueError("Two independent candidate image paths are required")
    hashes = {key: _digest(path) for key, path in candidates.items()}
    if hashes[pair.first_id] == hashes[pair.second_id]:
        raise ValueError("Candidate images have identical bytes; positional audit is ambiguous")
    ids = (pair.first_id, pair.second_id)
    runs = []
    for position_ids in (ids, ids[::-1]):
        placement = dict(zip(LABELS, position_ids))
        ordered = {label: candidates[candidate_id] for label, candidate_id in
                   placement.items()}
        # Do not allow image edits between passes or while callback executes.
        if any(_digest(candidates[key]) != hashes[key] for key in ids):
            raise ValueError("Candidate image changed during the A/B audit")
        verdict = _safe_verdict(judge(ordered, pair.prompt, pair.rubric))
        if any(_digest(candidates[key]) != hashes[key] for key in ids):
            raise ValueError("Judge modified the audited source image")
        remapped = {placement[label]: round(verdict.scores[label], 6)
                    for label in LABELS}
        mapped_winner = (placement[verdict.winner]
                         if verdict.winner in LABELS else verdict.winner)
        runs.append({
            "order": [placement[label] for label in LABELS],
            "winner": mapped_winner,
            "display_winner": verdict.winner,
            "scores_by_id": {key: remapped[key] for key in ids},
            "reason": verdict.reason,
            "abstained": verdict.winner in ("tie", "neither"),
        })
    first, swapped = runs
    shifts = {key: round(first["scores_by_id"][key] -
                         swapped["scores_by_id"][key], 6) for key in ids}
    # Relative influence of the first display slot on scores, independent
    # of candidate identity. The second pass gives the other image slot A.
    positional_lifts = [
        first["scores_by_id"][ids[0]] - swapped["scores_by_id"][ids[0]],
        swapped["scores_by_id"][ids[1]] - first["scores_by_id"][ids[1]],
    ]
    lift = round(sum(positional_lifts) / 2, 6)
    position_wins = sum(run["display_winner"] == "A" for run in runs)
    decisive = sum(run["display_winner"] in LABELS for run in runs)
    return {
        "pair_id": pair.pair_id,
        "candidate_ids": list(ids),
        "sha256_by_id": hashes,
        "rubric": pair.rubric,
        "prompt": pair.prompt,
        "first_order": first,
        "swapped_order": swapped,
        "winner_invariant": first["winner"] == swapped["winner"],
        "winner_flip": (first["winner"] in ids and swapped["winner"] in ids
                        and first["winner"] != swapped["winner"]),
        "abstentions": sum(run["abstained"] for run in runs),
        "first_position_wins": position_wins,
        "decisive_runs": decisive,
        "first_position_score_lift": lift,
        "absolute_score_shift_by_id": {
            key: round(abs(shifts[key]), 6) for key in ids},
        "max_absolute_score_shift": max(abs(v) for v in shifts.values()),
    }


def audit_pairs(pairs: Sequence[Comparison], judge: Reviewer) -> dict:
    """Inspectable finite-pair report. No p-value or accuracy claim."""
    if not pairs:
        raise ValueError("Audit needs at least one comparison pair")
    ids = [pair.pair_id for pair in pairs]
    if len(ids) != len(set(ids)):
        raise ValueError("Pair IDs must be unique")
    outcomes = [audit_pair(pair, judge) for pair in pairs]
    decisions = 2 * len(outcomes)
    decisive = sum(x["decisive_runs"] for x in outcomes)
    first_wins = sum(x["first_position_wins"] for x in outcomes)
    return {
        "protocol_version": PROTOCOL,
        "quality_calibrated": False,
        "sampling_note": (
            "Two ordered trials per pair; observations may be correlated. "
            "Cannot infer significance, reliability, human agreement or "
            "quality from this audit alone."
        ),
        "pair_count": len(outcomes),
        "decision_count": decisions,
        "pairs": outcomes,
        "summary": {
            "winner_invariant_pairs": sum(x["winner_invariant"] for x in outcomes),
            "winner_flip_pairs": sum(x["winner_flip"] for x in outcomes),
            "abstaining_decisions": sum(x["abstentions"] for x in outcomes),
            "decisive_decisions": decisive,
            "first_position_wins": first_wins,
            "first_position_win_fraction_of_decisive": (
                round(first_wins / decisive, 6) if decisive else None),
            "mean_first_position_score_lift": round(
                sum(x["first_position_score_lift"] for x in outcomes) /
                len(outcomes), 6),
            "largest_candidate_score_shift": max(
                x["max_absolute_score_shift"] for x in outcomes),
        },
    }


def write_report(path: Path, report: dict) -> None:
    """Deterministic JSON output, atomic local write, no provider calls."""
    import json
    if report.get("protocol_version") != PROTOCOL:
        raise ValueError("Unexpected positional-audit schema version")
    atomic_text(path, json.dumps(report, indent=2, ensure_ascii=False,
                                 sort_keys=True, allow_nan=False) + "\n")
