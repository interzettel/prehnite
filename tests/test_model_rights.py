"""License provenance is coverage/exception evidence, not a license grant."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest

from prehnite.registry import MODELS

ROOT = Path(__file__).resolve().parents[1]


def module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("model_rights", ROOT / "scripts/model_rights.py")
    obj = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(obj)
    return obj


def inventory():
    return json.loads((ROOT / "progress/model_rights_inventory.json").read_text(encoding="utf-8"))


def test_current_registry_external_coverage_and_no_implicit_license():
    r = module()
    data = inventory()
    result = r.validate(data, today=date(2026, 10, 17))
    assert result["external_model_count"] == 9
    assert result["checkpoint_examples"] == 4
    assert result["rights_approved"] == 0
    assert result["weight_hashes_verified"] == 0
    assert {(entry["provider"],entry["model"]) for entry in data["external_models"]} == {
        (m.provider, m.model) for m in MODELS if m.provider != "demo"
    }
    assert all(x["model_training_rights"] == "not_established" for x in data["external_models"])
    assert all(x["model_redistribution_rights"] == "not_established" for x in data["external_models"])
    assert all(x["license_approval"] == "requires_manual_review" for x in data["candidate_checkpoint_families"])


def test_committed_human_report_matches_generator_exactly():
    r = module()
    data = inventory()
    assert r.REPORT.read_text(encoding="utf-8") == r.markdown(data)
    contents = r.markdown(data)
    assert "FLUX.1 dev uses a distinct non-commercial license" in contents
    assert "R06-A02 is a documented research inventory" in contents
    assert "Rights approved:** 0" in contents


@pytest.mark.parametrize("mutate,error", [
    (lambda d: d["external_models"].pop(), "coverage_mismatch"),
    (lambda d: d["external_models"].append(deepcopy(d["external_models"][0])), "duplicate_external_model"),
    (lambda d: d["external_models"][0].update(model="invented/provider"), "coverage_mismatch"),
    (lambda d: d["external_models"][0].update(weight_license_approval="approved"), "unverified_model_rights"),
    (lambda d: d["external_models"][0].update(model_training_rights="granted"), "unverified_model_rights"),
    (lambda d: d["external_models"][0].update(source_code_license_inherited=True), "unverified_model_rights"),
    (lambda d: d["external_models"][0].update(terms_url="http://localhost/private"), "missing_valid_model_terms_url"),
    (lambda d: d["external_models"][0].update(terms_url="https://example.com/?secret=abc"), "missing_valid_model_terms_url"),
    (lambda d: d["external_models"][0].update(training_review="none"), "missing_model_specific_rights_rationale"),
    (lambda d: d["candidate_checkpoint_families"][0].update(checkpoint_hash_verified=True), "unverified_checkpoint"),
    (lambda d: d["candidate_checkpoint_families"][0].update(license_approval="approved"), "unverified_checkpoint"),
    (lambda d: d["candidate_checkpoint_families"].pop(1), "missing_known_noncommercial_flux_example"),
    (lambda d: d.update(checked_on="2099-01-01"), "invalid_inventory_review_date"),
    (lambda d: d.update(no_model_weights_bundled=False), "bundled_model_weights"),
])
def test_missing_rights_metadata_and_approval_claims_are_refused(mutate,error):
    r=module()
    data=inventory()
    mutate(data)
    with pytest.raises(r.ModelTermsRefused, match=error):
        r.validate(data,today=date(2026,10,17))


def test_source_date_is_required_and_pinned_to_actual_review():
    r=module()
    data=inventory()
    data["candidate_checkpoint_families"][0]["verified_on"]="2026-10-20"
    with pytest.raises(r.ModelTermsRefused,match="invalid_checkpoint_review_date"):
        r.validate(data,today=date(2026,10,17))


def test_local_workflow_license_not_inherited_from_gpl_or_mit():
    data=inventory()
    for record in data["external_models"]:
        if record["provider"]=="comfyui":
            assert record["execution"]=="user_supplied_workflow"
            assert record["source_code_license_inherited"] is False
            assert record["model_redistribution_rights"]=="not_established"
    assert any(c["claim_type"]=="software_license_only" for c in data["candidate_checkpoint_families"])


def test_upstream_dev_terms_not_assumed_for_flux_3_hosted():
    data=inventory()
    flux=[r for r in data["external_models"] if r["model"].startswith("blackforestlabs/flux-3/")]
    assert len(flux)==2
    assert all(r["execution"]=="hosted_api" for r in flux)
    assert all("fal.ai/models/" in r["terms_url"] for r in flux)
    assert all(r["model_training_rights"]=="not_established" for r in flux)
