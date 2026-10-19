"""CPU-only integrity checks for the P08-A04 compatibility profile."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "docs" / "compatibility-profile.v1.json"
HEX256 = re.compile(r"^[0-9a-f]{64}$")


def load_profile():
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def observations_by_class(profile, evidence_class):
    return [item for item in profile["observations"] if item["evidence_class"] == evidence_class]


def test_profile_is_versioned_and_has_expected_schema():
    profile = load_profile()
    assert profile["schema_version"] == 1
    assert profile["profile_version"] == "1.0.0"
    assert profile["profile_id"] == "p08-a04-local-compatibility"
    assert profile["task"] == "P08-A04"
    assert profile["acceptance"] == (
        "Decision table states actually measured versus unknown VRAM configurations"
    )
    assert profile["observations"]


def test_only_observed_success_carries_successful_measurements():
    profile = load_profile()
    successes = observations_by_class(profile, "observed_success")
    assert len(successes) == 1
    success = successes[0]
    assert success["measured"]["prompt_count"] == 1
    assert success["measured"]["sampled_peak_vram_used_mib"] == 2533
    assert success["measured"]["job_start_to_success_seconds"] == 8.994
    assert success["measured"]["minimum_available_ram_mb"] == 3338
    assert success["measured"]["ram_unit"] == "MB as recorded by the historical supervisor"
    assert success["not_a_minimum_vram_requirement"] is True
    assert HEX256.fullmatch(success["evidence"]["receipt_sha256"])

    for item in profile["observations"]:
        if item["evidence_class"] != "observed_success":
            measured = item.get("measured")
            if measured is not None:
                assert measured.get("prompt_count", 0) == 0
                assert "job_start_to_success_seconds" not in measured
                assert "sampled_peak_vram_used_mib" not in measured


def test_observed_blocked_is_system_ram_not_vram_failure():
    profile = load_profile()
    blocked = observations_by_class(profile, "observed_blocked")
    assert len(blocked) == 1
    row = blocked[0]
    assert row["measured"]["prompt_count"] == 0
    assert row["measured"]["available_ram_mib_samples"] == [5759, 5741, 5737]
    assert row["resource_policy"]["min_available_ram_mib"] == 6000
    assert row["measured"]["free_vram_mib"] == 7353
    assert "system-RAM" in row["outcome"]
    assert any("VRAM incompatibility" in limit for limit in row["limits"])


def test_unknown_rows_cannot_be_read_as_success():
    profile = load_profile()
    unknown = observations_by_class(profile, "unknown")
    assert len(unknown) >= 8
    for row in unknown:
        assert row["measured"] is None
        assert row["evidence"] == {"kind": "none"}
        assert "Unknown" in row["outcome"]


def test_larger_models_and_other_vram_tiers_are_unknown():
    profile = load_profile()
    ids = {row["id"] for row in observations_by_class(profile, "unknown")}
    assert "unknown-sam2.1-large-8188" in ids
    assert "unknown-groundingdino-swinb-8188" in ids
    assert "unknown-quantized-tested-stack-8188" in ids
    assert "unknown-sdxl-segmentation-8188" in ids
    assert "unknown-other-vram-tiers" in ids
    assert "unknown-wsl-tested-stack" in ids
    assert "unknown-repeated-batch-throughput" in ids


def test_no_estimated_compatibility_is_promoted():
    profile = load_profile()
    assert profile["estimated_compatibility"] is None
    assert profile["file_size_context"]["total_installed_bytes"] == 1458753441
    assert "not a VRAM estimate" in profile["file_size_context"]["note"]
    assert not observations_by_class(profile, "estimated_unverified")


def test_unsupported_requires_demonstrated_incompatibility():
    profile = load_profile()
    assert profile["unsupported"] == []
    for row in profile["unsupported"]:
        assert row.get("technical_incompatibility_demonstrated") is True


def test_tested_components_hashes_and_total():
    profile = load_profile()
    config = profile["tested_configuration"]
    components = config["components"]
    assert len(components) == 8
    assert sum(item["bytes"] for item in components) == config["total_installed_bytes"]
    for item in components:
        assert HEX256.fullmatch(item["sha256"])
        assert item["source_revision"]
        assert item["license"] == "Apache-2.0"


def test_decision_flags_do_not_overclaim():
    profile = load_profile()
    decision = profile["decision"]
    assert decision["tested_8gb_stack"] == "observed_success_once"
    assert decision["current_6000_mib_system_ram_preflight"] == (
        "observed_blocked_on_system_ram_not_vram"
    )
    assert decision["no_measured_minimum_vram"] is True
    assert decision["not_a_general_8gb_support_claim"] is True
    assert decision["larger_models"] == "unknown"
    assert decision["other_vram_tiers"] == "unknown"
    assert decision["repeated_runs"] == "unknown"
