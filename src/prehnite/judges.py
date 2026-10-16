"""Typed, independent visual judgments. A score is NOT a calibrated probability."""
from __future__ import annotations

import base64
import io
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from .schema import Endpoint


@dataclass
class Verdict:
    winner: str
    scores: dict[str, float]
    reason: str
    tokens_in: int = 0
    tokens_out: int = 0


def preview(path: Path, max_edge: int = 1300) -> str:
    with Image.open(path) as source:
        im = ImageOps.exif_transpose(source).convert("RGB")
        im.thumbnail((max_edge, max_edge))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=85)
    return base64.b64encode(b.getvalue()).decode("ascii")


def check_verdict(raw: object, choices: tuple[str, ...]) -> Verdict:
    """Strictly validate a rubric response, not merely its JSON syntax.

    These scores are uncalibrated rubric judgments, not probabilities.
    """
    if not isinstance(raw, dict):
        raise ValueError("Judge verdict must be a JSON object")
    if len(choices) != len(set(choices)) or not choices:
        raise ValueError("Candidate labels must be nonempty and unique")
    winner = raw.get("winner")
    if winner not in (*choices, "tie", "neither"):
        raise ValueError("Judge returned invalid winner")
    scores = raw.get("scores")
    if not isinstance(scores, dict) or set(scores) != set(choices):
        raise ValueError("Judge scores must cover every candidate exactly")
    normalized = {}
    for label in choices:
        value = scores[label]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Judge scores must be numeric JSON values")
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Judge scores must be finite and between 0 and 1")
        normalized[label] = value
    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Judge must explain its decision")
    # Separate outright winner from an abstention. A tie has nearly equal
    # rubric scores; "neither" means no candidate meets a minimal standard.
    top = max(normalized.values())
    if winner == "tie" and max(normalized.values()) - min(normalized.values()) > 0.02:
        raise ValueError("Judge tie contradicts candidate scores")
    if winner == "neither" and top >= 0.5:
        raise ValueError("Judge neither contradicts high candidate score")
    if winner in choices and normalized[winner] < top - 0.02:
        raise ValueError("Judge winner contradicts candidate scores")
    return Verdict(str(winner), normalized, reason.strip()[:600])


class HaikuJudge:
    def __init__(self, endpoint: Endpoint):
        self.endpoint = endpoint

    def review(self, images: dict[str, Path], prompt: str | None,
               kind: str) -> Verdict:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is required for the optional judge")
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError("Install prehnite[anthropic]") from exc
        keys = tuple(images)
        content = []
        instructions = (
            "Evaluate visible photographic quality, realism, defects and artifacts."
            if kind == "blind" else
            "Evaluate fidelity to the exact prompt, visible technical quality, and defects."
            if kind == "prompt" else
            "Evaluate the subject completeness, visible edges, transparency halos and "
            "background contamination of the cutout preview relative to the source."
        )
        content.append({"type": "text", "text": instructions + "\n"
                        "Return ONLY JSON with keys winner (one of candidate labels/tie/neither), "
                        f"scores (mapping {list(keys)} to values 0..1), reason (brief). "
                        "Scores measure rubric satisfaction, not certainty. "
                        "A named winner must have the top score; a tie requires "
                        "scores within 0.02 and neither requires all scores below "
                        "0.5. Return a meaningful brief reason. "
                        + (f"Exact prompt: {prompt}" if prompt else "")})
        for key, path in images.items():
            content.append({"type": "text", "text": f"Candidate {key}"})
            content.append({"type": "image", "source": {"type": "base64",
                           "media_type": "image/jpeg", "data": preview(path)}})
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=self.endpoint.model or "claude-haiku-5-5",
            max_tokens=320,
            temperature=0,
            messages=[{"role": "user", "content": content}],
        )
        output = "".join(c.text for c in message.content if getattr(c, "type", "") == "text")
        try:
            raw = json.loads(output)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", output, flags=re.S)
            if not match:
                raise ValueError("Judge failed to return JSON")
            raw = json.loads(match.group())
        verdict = check_verdict(raw, keys)
        verdict.tokens_in = int(message.usage.input_tokens)
        verdict.tokens_out = int(message.usage.output_tokens)
        return verdict


def technical(source: Path, expected: tuple[int, int]) -> Verdict:
    with Image.open(source) as im:
        correct = im.size == expected and im.width > 0 and im.height > 0
    return Verdict("A" if correct else "neither", {"A": 1.0 if correct else 0.0},
                   "Dimensions and decodability only; aesthetic quality NOT assessed")
