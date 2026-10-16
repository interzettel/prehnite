"""Documented Jev 1.14 JSON fixtures, no HTTP/API key/provider dispatch."""
from __future__ import annotations

import base64
import hashlib
import json
import math
from decimal import Decimal

import pytest
from PIL import Image

from prehnite.jev_wire_fixture import (
    VendorQuestion, build_offline_request_fixture,
    parse_official_mock_response, validate_vendor_questions)
from prehnite.typed_visual import Question, preflight, prepare_still_image


def vendor_questions():
    return (
        VendorQuestion("present", "noul",
                       "Is the main product fully visible in the image?"),
        VendorQuestion("category", "choice",
                       "Which technical failure category best fits the image?",
                       options=(("clean","No visible defect"),
                                ("cropped","Subject cut by the frame"))),
        VendorQuestion("severity", "score",
                       "How technically severe is the visible edge problem?",
                       levels=("None", "Small issue", "Strong artifact")),
        VendorQuestion("region", "box",
                       "Locate the product in the image if it is visible.",
                       presence_key="present"),
    )


def official_response(*, p=.92):
    return {
        "model": "jev-1.14.0",
        "answers": {
            "present": {"type": "noul", "noul": p},
            "category": {"type": "choice", "choice": "clean",
                         "confidence": .7,
                         "probabilities": {"clean": .8, "cropped": .2}},
            "severity": {"type": "score", "score": 1.43, "confidence": .35,
                         "legend": {"0":"None","1":"Small issue","2":"Strong artifact"},
                         "probabilities": {"0": 0.0,"1": 0.57,"2": 0.43}},
            "region": {"type":"box", "box":{
                "left": .1,"top": .2,"right": .8,"bottom": .9},
                "confidence": .9},
        },
        "usage": {"input_tokens": 2400, "output_tokens": 93},
    }


def image_and_permit(tmp_path, qs=None):
    root=tmp_path/"inputs"
    root.mkdir()
    image=root/"art.png"
    Image.new("RGB",(480,360),(9,74,58)).save(image)
    sha=hashlib.sha256(image.read_bytes()).hexdigest()
    receipt=prepare_still_image(root,"art.png",sha)
    questions=qs or vendor_questions()
    permit=preflight(receipt,tuple(
        Question(q.key,q.kind,options=tuple(k for k,_ in q.options),
                 presence_key=q.presence_key) for q in questions),
        allow_paid=True,allow_cloud_uploads=True,
        allow_experimental_images=True,allow_experimental_box=True,
        input_token_ceiling=8000,max_usd=Decimal(".001"))
    return receipt,permit,questions


def test_official_probability_and_level_position_are_not_boolean_quality():
    result=parse_official_mock_response(vendor_questions(),official_response(p=.4))
    assert result["answers"]["present"]["yes_probability"]==0.4
    assert result["answers"]["severity"]["position"]==1.43
    assert result["answers"]["category"]["selected"]=="clean"
    assert result["answers"]["region"]["masked_due_to_presence"] is True
    assert result["answers"]["region"]["box"] is None
    assert result["automatic_acceptance_authorized"] is False
    assert result["confidence_calibrated_on_our_images"] is False


def test_box_present_keeps_named_normalized_edges():
    output=parse_official_mock_response(vendor_questions(),official_response())
    assert output["answers"]["region"]["box"] == {
        "left":.1,"top":.2,"right":.8,"bottom":.9}
    assert output["answers"]["region"]["masked_due_to_presence"] is False


def test_inert_request_fixture_embeds_media_once_and_tracks_danger_zone(tmp_path):
    image,permit,questions=image_and_permit(tmp_path)
    fixture=build_offline_request_fixture(image,permit,questions)
    assert fixture.status=="offline_fixture_never_dispatched"
    assert fixture.model=="jev-1.14.0"
    assert fixture.proposed_headers == {"TypeSafe-Danger-Zone-Images":"true"}
    raw=fixture.request_json
    ref=raw["state"]["image"]
    assert len(raw["assets"])==1
    assert raw["assets"][ref]["type"]=="image"
    assert base64.b64decode(raw["assets"][ref]["data_base64"])==image.data
    assert json.dumps(raw).count(ref)==2  # state ref and assets-map key only
    assert raw["questions"]["region"] == {
        "type":"box",
        "instructions":"Locate the product in the image if it is visible."}
    assert raw["questions"]["severity"]["criteria"]==[
        "None","Small issue","Strong artifact"]
    assert "art.png" not in json.dumps(raw)
    assert fixture.serialized_bytes < fixture.estimated_expanded_bytes
    assert "data_base64" not in repr(fixture)


