"""Synthetic judges for fixed-rubric A/B then B/A positional-bias audit."""
from __future__ import annotations

import json

import pytest
from PIL import Image

from prehnite.judges import Verdict
from prehnite.position_audit import Comparison, audit_pair, audit_pairs, write_report


@pytest.fixture
def pair(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (64, 64), "red").save(a)
    Image.new("RGB", (64, 64), "blue").save(b)
    return Comparison("fixture-01", "red", a, "blue", b,
                      "A red object near a blue object",
                      "Grade realism, composition and visible artifacts on 0..1")


class Consistent:
    def __init__(self):
        self.calls = []

    def __call__(self, images, prompt, rubric):
        self.calls.append((tuple(images), prompt, rubric))
        # Stable content identity regardless of display label order.
        scores = {label: (0.9 if path.name == "a.png" else 0.35)
                  for label, path in images.items()}
        return {"winner": max(scores, key=scores.get), "scores": scores,
                "reason": "Consistent object preference"}


def test_fixed_rubric_prompt_and_remapped_stable_identity(pair):
    judge = Consistent()
    row = audit_pair(pair, judge)
    assert [call[0] for call in judge.calls] == [("A", "B"), ("A", "B")]
    assert all(call[1:] == (pair.prompt, pair.rubric) for call in judge.calls)
    assert row["first_order"]["order"] == ["red", "blue"]
    assert row["swapped_order"]["order"] == ["blue", "red"]
    assert row["first_order"]["winner"] == row["swapped_order"]["winner"] == "red"
    assert row["swapped_order"]["display_winner"] == "B"
    assert row["first_order"]["scores_by_id"] == row["swapped_order"]["scores_by_id"]
    assert row["winner_invariant"] and not row["winner_flip"]
    assert row["first_position_wins"] == 1
    assert row["decisive_runs"] == 2
    assert row["first_position_score_lift"] == 0
    assert row["max_absolute_score_shift"] == 0


def test_first_position_judge_exposes_flip_and_score_lift(pair):
    def always_first(images, prompt, rubric):
        return Verdict("A", {"A": 0.9, "B": 0.2}, "I favor the first")
    row = audit_pair(pair, always_first)
    assert row["first_order"]["winner"] == "red"
    assert row["swapped_order"]["winner"] == "blue"
    assert row["first_position_wins"] == 2
    assert row["winner_flip"] and not row["winner_invariant"]
    assert row["first_position_score_lift"] == pytest.approx(0.7)
    assert row["absolute_score_shift_by_id"] == {"red": 0.7, "blue": 0.7}


def test_tie_and_neither_are_not_falsely_counted_as_first_wins(pair):
    cases = [
        ("tie", {"A": 0.71, "B": 0.71}),
        ("neither", {"A": 0.18, "B": 0.1}),
    ]
    for decision, scores in cases:
        def abstainer(images, prompt, rubric):
            return {"winner": decision, "scores": scores,
                    "reason": "Both inadequate or tied"}
        row = audit_pair(pair, abstainer)
        assert row["winner_invariant"]
        assert not row["winner_flip"]
        assert row["first_position_wins"] == 0
        assert row["decisive_runs"] == 0
        assert row["abstentions"] == 2
        report = audit_pairs([pair], abstainer)
        assert report["summary"]["first_position_win_fraction_of_decisive"] is None


def test_mixed_stability_and_report_effect_sizes_are_reproducible(pair, tmp_path):
    second = Comparison("fixture-02", pair.first_id, pair.first_image,
                        pair.second_id, pair.second_image, pair.prompt, pair.rubric)
    class Mixed:
        count = 0
        def __call__(self, images, prompt, rubric):
            self.count += 1
            if self.count <= 2:
                scores = {label: (0.9 if path.name == "a.png" else 0.35)
                          for label, path in images.items()}
                return {"winner": max(scores, key=scores.get), "scores": scores,
                        "reason": "Stable"}
            return {"winner": "A", "scores": {"A": 0.9, "B": 0.2},
                    "reason": "First-position preference"}
    first = audit_pairs([pair, second], Mixed())
    second_run = audit_pairs([pair, second], Mixed())
    assert first == second_run
    assert first["protocol_version"] == "prehnite.position-audit.v1"
    assert first["quality_calibrated"] is False
    assert first["summary"]["winner_invariant_pairs"] == 1
    assert first["summary"]["winner_flip_pairs"] == 1
    assert first["summary"]["decisive_decisions"] == 4
    assert first["summary"]["first_position_wins"] == 3
    assert first["summary"]["first_position_win_fraction_of_decisive"] == 0.75
    assert first["summary"]["mean_first_position_score_lift"] == 0.35
    path = tmp_path / "audit.json"
    write_report(path, first)
    initial = path.read_bytes()
    write_report(path, second_run)
    assert initial == path.read_bytes()
    assert json.loads(initial) == first
    assert "full_path" not in first["pairs"][0]


@pytest.mark.parametrize("bad", [
    {"winner": "A", "scores": {"A": 0.9}, "reason": "Partial"},
    {"winner": "A", "scores": {"A": float("nan"), "B": 0.1}, "reason": "NaN"},
    {"winner": "C", "scores": {"A": 0.9, "B": 0.1}, "reason": "Unknown"},
    {"winner": "tie", "scores": {"A": 0.9, "B": 0.1}, "reason": "Conflict"},
    {"winner": "A", "scores": {"A": 0.2, "B": 0.9}, "reason": "Conflict"},
])
def test_invalid_judge_response_is_rejected(pair, bad):
    def erroneous(images, prompt, rubric):
        return bad
    with pytest.raises(ValueError):
        audit_pair(pair, erroneous)


def test_candidate_edits_between_passes_are_detected(pair):
    count = 0
    def mutating(images, prompt, rubric):
        nonlocal count
        count += 1
        if count == 1:
            Image.new("RGB", (64, 64), "green").save(pair.first_image)
        return {"winner": "A", "scores": {"A": 0.7, "B": 0.2},
                "reason": "Altered input"}
    with pytest.raises(ValueError, match="modified"):
        audit_pair(pair, mutating)


def test_duplicate_candidate_bytes_cannot_be_claimed_independent(pair):
    pair.second_image.write_bytes(pair.first_image.read_bytes())
    with pytest.raises(ValueError, match="identical bytes"):
        audit_pair(pair, Consistent())


def test_duplicated_pair_ids_and_empty_study_rejected(pair):
    with pytest.raises(ValueError, match="unique"):
        audit_pairs([pair, pair], Consistent())
    with pytest.raises(ValueError, match="at least one"):
        audit_pairs([], Consistent())


def test_absent_rubric_or_identical_ids_fails_before_judging(pair):
    same_ids = Comparison(pair.pair_id, "x", pair.first_image, "x",
                          pair.second_image, pair.prompt, pair.rubric)
    with pytest.raises(ValueError, match="distinct"):
        audit_pair(same_ids, lambda *_: pytest.fail("Judge called"))
    missing_rubric = Comparison(pair.pair_id, pair.first_id, pair.first_image,
                               pair.second_id, pair.second_image, pair.prompt, " ")
    with pytest.raises(ValueError, match="rubric"):
        audit_pair(missing_rubric, lambda *_: pytest.fail("Judge called"))


def test_reject_unversioned_or_invalid_report(tmp_path):
    with pytest.raises(ValueError, match="schema version"):
        write_report(tmp_path/"invalid.json", {"protocol_version": "unknown"})
    assert not (tmp_path/"invalid.json").exists()
