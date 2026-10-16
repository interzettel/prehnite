"""Opt-in cache: deterministic keying, scope isolation and fail-closed reuse."""
from __future__ import annotations

import hashlib
import zipfile

import pytest
from PIL import Image

from prehnite.cache import CacheIntegrityError, StageCache
from prehnite.engine import Engine
from prehnite.providers import Result
from prehnite.schema import CachePolicy, Endpoint, Manifest, Profile


def policy(**extras):
    return CachePolicy.model_validate({
        "enabled": True, "namespace": "personal-project",
        **extras,
    })


def job(batch_id, *, prompt="same prompt", namespace="personal-project",
        cache_enabled=True, revisions=None, allow_paid_cache=False):
    manifest = Manifest.model_validate({
        "id": batch_id,
        "assets": [{"id": "one", "prompt": prompt,
                    "aspect_ratio": "3:4", "target_size": [192, 256],
                    "seed": 18, "output": {"image": "one.png"}}],
    })
    settings = {
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
        "cache": {"enabled": cache_enabled, "namespace": namespace,
                  "allow_paid": allow_paid_cache,
                  "model_revisions": revisions or {}},
    }
    return manifest, Profile.model_validate(settings)


def direct_stage(engine, endpoint, output, invoker, request=None, price_key=""):
    return engine.stage(
        "one:a1:native_4k:generate", "generation", endpoint, output,
        invoker, price_key, cache_request=request or {
            "prompt": "same prompt", "seed": 18,
            "aspect_ratio": "3:4", "tier": "4k",
        })


def simple_provider(on_submit, resume_id, temp):
    assert resume_id is None
    Image.new("RGB", (192, 256), "forestgreen").save(temp)
    return Result(temp, metadata={"synthetic": True})


def test_cache_hit_reuses_same_scope_without_new_inference_or_reserve(tmp_path):
    ep = Endpoint(provider="demo", model="synthetic")
    m1, p = job("cache-batch-1")
    first = Engine(m1, p, tmp_path)
    try:
        dest = first.journal.root/"manual.png"
        direct_stage(first, ep, dest, simple_provider)
        assert len(first.journal.attempts()) == 1
        first_digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    finally:
        first.journal.close()

    m2, p2 = job("cache-batch-2")
    second = Engine(m2, p2, tmp_path)
    try:
        dest = second.journal.root/"manual.png"
        direct_stage(second, ep, dest, lambda *args: pytest.fail("Cache miss"))
        assert hashlib.sha256(dest.read_bytes()).hexdigest() == first_digest
        task = second.journal.get("one:a1:native_4k:generate")
        assert task["data"]["cache_hit"] is True
        assert task["reserved_usd"] == 0
        assert second.journal.attempts() == []
    finally:
        second.journal.close()


def test_distinct_privacy_namespace_cannot_reuse_other_images(tmp_path):
    ep = Endpoint(provider="demo", model="synthetic")
    first = Engine(*job("one-batch", namespace="owner-one"), tmp_path)
    try:
        direct_stage(first, ep, first.journal.root/"test.png", simple_provider)
    finally:
        first.journal.close()
    second = Engine(*job("two-batch", namespace="owner-two"), tmp_path)
    try:
        seen = []
        def invoke(*args):
            seen.append(1)
            return simple_provider(*args)
        direct_stage(second, ep, second.journal.root/"test.png", invoke)
        assert seen == [1]
        assert second.journal.get("one:a1:native_4k:generate")["data"].get("cache_hit") is None
    finally:
        second.journal.close()


@pytest.mark.parametrize("variation", ["prompt", "seed", "options", "model", "revision"])
def test_changed_content_or_model_cannot_hit_old_cache(tmp_path, variation):
    ep = Endpoint(provider="demo", model="synthetic")
    first = Engine(*job("original"), tmp_path)
    request = {"prompt": "prompt-A", "seed": 1, "tier": "4k", "aspect_ratio": "3:4"}
    try:
        direct_stage(first, ep, first.journal.root/"test.png", simple_provider, request)
    finally:
        first.journal.close()
    endpoint = ep
    new_request = dict(request)
    revisions = {}
    if variation == "prompt":
        new_request["prompt"] = "prompt-B"
    elif variation == "seed":
        new_request["seed"] = 2
    elif variation == "options":
        endpoint = Endpoint(provider="demo", model="synthetic", options={"shift": 1})
    elif variation == "model":
        endpoint = Endpoint(provider="demo", model="different")
    else:
        revisions = {"generation": "new-pinned-model-2026"}
    second = Engine(*job("changed", revisions=revisions), tmp_path)
    seen = []
    try:
        def invoke(*args):
            seen.append(1)
            return simple_provider(*args)
        direct_stage(second, endpoint, second.journal.root/"test.png", invoke, new_request)
        assert seen == [1]
    finally:
        second.journal.close()


def test_corrupted_cache_never_falls_back_to_silent_paid_or_local_retry(tmp_path):
    ep = Endpoint(provider="demo", model="synthetic")
    first = Engine(*job("cache-good"), tmp_path)
    request = {"prompt": "same prompt", "seed": 18,
               "aspect_ratio": "3:4", "tier": "4k"}
    try:
        direct_stage(first, ep, first.journal.root/"test.png", simple_provider, request)
        key = first.cache.key("generation", ep, request)
        cached = first.cache._path(key)
    finally:
        first.journal.close()
    cached.write_bytes(b"tampered zip")
    second = Engine(*job("cache-corrupt"), tmp_path)
    try:
        with pytest.raises(CacheIntegrityError):
            direct_stage(second, ep, second.journal.root/"test.png",
                         lambda *args: pytest.fail("No fallback to provider"), request)
        assert second.journal.attempts() == []
        assert second.journal.get("one:a1:native_4k:generate") is None
    finally:
        second.journal.close()


