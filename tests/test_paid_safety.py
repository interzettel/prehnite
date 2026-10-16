"""Offline safety regressions: never contact a real inference provider."""
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from prehnite.engine import BudgetExceeded, Engine
from prehnite.manifest import validate_job
from prehnite.providers import Result
from prehnite.schema import Endpoint, Manifest, Profile


def manifest():
    return Manifest.model_validate({
        "id": "safe-batch",
        "assets": [
            {"id": "one", "prompt": "Fixture", "aspect_ratio": "3:4",
             "target_size": [192, 256], "output": {"image": "one.png"}}
        ],
    })


def profile(*, budget=0.2, price=0.04, judge="demo"):
    return Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": judge, "model": "mock" if judge == "anthropic" else "technical"},
        "policy": {"uncertain": "accept_unverified"},
        "costs": {
            "allow_paid": True, "allow_cloud_uploads": True,
            "max_usd": budget, "estimates_usd": {
                "generation:2k": price, "judge": 0.02
            },
        },
    })


def fake_stage(output, request_id, seen):
    def run(on_submit, resume_id):
        seen.append(resume_id)
        if not resume_id:
            on_submit(request_id)
        Image.new("RGB", (192, 256), "blue").save(output)
        return Result(output, request_id, {"fixture": True})
    return run


def test_crash_after_paid_dispatch_but_before_provider_id_blocks_retry(tmp_path):
    engine = Engine(manifest(), profile(), tmp_path)
    output = tmp_path / "image.png"
    ep = Endpoint(provider="fal", model="test")
    engine.journal.put(
        "one:generate", "generation", "submitting",
        provider="fal", model="test", reserved_usd=0.04,
    )
    calls = []
    with pytest.raises(RuntimeError, match="no recoverable provider ID"):
        engine.stage("one:generate", "generation", ep, output,
                     fake_stage(output, "new-request", calls), "generation:2k")
    assert calls == []
    assert engine.journal.reserved() == 0.04
    engine.journal.close()


def test_completed_paid_task_without_saved_request_id_never_regenerates(tmp_path):
    engine = Engine(manifest(), profile(), tmp_path)
    output = tmp_path / "deleted.png"
    engine.journal.put("lost", "generation", "completed", provider="fal",
                       model="test", path=str(output), reserved_usd=0.04)
    calls = []
    with pytest.raises(RuntimeError, match="no recoverable provider ID"):
        engine.stage("lost", "generation", Endpoint(provider="fal", model="test"),
                     output, fake_stage(output, "unexpected", calls), "generation:2k")
    assert not calls
    engine.journal.close()


def test_submitted_remote_request_resumes_existing_id_without_new_budget(tmp_path):
    engine = Engine(manifest(), profile(), tmp_path)
    output = tmp_path / "result.png"
    engine.journal.put("recover", "generation", "submitted", request_id="req-123",
                       provider="fal", model="test", reserved_usd=0.04)
    calls = []
    engine.stage("recover", "generation", Endpoint(provider="fal", model="test"),
                 output, fake_stage(output, "req-123", calls), "generation:2k")
    assert calls == ["req-123"]
    assert engine.journal.reserved() == 0.04
    assert engine.journal.get("recover")["status"] == "completed"
    engine.journal.close()


def test_uncertain_paid_judge_is_not_sent_again(tmp_path):
    engine = Engine(manifest(), profile(judge="anthropic"), tmp_path)
    image_a, image_b = tmp_path/"a.png", tmp_path/"b.png"
    for img in (image_a, image_b):
        Image.new("RGB", (192, 256), "orange").save(img)
    engine.journal.put("one:a1:judge:blind", "judge", "submitting",
                       provider="anthropic", model="mock", reserved_usd=0.02)
    with pytest.raises(RuntimeError, match="uncertain status"):
        engine.adjudicate(manifest().assets[0], {
            "enhanced_2k": image_a, "native_4k": image_b,
        }, 1)
    assert engine.journal.reserved() == 0.02
    engine.journal.close()


def test_enforces_remaining_budget_before_second_paid_call(tmp_path):
    engine = Engine(manifest(), profile(budget=0.06), tmp_path)
    ep = Endpoint(provider="fal", model="test")
    first = tmp_path/"first.png"
    engine.stage("first", "generation", ep, first,
                 fake_stage(first, "req-first", []), "generation:2k")
    second = tmp_path/"second.png"
    calls = []
    with pytest.raises(BudgetExceeded):
        engine.stage("second", "generation", ep, second,
                     fake_stage(second, "req-second", calls), "generation:2k")
    assert not calls
    assert engine.journal.reserved() == 0.04
    engine.journal.close()


def test_a_second_worker_cannot_acquire_same_batch_lock(tmp_path):
    one = Engine(manifest(), profile(), tmp_path)
    two = Engine(manifest(), profile(), tmp_path)
    try:
        with one.journal.exclusive():
            with pytest.raises(RuntimeError, match="already has a running worker"):
                with two.journal.exclusive():
                    pytest.fail("Concurrent runner entered the critical section")
        with two.journal.exclusive():
            assert True  # Lock released by first worker.
    finally:
        one.journal.close()
        two.journal.close()


def test_preflight_rejects_unpriced_paid_models(tmp_path):
    p = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "fal", "model": "some-model"},
        "upscale": {"provider": "disabled"},
        "costs": {"allow_paid": True, "allow_cloud_uploads": False,
                  "max_usd": 2, "estimates_usd": {}},
    })
    with pytest.raises(ValueError, match="Missing price estimates"):
        validate_job(manifest(), p, tmp_path)


def test_preflight_rejects_zero_spend_cap_for_paid_calls(tmp_path):
    p = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "fal", "model": "some-model"},
        "upscale": {"provider": "disabled"},
        "costs": {"allow_paid": True, "max_usd": 0,
                  "estimates_usd": {"generation:4k": 0.03}},
    })
    with pytest.raises(ValueError, match="positive max_usd"):
        validate_job(manifest(), p, tmp_path)


@pytest.mark.parametrize("bad_value", [0, -1, float("nan"), float("inf")])
def test_nonpositive_or_nonfinite_call_estimates_rejected(bad_value):
    with pytest.raises(ValidationError):
        Profile.model_validate({"costs": {"estimates_usd": {"judge": bad_value}}})
