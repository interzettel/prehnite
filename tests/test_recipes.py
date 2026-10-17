"""No-network contracts for future installable micro/macro model blueprints."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from prehnite.recipes import Recipe, describe_recipe, load_recipe, recipe_sha256

ROOT = Path(__file__).resolve().parents[1]
MICRO = ROOT / "recipes/prehnite-micro/0.1.0-preview.1.json"
MACRO = ROOT / "recipes/prehnite-macro/0.1.0-preview.1.json"


def parsed(path=MICRO):
    return json.loads(path.read_text(encoding="utf-8"))


def refuses(value, pattern: str):
    with pytest.raises((ValueError, ValidationError), match=pattern):
        Recipe.model_validate(value)


def test_both_default_blueprints_have_no_execution_or_paid_capability():
    micro, macro = load_recipe(MICRO), load_recipe(MACRO)
    assert (micro.id, micro.kind) == ("prehnite-micro", "micro")
    assert (macro.id, macro.kind) == ("prehnite-macro", "macro")
    assert len(micro.stages) == len(macro.stages) == 3
    for recipe in (micro, macro):
        info = describe_recipe(recipe)
        assert info["executable"] is False
        assert info["hardware_verified"] is False
        assert info["weights_included"] is False
        assert info["automatic_spending_enabled"] is False
        assert info["external_model_rights_approved"] is False
        assert info["has_unresolved_model_pins"] is True
        assert len(info["sha256"]) == 64
        assert recipe_sha256(recipe) == recipe_sha256(load_recipe(MICRO if recipe is micro else MACRO))
        assert recipe.policy.allow_paid is False
        assert recipe.policy.allow_cloud_uploads is False
        assert recipe.policy.auto_download_weights is False
    assert not describe_recipe(micro)["contains_hosted_models"]
    assert describe_recipe(macro)["contains_hosted_models"]


@pytest.mark.parametrize("operation,pattern", [
    (lambda d: d.update(release_status="production_ready"), "blueprint_only"),
    (lambda d: d.update(hardware_status="verified_8gb"), "unverified"),
    (lambda d: d["policy"].update(allow_paid=True), "False"),
    (lambda d: d["policy"].update(allow_cloud_uploads=True), "False"),
    (lambda d: d["policy"].update(max_usd=2), "0"),
    (lambda d: d["policy"].update(auto_download_weights=True), "False"),
    (lambda d: d["policy"].update(bundle_model_weights=True), "False"),
    (lambda d: d.update(version="latest"), "semantic version"),
    (lambda d: d.update(id="prehnite-macro"), "disagree"),
    (lambda d: d["stages"].append(deepcopy(d["stages"][1])), "Duplicate stage IDs"),
    (lambda d: d["stages"][1].update(depends_on=["invalid"]), "Unknown dependency"),
    (lambda d: d["stages"][1].update(depends_on=["cutout"]), "Self-referential"),
    (lambda d: d["stages"][0].update(depends_on=["cutout"]), "Generation is a root"),
    (lambda d: d["stages"][1].update(operation="generate", model={"provider":"demo", "model":"synthetic", "pin_status":"unresolved", "license_review":"bundled_demo_code_only"}), "Generation is a root"),
    (lambda d: d["stages"][1].update(model={"provider":"fal",
                                           "model":"blackforestlabs/flux-3/text-to-image",
                                           "pin_status":"unresolved","license_review":"required"}),
     "Local stage cannot pretend"),
    (lambda d: d["stages"][1]["model"].update(license_review="bundled_demo_code_only"),
     "cannot inherit"),
    (lambda d: d["stages"][1]["model"].update(revision="latest"), "Unresolved model"),
    (lambda d: d["stages"][1]["model"].update(weight_sha256="f"*64), "Unresolved model"),
    (lambda d: d["stages"][1]["model"].update(source_url="http://example.com/model"), "plain HTTPS"),
    (lambda d: d["stages"][1]["model"].update(source_url="https://bob:secret@hf.example/path"),
     "plain HTTPS"),
    (lambda d: d["stages"][1]["model"].update(model="nonexistent-local-model"), "Unknown or nonimplemented"),
])
def test_unsupported_advertising_fails_closed(operation, pattern):
    value=parsed()
    operation(value)
    refuses(value,pattern)


def test_graph_cycles_and_mask_without_source_image_refused():
    x=parsed()
    x["stages"][1]["depends_on"]=["quality"]
    x["stages"][2]["depends_on"]=["generate","cutout"]
    refuses(x,"Image processing stage needs an RGB image input")
    x=parsed()
    x["stages"][1]["depends_on"]=["generate","quality"]
    x["stages"][2]["depends_on"]=["generate","cutout"]
    refuses(x,"cycle")


def test_missing_required_stages_and_unknown_capabilities_fail():
    x=parsed()
    x["stages"]=[x["stages"][0],x["stages"][2]]
    x["stages"][1]["depends_on"]=["generate"]
    refuses(x,"at least one cutout")
    x=parsed(MACRO)
    x["stages"][1]["operation"]="matte"
    x["stages"][1]["model"]["provider"]="fal"
    x["stages"][1]["model"]["model"]="fal-ai/birefnet/v2"
    x["stages"][1]["execution"]="hosted"
    refuses(x,"nonimplemented model capability")


def test_micro_cannot_accidentally_include_cloud_api_stage():
    x=parsed()
    x["stages"][0]["model"]={
        "provider":"fal","model":"blackforestlabs/flux-3/klein/text-to-image",
        "pin_status":"unresolved","license_review":"required"
    }
    x["stages"][0]["execution"]="hosted"
    refuses(x,"Micro recipes must remain local-first")


def test_macro_cloud_stages_remain_design_only_even_with_pinned_contract():
    x=parsed(MACRO)
    assert Recipe.model_validate(x).policy.allow_paid is False
    x["policy"]["allow_paid"]=True
    refuses(x,"False")
    x=parsed(MACRO)
    x["stages"][0]["model"]["pin_status"]="locally_hashed"
    x["stages"][0]["model"]["revision"]="sha256-revision"
    x["stages"][0]["model"]["weight_sha256"]="a"*64
    refuses(x,"Local weight pin")


def test_local_revision_can_be_hashed_without_claiming_rights_or_hardware():
    x=parsed()
    m=x["stages"][0]["model"]
    m.update(pin_status="locally_hashed",revision="revision-a1",weight_sha256="c"*64)
    recipe=Recipe.model_validate(x)
    assert recipe.stages[0].model.weight_sha256=="c"*64
    assert not describe_recipe(recipe)["executable"]
    assert not describe_recipe(recipe)["hardware_verified"]


def test_canonical_hash_independent_of_json_dict_key_order(tmp_path):
    x=parsed()
    assert recipe_sha256(Recipe.model_validate(x)) == recipe_sha256(
        Recipe.model_validate(dict(reversed(list(x.items()))))
    )
    x["description"]="Different valid description for this preview-only model blueprint."
    assert recipe_sha256(Recipe.model_validate(x)) != recipe_sha256(load_recipe(MICRO))


def test_loader_refuses_duplicates_symlinks_bad_types_and_oversized_files(tmp_path):
    path=tmp_path/"recipe.json"
    source=MICRO.read_text(encoding="utf-8")
    path.write_text(source.replace('"schema_version": 1,',
                                   '"schema_version": 1, "schema_version": 1,'))
    with pytest.raises(ValueError,match="Duplicate JSON key"):
        load_recipe(path)
    path.write_text(source)
    link=tmp_path/"linked.json"
    try:
        link.symlink_to(path)
    except (OSError, NotImplementedError):
        pytest.skip("OS does not permit creating symlinks")
    with pytest.raises(ValueError,match="regular local JSON"):
        load_recipe(link)
    too_big=tmp_path/"huge.json"
    too_big.write_bytes(b" " * (129 * 1024))
    with pytest.raises(ValueError,match="size"):
        load_recipe(too_big)
    path.write_text('{"schema_version": 1, "id": 42}')
    with pytest.raises(ValidationError):
        load_recipe(path)


def test_source_uri_never_dispatches_or_fetches():
    micro,macro=load_recipe(MICRO),load_recipe(MACRO)
    assert all(x.model.pin_status=="unresolved" for x in macro.stages)
    assert all(x.model.pin_status=="unresolved" for x in micro.stages)
    # Planning is pure metadata; there is no provider dispatch method.
    assert not hasattr(micro, "run")
    assert not hasattr(macro, "download")