def test_request_permit_binding_and_token_count_cannot_be_swapped(tmp_path):
    image,permit,questions=image_and_permit(tmp_path)
    from dataclasses import replace
    with pytest.raises(ValueError,match="binding"):
        build_offline_request_fixture(image,replace(permit,image_sha256="a"*64),
                                      questions)
    with pytest.raises(ValueError,match="binding"):
        build_offline_request_fixture(image,replace(permit,question_count=1),
                                      questions)
    with pytest.raises(ValueError,match="binding"):
        build_offline_request_fixture(image,replace(permit,status="live_approved"),
                                      questions)


def test_explicit_long_context_header_is_only_a_proposal(tmp_path):
    image,permit,questions=image_and_permit(tmp_path)
    from dataclasses import replace
    plan=build_offline_request_fixture(
        image,replace(permit,experimental_long_context=True),questions)
    assert plan.proposed_headers["TypeSafe-Danger-Zone-Long-Context"]=="true"
    assert plan.status=="offline_fixture_never_dispatched"


@pytest.mark.parametrize("item",[
    {"type":"noul","noul":True},
    {"type":"noul","noul":float("nan")},
    {"type":"noul","noul":-0.1},
    {"type":"noul","noul":1.2},
    {"type":"noul","noul":"0.7"},
    {"type":"choice","choice":"yes"},
])
def test_noul_wrong_type_or_invalid_probability_never_accepted(item):
    response=official_response()
    response["answers"]["present"]=item
    with pytest.raises(ValueError):
        parse_official_mock_response(vendor_questions(),response)


def test_choice_distribution_and_selection_must_be_coherent():
    for changes in [
        {"probabilities":{"clean": .6, "cropped":.7}},
        {"probabilities":{"clean": .2, "cropped":.8}},
        {"probabilities":{"clean":.8, "other":.2}},
        {"confidence":float("inf")},
        {"choice":"unknown"},
    ]:
        response=official_response()
        response["answers"]["category"].update(changes)
        with pytest.raises(ValueError):
            parse_official_mock_response(vendor_questions(),response)


def test_score_position_uses_level_probability_weighted_expectation():
    for changed in [
        {"score":.72}, {"score":True},
        {"legend":{"0":"none", "1":"small", "2":"strong"}},
        {"probabilities":{"0": .2,"1": .2,"2":.2}},
        {"confidence":-0.1}
    ]:
        response=official_response()
        response["answers"]["severity"].update(changed)
        with pytest.raises(ValueError):
            parse_official_mock_response(vendor_questions(),response)


@pytest.mark.parametrize("box",[
    {"left":.8,"right":.7,"top":0,"bottom":1},
    {"left":True,"right":1,"top":0,"bottom":1},
    {"left":0,"right":1.1,"top":0,"bottom":1},
    {"left":0,"right":1,"top":0,"bottom":float("nan")},
    {"xmin":0,"xmax":1,"top":0,"bottom":1},
])
def test_official_box_edges_are_not_raw_unvalidated_coordinates(box):
    response=official_response()
    response["answers"]["region"]["box"]=box
    with pytest.raises(ValueError):
        parse_official_mock_response(vendor_questions(),response)


def test_wrong_model_request_extra_answers_and_usage_over_ceiling():
    for patch in [
        {"model":"jev-latest"},
        {"usage":{"input_tokens":True,"output_tokens":0}},
        {"answers":{"present":{"type":"noul","noul":1}}},
    ]:
        response=official_response()
        response.update(patch)
        with pytest.raises(ValueError):
            parse_official_mock_response(vendor_questions(),response)
    with pytest.raises(ValueError,match="ceiling"):
        parse_official_mock_response(vendor_questions(),official_response(),
                                     max_input_tokens=2000)


def test_malformed_question_specs_rejected_before_build(tmp_path):
    with pytest.raises(ValueError):
        VendorQuestion("bad!", "noul", "Are the pixels correctly cropped?")
    with pytest.raises(ValueError):
        VendorQuestion("category","choice","Classify the defect present?",
                       options=(("same","a"),("same","b")))
    with pytest.raises(ValueError):
        VendorQuestion("severity","score","How severe is the issue?",
                       levels=("only_one",))
    with pytest.raises(ValueError):
        validate_vendor_questions((VendorQuestion("region","box",
          "Find the subject bounding box.",presence_key="missing"),))


def test_no_network_apis_imported_or_default_batch_judge_replaced():
    import prehnite.jev_wire_fixture as module
    import inspect
    body=inspect.getsource(module)
    assert "httpx" not in body
    assert "requests.post" not in body
    assert "TypeSafeClient()" not in body
    from prehnite.judges import HaikuJudge, check_verdict
    assert HaikuJudge is not None and callable(check_verdict)
