"""Typed judge and order-perturbation tests: zero Anthropic network traffic."""
from __future__ import annotations

from pathlib import Path

import pytest

from prehnite.engine import Engine
from prehnite.judges import Verdict, check_verdict
from prehnite.schema import Manifest, Profile


def valid():
    return {"winner": "A", "scores": {"A": 0.90, "B": 0.30},
            "reason": "A has fewer structural defects"}


@pytest.mark.parametrize("payload,pattern", [
    (None, "JSON object"),
    ([], "JSON object"),
    ({"winner": "C", "scores": {"A": 0.9, "B": 0.3},
      "reason": "Bad label"}, "winner"),
    ({"winner": "A", "scores": {"A": 0.9},
      "reason": "Missing B"}, "every candidate"),
    ({"winner": "A", "scores": {"A": 0.9, "B": 0.3, "C": 0.5},
      "reason": "Extra label"}, "every candidate"),
    ({"winner": "A", "scores": {"A": "0.9", "B": 0.3},
      "reason": "String"}, "numeric"),
    ({"winner": "A", "scores": {"A": True, "B": 0.3},
      "reason": "Boolean"}, "numeric"),
    ({"winner": "A", "scores": {"A": float("nan"), "B": 0.3},
      "reason": "Nonfinite"}, "finite"),
    ({"winner": "A", "scores": {"A": float("inf"), "B": 0.3},
      "reason": "Infinite"}, "finite"),
    ({"winner": "A", "scores": {"A": -0.01, "B": 0.3},
      "reason": "Below zero"}, "between 0 and 1"),
    ({"winner": "A", "scores": {"A": 1.01, "B": 0.3},
      "reason": "Above one"}, "between 0 and 1"),
    ({"winner": "B", "scores": {"A": 0.90, "B": 0.10},
      "reason": "Contradiction"}, "contradicts"),
    ({"winner": "tie", "scores": {"A": 0.99, "B": 0.11},
      "reason": "Unequal"}, "tie contradicts"),
    ({"winner": "neither", "scores": {"A": 0.80, "B": 0.40},
      "reason": "A exceeds threshold"}, "neither contradicts"),
    ({"winner": "A", "scores": {"A": 0.90, "B": 0.30},
      "reason": "  "}, "explain"),
])
def test_bad_verdicts_are_never_accepted(payload, pattern):
    with pytest.raises(ValueError, match=pattern):
        check_verdict(payload, ("A", "B"))


@pytest.mark.parametrize("winner,scores", [
    ("A", {"A": 0.7, "B": 0.2}),
    ("B", {"A": 0.2, "B": 0.7}),
    ("tie", {"A": 0.74, "B": 0.75}),
    ("neither", {"A": 0.10, "B": 0.30}),
])
def test_complete_consistent_verdicts_are_typed(winner, scores):
    raw = {"winner": winner, "scores": scores, "reason": "Observed flaws"}
    result = check_verdict(raw, ("A", "B"))
    assert result.winner == winner
    assert result.scores == scores


def job():
    manifest = Manifest.model_validate({
        "id": "judge-bias",
        "assets": [{"id": "one", "prompt": "An indoor candid portrait",
                    "aspect_ratio": "3:4", "target_size": [192, 256],
                    "output": {"image": "one.png"}}],
    })
    profile = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "anthropic", "model": "fake-haiku"},
        "policy": {"uncertain": "accept_unverified", "minimum_score": 0.7},
        "costs": {"allow_paid": True, "allow_cloud_uploads": True,
                  "max_usd": 0.50, "estimates_usd": {"judge": 0.04}},
    })
    return manifest, profile


class PositionalMock:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    observed = []

    def review(self, images, prompt, kind):
        self.observed.append((kind, tuple(images)))
        winner = next(iter(images))
        return Verdict(winner, {key: (0.9 if key == winner else 0.2)
                                for key in images}, "Preferred first image")


class ConsistentMock(PositionalMock):
    def review(self, images, prompt, kind):
        self.observed.append((kind, tuple(images)))
        return Verdict("A", {"A": 0.92, "B": 0.30}, "A visibly matches the brief")


def test_order_swap_surfaces_mock_first_candidate_bias(monkeypatch, tmp_path):
    import prehnite.engine as engine_mod
    monkeypatch.setattr(engine_mod, "HaikuJudge", PositionalMock)
    PositionalMock.observed = []
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    try:
        selected, score, reason = engine.adjudicate(manifest.assets[0],
                                                    {"variant1": tmp_path / "a.png",
                                                     "variant2": tmp_path / "b.png"}, 1)
        assert selected is None and score is None
        assert "disagree" in reason
        assert PositionalMock.observed == [("blind", ("A", "B")),
                                           ("prompt", ("B", "A"))]
        assert engine.journal.reserved() == pytest.approx(0.08)
    finally:
        engine.journal.close()


def test_consistent_judge_survives_swapped_order_and_reuses_cache(monkeypatch, tmp_path):
    import prehnite.engine as engine_mod
    monkeypatch.setattr(engine_mod, "HaikuJudge", ConsistentMock)
    ConsistentMock.observed = []
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    candidates = {"native": tmp_path / "a.png", "upscaled": tmp_path / "b.png"}
    try:
        selected, score, _ = engine.adjudicate(manifest.assets[0], candidates, 1)
        assert selected == "native" and score == pytest.approx(0.92)
        assert engine.journal.get("one:a1:judge:blind")["data"]["candidate_order"] == ["A", "B"]
        assert engine.journal.get("one:a1:judge:prompt")["data"]["candidate_order"] == ["B", "A"]
        again = engine.adjudicate(manifest.assets[0], candidates, 1)
        assert again[0] == "native"
        assert len(ConsistentMock.observed) == 2  # No new paid calls.
    finally:
        engine.journal.close()


def test_corrupt_cached_verdict_is_rejected_without_model_call(monkeypatch, tmp_path):
    import prehnite.engine as engine_mod

    class Uncallable:
        def __init__(self, endpoint):
            pytest.fail("Paid judge called to repair invalid cached decision")

    monkeypatch.setattr(engine_mod, "HaikuJudge", Uncallable)
    manifest, profile = job()
    engine = Engine(manifest, profile, tmp_path)
    engine.journal.put(
        "one:a1:judge:blind", "judge", "completed",
        provider="anthropic", model="fake-haiku", reserved_usd=0.04,
        data={"winner": "A", "scores": {"A": 0.2, "B": 0.9},
              "reason": "Inconsistent cached result", "candidate_order": ["A", "B"]},
    )
    try:
        with pytest.raises(ValueError, match="winner contradicts"):
            engine.adjudicate(manifest.assets[0],
                              {"native": tmp_path / "a.png",
                               "upscaled": tmp_path / "b.png"}, 1)
        assert engine.journal.reserved() == pytest.approx(0.04)
    finally:
        engine.journal.close()
