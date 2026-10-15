"""Typed, independent visual judgments. A score is NOT a calibrated probability."""
from __future__ import annotations

import base64
import io
import json
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


def check_verdict(raw: dict, choices: tuple[str, ...]) -> Verdict:
    scores = raw.get("scores", {})
    if raw.get("winner") not in (*choices, "tie", "neither"):
        raise ValueError("Judge returned invalid winner")
    if not isinstance(scores, dict) or set(scores) != set(choices):
        raise ValueError("Judge scores must cover every candidate")
    vals = {key: float(value) for key, value in scores.items()}
    if any(not (0 <= v <= 1) for v in vals.values()):
        raise ValueError("Judge scores must be between 0 and 1")
    return Verdict(str(raw["winner"]), vals, str(raw.get("reason", ""))[:600])


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
