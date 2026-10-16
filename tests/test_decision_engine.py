"""Provider-neutral visual decision contract and reversible bounded policy tests.

All evidence is synthetic and local; no model, image API, or credentials.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from prehnite.decision_engine import (
    CAPABILITIES, CandidateState, DecisionEvidence, ModelCapabilities,
    RepairLimits, decide_candidate, normalized_mock_evidence,
    require_capability,
)
from prehnite.judges import Verdict

SHA = "a" * 64


def issue(cohort="product", technical="none", *, stage="cutout",
          attempts=0, repairs=0, accepted=False, uncertain=False, submitting=False,
          model=()):
    return CandidateState(
        cohort=cohort, technical_issue=technical, stage=stage,
        stage_attempts=attempts, local_repairs_used=repairs,
        accepted_output_exists=accepted, remote_charge_uncertain=uncertain,
        awaiting_provider_submission=submitting, model_evidence=model)


def enabled(**changes):
    options=dict(allow_technical_auto_rejection=True, allow_local_mask_repair=True,
                 maximum_local_repairs=1, maximum_total_stage_attempts=2)
    options.update(changes)
    return RepairLimits(**options)


def test_model_registry_declares_provider_specific_capabilities_and_experimental_status():
    assert set(CAPABILITIES)=={"jev","openai-compatible","anthropic","local"}
    assert CAPABILITIES["jev"].experimental is True
    assert CAPABILITIES["jev"].external_upload is True
    assert "bounding_box" in CAPABILITIES["jev"].kinds
    assert "bounding_box" not in CAPABILITIES["openai-compatible"].kinds
    assert CAPABILITIES["local"].external_upload is False
    assert CAPABILITIES["anthropic"].declares_calibrated_confidence is False


def test_model_capabilities_fail_closed_before_any_cloud_upload():
    with pytest.raises(PermissionError,match="Cloud"):
        require_capability("jev",kind="presence_probability",media="still_image")
    with pytest.raises(ValueError,match="Unsupported"):
        require_capability("anthropic",kind="bounding_box",media="still_image",
                           cloud_upload_authorized=True)
    with pytest.raises(ValueError,match="Unsupported"):
        require_capability("jev",kind="presence_probability",media="frame_sequence",
                           cloud_upload_authorized=True)
    assert require_capability("local",kind="technical_flag",media="still_image").provider=="local"
    assert require_capability("jev",kind="presence_probability",media="still_image",
                              cloud_upload_authorized=True).experimental is True


@pytest.mark.parametrize("provider,model",[
    ("anthropic","abc"),("local","wrong"),("jev","jev-latest"),("new","foo")])
def test_unpinned_or_unknown_model_evidence_is_rejected(provider,model):
    with pytest.raises(ValueError):
        DecisionEvidence(provider,model,"presence_probability",.6,"present",SHA)


@pytest.mark.parametrize("value",[True,False,"0.7",None,-1,2,float("nan"),float("inf")])
def test_probability_never_accepts_fabricated_numeric_inputs(value):
    with pytest.raises(ValueError):
        DecisionEvidence("jev",CAPABILITIES["jev"].model,
                         "presence_probability",value,"subject",SHA)


def test_judge_outputs_remain_semantically_distinct_and_unverified():
    present=DecisionEvidence("jev",CAPABILITIES["jev"].model,
                             "presence_probability",.9,"subject",SHA)
    rubric=DecisionEvidence("anthropic",CAPABILITIES["anthropic"].model,
                            "rubric_score",.9,"subject",SHA)
    assert present.kind != rubric.kind
    assert present.calibrated is False and rubric.calibrated is False
    with pytest.raises(ValueError,match="calibration"):
        DecisionEvidence("jev",CAPABILITIES["jev"].model,
                         "presence_probability",.99,"subject",SHA,calibrated=True)


def test_local_boolean_and_bbox_are_strictly_typed():
    cap=CAPABILITIES["local"]
    with pytest.raises(ValueError,match="Boolean"):
        DecisionEvidence("local",cap.model,"technical_flag",1,"mask_valid",SHA)
    ev=DecisionEvidence("local",cap.model,"technical_flag",False,"mask_valid",SHA)
    assert ev.value is False
    jev=CAPABILITIES["jev"]
    valid=DecisionEvidence("jev",jev.model,"bounding_box",(.1,.2,.9,1),"subject",SHA)
    assert valid.value[0]==.1
    for box in [(0,0,0,1),(0,.2,1,1.1),(True,.1,.8,.8),(0,0,float("nan"),1)]:
        with pytest.raises(ValueError):
            DecisionEvidence("jev",jev.model,"bounding_box",box,"subject",SHA)


def test_normalize_official_jev_mock_preserves_noul_probability_not_boolean():
    fixture={
        "status":"offline_vendor_response_fixture_only",
        "model":"jev-1.14.0","automatic_acceptance_authorized":False,
        "answers":{"subject":{"type":"noul","yes_probability":.73}},
    }
    value=normalized_mock_evidence("jev",response=fixture,
                                   subject="subject",image_sha256=SHA)
    assert value.kind=="presence_probability" and value.value==.73
    assert value.calibrated is False
    altered=dict(fixture,automatic_acceptance_authorized=True)
    with pytest.raises(ValueError,match="validated"):
        normalized_mock_evidence("jev",response=altered,subject="subject",
                                 image_sha256=SHA)


def test_normalize_structured_openai_fixture_requires_internal_schema():
    fixture={"schema_version":1,"status":"offline_fixture_no_provider",
             "question":"defect", "kind":"category_choice","value":"alpha_fringe"}
    ev=normalized_mock_evidence("openai-compatible",response=fixture,
                                subject="defect",image_sha256=SHA)
    assert ev.kind=="category_choice" and ev.value=="alpha_fringe"
    with pytest.raises(ValueError):
        normalized_mock_evidence("openai-compatible",
                                 response=dict(fixture,secret_request="PRIVATE"),
                                 subject="defect",image_sha256=SHA)


def test_legacy_anthropic_verdict_is_rubric_not_calibrated_yes_probability():
    value=normalized_mock_evidence("anthropic",response={
        "verdict":Verdict("A",{"A":.85,"B":.2},"less halos")},
        subject="A",image_sha256=SHA)
    assert value.kind=="rubric_score"
    assert value.value==.85
    with pytest.raises(ValueError,match="winner"):
        normalized_mock_evidence("anthropic",response={
            "verdict":Verdict("B",{"A":.85,"B":.2},"inconsistent")},
            subject="A",image_sha256=SHA)


def test_default_policy_is_read_only_and_cannot_auto_reject_or_repair():
    limits=RepairLimits()
    for technical in ("mask_empty","alpha_edge_contamination","image_geometry_invalid"):
        plan=decide_candidate(issue(technical=technical),limits)
        assert plan.action=="human_review"
        assert plan.requires_human is True
    assert limits.maximum_additional_paid_usd==Decimal(0)


@pytest.mark.parametrize("cohort,technical",[
    ("product","alpha_edge_contamination"),
    ("portrait","alpha_edge_contamination"),
])
def test_explicit_policy_schedules_only_one_nonpaid_local_mask_refinement(cohort,technical):
    plan=decide_candidate(issue(cohort,technical),enabled())
    assert plan.action=="repair_local_mask"
    assert plan.mutates_accepted_asset is False
    assert plan.would_spend_usd==Decimal(0)
    after=decide_candidate(issue(cohort,technical,attempts=1,repairs=1),enabled())
    assert after.action=="reject_candidate"
    assert after.reason_code=="technical_repair_exhausted"
    assert after.would_spend_usd==0


@pytest.mark.parametrize("technical",["mask_full_frame","image_geometry_invalid",
                                      "wrong_image_encoding"])
def test_deterministically_invalid_unaccepted_candidate_can_be_rejected(technical):
    result=decide_candidate(issue("product",technical),enabled())
    assert result.action=="reject_candidate"
    assert result.reason_code=="deterministic_invalid_candidate"


def test_subject_instance_ambiguity_never_auto_selects_product_or_person():
    for cohort in ("product","portrait"):
        state=issue(cohort,"subject_instance_ambiguous")
        out=decide_candidate(state,enabled())
        assert out.action=="human_review"
        assert out.reason_code=="multiple_subjects_require_selection"


def test_unknown_technical_issue_does_not_silently_trigger_regeneration():
    with pytest.raises(ValueError,match="Unknown"):
        issue(technical="random_model_failure")


@pytest.mark.parametrize("remote,awaiting",[(True,False),(False,True),(True,True)])
def test_ambiguous_paid_or_submitting_job_refuses_automatic_retry(remote,awaiting):
    plan=decide_candidate(issue(technical="mask_empty",uncertain=remote,
                                submitting=awaiting),enabled())
    assert plan.action=="human_review"
    assert plan.reason_code=="billing_or_submission_uncertain"


def test_existing_accepted_output_remains_immutable_even_for_real_hard_errors():
    for technical in ("mask_empty","image_geometry_invalid","alpha_edge_contamination"):
        out=decide_candidate(issue(technical=technical,accepted=True),enabled())
        assert out.action=="human_review"
        assert out.mutates_accepted_asset is False


def test_repair_and_stage_caps_prevent_unbounded_work():
    assert decide_candidate(issue(technical="alpha_edge_contamination",
                                  repairs=1,attempts=1),enabled()).action=="reject_candidate"
    capped=decide_candidate(issue(technical="mask_empty",repairs=0,attempts=2),enabled())
    assert capped.action=="human_review"
    assert capped.reason_code=="maximum_stage_attempts_reached"
    bad_stage=decide_candidate(issue(technical="alpha_edge_contamination",
                                    stage="generation"),enabled())
    assert bad_stage.action=="human_review"
    assert bad_stage.reason_code=="wrong_stage_for_local_repair"


def test_uncalibrated_judges_cannot_trigger_unapproved_auto_accept_or_reject():
    evidence=DecisionEvidence("jev",CAPABILITIES["jev"].model,
                              "presence_probability",.999,"subject",SHA)
    result=decide_candidate(issue("portrait","none",model=(evidence,)),enabled())
    assert result.action=="human_review"
    assert result.reason_code=="uncalibrated_visual_decision"
    evidence2=DecisionEvidence("anthropic",CAPABILITIES["anthropic"].model,
                               "rubric_score",.01,"subject",SHA)
    out=decide_candidate(issue("product","none",model=(evidence2,)),enabled())
    assert out.action=="human_review"


def test_explicit_model_abstention_cannot_cause_hard_reject():
    evidence=DecisionEvidence("jev",CAPABILITIES["jev"].model,
                              "presence_probability","abstain","subject",SHA,
                              status="abstained")
    result=decide_candidate(issue("portrait","image_geometry_invalid",
                                  model=(evidence,)),enabled())
    assert result.action=="human_review"
    assert result.reason_code=="model_abstained"


@pytest.mark.parametrize("amount",[Decimal("0.001"),Decimal("-1"),
                                   Decimal("NaN"),Decimal("Infinity"),1])
def test_local_policy_never_introduces_paid_retry_even_with_owner_opt_in(amount):
    with pytest.raises(ValueError,match="cannot authorize paid"):
        enabled(maximum_additional_paid_usd=amount)


def test_policy_configuration_caps_are_validated():
    for x in [True,-1,4,1.5]:
        with pytest.raises(ValueError):
            enabled(maximum_local_repairs=x)
    for x in [True,0,6]:
        with pytest.raises(ValueError):
            enabled(maximum_total_stage_attempts=x)


def test_product_portrait_synthetic_cohorts_have_distinct_behaviors_and_no_spend():
    cases=[
        ("product","mask_empty","human_review"),
        ("product","mask_full_frame","reject_candidate"),
        ("product","subject_instance_ambiguous","human_review"),
        ("portrait","alpha_edge_contamination","repair_local_mask"),
        ("portrait","subject_instance_ambiguous","human_review"),
        ("portrait","image_geometry_invalid","reject_candidate"),
    ]
    seen={c:set() for c,_,_ in cases}
    for cohort,technical,expected in cases:
        result=decide_candidate(issue(cohort,technical),enabled())
        assert result.action==expected
        assert result.would_spend_usd==0
        seen[cohort].add(technical)
    assert len(seen["product"])==len(seen["portrait"])==3

def test_empty_mask_is_not_repaired_using_local_alpha_morphology():
    state=issue("product","mask_empty")
    for limits in (enabled(), RepairLimits()):
        plan=decide_candidate(state,limits)
        assert plan.action=="human_review"
        assert plan.reason_code=="empty_mask_needs_new_segmentation_or_human"
