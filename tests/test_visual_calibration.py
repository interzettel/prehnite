"""Offline Jev Noul gold-label evaluation: reliability and reserved-cost evidence."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from prehnite.visual_calibration import (
    evaluate_binary_visual_gold, write_aggregate_gold_report,
)


def row(prob, label, *, cohort="synthetic", tokens=1000):
    return {"yes_probability":prob, "gold_yes":label,
            "cohort":cohort, "reserved_input_tokens":tokens}


def evaluate(rows, **kw):
    return evaluate_binary_visual_gold(
        rows, declared_source="synthetic_fixture", **kw)


def test_perfect_fixture_has_zero_brier_zero_ece_and_full_coverage():
    samples=[row(1.0,True) for _ in range(10)]+[
        row(0.0,False) for _ in range(10)]
    metrics=evaluate(samples)
    assert metrics["examples"]==20
    assert metrics["brier_score"]==0
    assert metrics["expected_calibration_error_10bin"]==0
    assert metrics["coverage"]==1
    assert metrics["accepted"]==10
    assert metrics["rejected"]==10
    assert metrics["abstained"]==0
    assert metrics["false_accepts"]==0
    assert metrics["false_rejects"]==0
    assert metrics["correct_nonabstaining_decisions"]==20
    assert metrics["label_provenance_verified_independently"] is False
    assert metrics["human_aesthetic_quality_certified"] is False
    assert metrics["actual_provider_invoice_usd"] is None
    assert metrics["inference_executed_by_evaluator"] is False


def test_false_accept_false_reject_and_abstention_are_separately_counted():
    samples=[row(.95, False),row(.05,True),row(.5,True)]
    metrics=evaluate(samples)
    assert metrics["false_accepts"]==1
    assert metrics["false_rejects"]==1
    assert metrics["abstained"]==1
    assert metrics["accepted"]==1
    assert metrics["rejected"]==1
    assert metrics["coverage"]==round(2/3,8)
    assert metrics["false_accept_rate_of_accepted"]==1
    assert metrics["false_reject_rate_of_rejected"]==1
    assert metrics["correct_nonabstaining_decisions"]==0
    assert metrics["quoted_reserved_usd_per_correct_decision_estimate"] is None
    assert metrics["brier_score"]>0
    assert metrics["small_sample_warning"] is True


def test_reserved_cost_is_not_actual_invoice_and_never_guessed():
    samples=[row(.95, True,tokens=1000),row(.05,False,tokens=1000),
             row(.5,False,tokens=1000)]
    data=evaluate(samples)
    assert data["all_token_reservations_known"] is True
    assert data["total_reserved_input_tokens"]==3000
    assert Decimal(data["quoted_reserved_usd_estimate"])==Decimal("0.000126")
    assert Decimal(data["quoted_reserved_usd_per_correct_decision_estimate"])==Decimal("0.000063")
    assert data["actual_provider_invoice_usd"] is None
    samples[1]["reserved_input_tokens"]=None
    unknown=evaluate(samples)
    assert unknown["total_reserved_input_tokens"] is None
    assert unknown["quoted_reserved_usd_estimate"] is None
    assert unknown["quoted_reserved_usd_per_correct_decision_estimate"] is None


def test_empty_action_categories_do_not_create_zero_division_fabrication():
    data=evaluate([row(.5,True)])
    assert data["coverage"]==0
    assert data["false_accept_rate_of_accepted"] is None
    assert data["false_reject_rate_of_rejected"] is None
    assert data["false_accept_rate_wilson95_of_accepted"] is None
    assert data["false_reject_rate_wilson95_of_rejected"] is None
    assert data["quoted_reserved_usd_per_correct_decision_estimate"] is None


def test_wilson_intervals_in_range_with_zero_failures():
    data=evaluate([row(.9,True)]*25 + [row(.1,False)]*25)
    assert data["false_accept_rate_wilson95_of_accepted"][0]==0
    assert 0<data["false_accept_rate_wilson95_of_accepted"][1]<1
    assert data["false_reject_rate_wilson95_of_rejected"][0]==0


def test_cohort_breakdown_aggregates_without_raw_identifiers():
    rows=[row(.9,True,cohort="cutout") for _ in range(20)]
    rows += [row(.7,False,cohort="generation") for _ in range(22)]
    result=evaluate(rows)
    assert set(result["cohorts"])=={"cutout","generation"}
    assert result["cohorts"]["cutout"]["count"]==20
    assert result["cohorts"]["generation"]["abstained"]==22
    assert result["small_sample_warning"] is True
    assert "source_path" not in json.dumps(result)


def test_reliability_bins_are_aggregate_not_sample_dumps():
    obs=[row(.6,True),row(.6,False),row(.2,False),row(.95,True)]
    result=evaluate(obs)
    bins=result["reliability_bins"]
    assert len(bins)==10
    assert sum(b["count"] for b in bins)==4
    assert all(b["observed_accuracy"] is None for b in bins if b["count"]==0)
    assert 0<=result["expected_calibration_error_10bin"]<=1


def test_threshold_boundaries_are_declared_with_no_hidden_default_actions():
    data=evaluate([row(.2,False),row(.8,True),row(.21,True),row(.79,False)])
    assert data["rejected"]==1
    assert data["accepted"]==1
    assert data["abstained"]==2
    assert data["correct_nonabstaining_decisions"]==2


@pytest.mark.parametrize("value",[True,False,None,"0.5",-0.1,1.1,float("nan"),float("inf")])
def test_invalid_probability_rejected(value):
    with pytest.raises(ValueError):
        evaluate([row(value,True)])


@pytest.mark.parametrize("value",[0,1,None,"yes",float("nan")])
def test_gold_label_must_be_boolean(value):
    with pytest.raises(ValueError,match="Boolean"):
        evaluate([row(.9,value)])


@pytest.mark.parametrize("cohort",[
    "Evil-Cohort","../secret","valid/path","person@example.com","",
    "s"*41,"one two","\u0000evil",
])
def test_cohort_labels_cannot_leak_metadata(cohort):
    with pytest.raises(ValueError,match="Cohort"):
        evaluate([row(.9,True,cohort=cohort)])


def test_extra_raw_asset_identifiers_prompts_and_paths_disallowed():
    raw=row(.9,True)
    for key in ("image_path","asset_id","prompt","provider_request_id","filename"):
        sample=dict(raw)
        sample[key]="PRIVATE_VALUE"
        with pytest.raises(ValueError,match="privacy-unsafe"):
            evaluate([sample])


def test_nonfinite_price_and_unknown_provenance_rejected():
    for price in (Decimal("NaN"),Decimal("Infinity"),Decimal("-1")):
        with pytest.raises(ValueError):
            evaluate([row(.9,True)],price_usd_per_million=price)
    with pytest.raises(ValueError,match="provenance"):
        evaluate_binary_visual_gold([row(.9,True)],declared_source="jev_verified_by_ai")


def test_malformed_thresholds_and_token_counts_rejected():
    for lo,hi in [(0.8,0.2),(.5,.9),(.1,.5),(-1,1)]:
        with pytest.raises(ValueError,match="threshold"):
            evaluate([row(.9,True)],lower=lo,upper=hi)
    for value in (True,-1,262001,0.5,"100"):
        with pytest.raises(ValueError,match="token"):
            evaluate([row(.9,True,tokens=value)])


def test_private_aggregate_json_export_is_deterministic(tmp_path):
    report=evaluate([row(0.9,True),row(.2,False)])
    out=tmp_path/"aggregate.json"
    assert write_aggregate_gold_report(out,report)==out
    first=out.read_bytes()
    write_aggregate_gold_report(out,report)
    assert first==out.read_bytes()
    assert json.loads(first)==report
    assert b"provider_request_id" not in first
    with pytest.raises(ValueError):
        write_aggregate_gold_report(tmp_path/"private.csv",report)


def test_public_cli_emits_only_private_aggregate_report(tmp_path):
    from typer.testing import CliRunner
    from prehnite.cli import app
    source=tmp_path/"raw-gold-private.json"
    records=[row(1,True,cohort="product"),row(0,False,cohort="cutout")]
    source.write_text(json.dumps({
        "schema_version":1,"declared_source":"synthetic_fixture",
        "observations":records
    }),encoding="utf-8")
    target=tmp_path/"summary.json"
    result=CliRunner().invoke(app,[
        "evaluate-visual-gold","--input",str(source),
        "--output",str(target),
    ])
    assert result.exit_code==0,result.output
    report=json.loads(target.read_text(encoding="utf-8"))
    assert report["examples"]==2
    assert report["human_aesthetic_quality_certified"] is False
    assert "raw-gold-private" not in target.read_text()
    assert "gold_yes" not in target.read_text()
    assert "no transport" not in target.read_text()
    assert source.exists()


def test_cli_rejects_malicious_extra_gold_fields(tmp_path):
    from typer.testing import CliRunner
    from prehnite.cli import app
    source=tmp_path/"private.json"
    source.write_text(json.dumps({
        "schema_version":1,"declared_source":"synthetic_fixture",
        "observations":[row(.9,True)],
        "secret_api_key":"DO_NOT_COPY"
    }))
    out=tmp_path/"out.json"
    result=CliRunner().invoke(app,[
        "evaluate-visual-gold","--input",str(source),"--output",str(out)])
    assert result.exit_code!=0
    assert not out.exists()