def test_cached_zip_receipt_does_not_contain_prompt_or_namespace(tmp_path):
    ep = Endpoint(provider="demo", model="synthetic")
    cache = StageCache(tmp_path, policy())
    request = {"prompt": "PRIVATE CLIENT PROMPT SHOULD NOT APPEAR", "seed": 42}
    key = cache.key("generation", ep, request)
    image = tmp_path/"image.png"
    Image.new("RGB", (192, 256), "red").save(image)
    assert cache.store(key, image) is True
    archive = cache._path(key)
    content = archive.read_bytes()
    assert b"PRIVATE CLIENT PROMPT" not in content
    assert b"personal-project" not in content
    assert cache.store(key, image) is False
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == {"receipt.json", "artifact.png"}


@pytest.mark.parametrize("bad", [
    {"enabled": True}, {"enabled": True, "namespace": "../escape"},
    {"enabled": True, "namespace": "work", "model_revisions": {"generation": "../bad"}},
    {"enabled": False, "namespace": "work", "allow_paid": True},
])
def test_invalid_cache_policy_rejected_before_use(bad):
    with pytest.raises(ValueError):
        CachePolicy.model_validate(bad)


def test_paid_cache_requires_separate_optin_and_pinned_revision(tmp_path):
    paid = Endpoint(provider="fal", model="blackforestlabs/flux-3/klein/text-to-image")
    c = StageCache(tmp_path, policy())
    assert c.key("generation", paid, {"prompt": "asset"}) is None
    c = StageCache(tmp_path, policy(allow_paid=True))
    assert c.key("generation", paid, {"prompt": "asset"}) is None
    c = StageCache(tmp_path, policy(allow_paid=True, model_revisions={
        "generation": "model-contract-pinned-v1",
    }))
    assert c.key("generation", paid, {"prompt": "asset"}) is not None


def test_ambiguous_previous_paid_task_is_never_replaced_with_cache(tmp_path):
    paid = Endpoint(provider="fal", model="blackforestlabs/flux-3/klein/text-to-image")
    m, p = job("ambiguous", revisions={"generation": "revision-v1"},
               allow_paid_cache=True)
    p = p.model_copy(update={"costs": p.costs.model_copy(update={
        "allow_paid": True, "allow_cloud_uploads": True, "max_usd": 0.10,
        "estimates_usd": {"generation:2k": 0.025, "generation:4k": 0.025},
    })})
    engine = Engine(m, p, tmp_path)
    try:
        request = {"prompt": "same prompt", "seed": 18, "tier": "4k", "aspect_ratio": "3:4"}
        key = engine.cache.key("generation", paid, request)
        img = tmp_path/"valid.png"
        Image.new("RGB", (192, 256), "green").save(img)
        engine.cache.store(key, img)
        engine.journal.put("one:a1:native_4k:generate", "generation", "submitting",
                           provider="fal", model=paid.model, reserved_usd=0.025)
        with pytest.raises(RuntimeError, match="no recoverable provider ID"):
            direct_stage(engine, paid, engine.journal.root/"test.png",
                         lambda *args: pytest.fail("Unsafe paid replay"),
                         request, "generation:4k")
        assert engine.journal.reserved() == pytest.approx(0.025)
    finally:
        engine.journal.close()


def test_cached_paid_operation_requires_explicit_consent_but_new_reserve_is_zero(tmp_path):
    paid = Endpoint(provider="fal", model="blackforestlabs/flux-3/klein/text-to-image")
    m, p = job("paid-new", revisions={"generation": "pinned-v1"}, allow_paid_cache=True)
    p = p.model_copy(update={"costs": p.costs.model_copy(update={
        "allow_paid": True, "allow_cloud_uploads": True, "max_usd": 0.10,
        "estimates_usd": {"generation:2k": 0.04, "generation:4k": 0.04},
    })})
    request = {"prompt": "same prompt", "seed": 18, "tier": "4k", "aspect_ratio": "3:4"}
    first = Engine(m, p, tmp_path)
    try:
        def mock_paid(on_submit, resume_id, temp):
            assert resume_id is None
            on_submit("fake-billable-request")
            Image.new("RGB", (192, 256), "green").save(temp)
            return Result(temp, "fake-billable-request")
        direct_stage(first, paid, first.journal.root/"test.png", mock_paid,
                     request, "generation:4k")
        assert first.journal.reserved() == pytest.approx(0.04)
    finally:
        first.journal.close()
    m2, p2 = job("paid-cached", revisions={"generation": "pinned-v1"}, allow_paid_cache=True)
    p2 = p2.model_copy(update={"costs": p.costs})
    second = Engine(m2, p2, tmp_path)
    try:
        direct_stage(second, paid, second.journal.root/"test.png",
                     lambda *args: pytest.fail("New paid request on cache hit"),
                     request, "generation:4k")
        assert second.journal.reserved() == 0
        assert second.journal.attempts() == []
        assert second.journal.get("one:a1:native_4k:generate")["data"]["cache_hit"]
    finally:
        second.journal.close()
