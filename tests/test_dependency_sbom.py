"""Deterministic offline dependency graph, license metadata and failure controls."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from copy import deepcopy

import pytest

ROOT=Path(__file__).resolve().parents[1]


def script():
    spec=importlib.util.spec_from_file_location("sbom_tool",ROOT/"scripts/dependency_sbom.py")
    module=importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def policy():
    return json.loads((ROOT/"progress/dependency_license_policy.json").read_text())


def package(name, version, requires=(), *, expression=None, license_text=None,
            classifiers=None, path="/private/DO_NOT_LEAK/key.pem"):
    return {"metadata":{
        "name":name,"version":version,"requires_dist":list(requires),
        "license_expression":expression,"license":license_text,
        "classifiers":classifiers or []},
        "metadata_location":path,
        "direct_url":{"url":"https://secret.invalid?token=NEVER-OUTPUT"},
        "installer":"pip",
    }


def fixture():
    pyproject={"project":{
        "name":"Prehnite", "dependencies":["alpha>=1,<2","optional>=2; python_version<'3.0'"],
        "optional-dependencies":{"dev":["pytest>=8,<10"]}}}
    inspection={"version":"1","installed":[
        package("Prehnite","0.1.0.dev0",expression="MIT"),
        package("Alpha","1.2.3",requires=["beta>=2,<3","optional; extra=='gpu'"],
                expression="BSD-3-Clause"),
        package("Beta","2.1",license_text="Legacy custom license text"),
        package("pytest","8.4.0",requires=["beta>=2.0"],classifiers=[
            "License :: OSI Approved :: MIT License"]),
        package("optional","2.3.0",expression="Apache-2.0"),
        package("unrelated","22.2.2",expression="GPL-3.0-only"),
    ]}
    return inspection,pyproject,policy()


def test_exact_installed_closure_and_license_ambiguity():
    module=script()
    inspection,project,exceptions=fixture()
    report=module.generate(inspection,project,exceptions)
    pins=report["resolved_versions"]
    assert pins["extras"]==[]
    assert pins["artifact_hashes_recorded"] is False
    assert pins["cross_platform_reproducibility_proven"] is False
    assert [(x["name"],x["version"]) for x in pins["components"]]==[
        ("alpha","1.2.3"),("beta","2.1"),("prehnite","0.1.0.dev0")]
    sbom=report["sbom"]
    assert sbom["specVersion"]=="1.5"
    assert len(sbom["components"])==3
    deps={x["ref"]:x["dependsOn"] for x in sbom["dependencies"]}
    assert deps["pkg:pypi/prehnite@0.1.0.dev0"]==["pkg:pypi/alpha@1.2.3"]
    assert deps["pkg:pypi/alpha@1.2.3"]==["pkg:pypi/beta@2.1"]
    assert sbom["components"][0]["licenses"]==[{"expression":"BSD-3-Clause"}]
    lic=report["license_review"]
    assert lic["legal_clearance_established"] is False
    assert lic["missing_or_ambiguous_metadata_count"]==1
    assert lic["needs_license_review"][0]["name"]=="beta"
    assert len(lic["known_exceptions"])==4
    assert "NEVER-OUTPUT" not in json.dumps(report)
    assert "DO_NOT_LEAK" not in json.dumps(report)
    assert "unrelated" not in json.dumps(report)


def test_opt_in_extra_is_scoped_and_non_default_packages_excluded():
    module=script()
    ins,proj,pol=fixture()
    report=module.generate(ins,proj,pol,extras=("dev",))
    names={x["name"] for x in report["resolved_versions"]["components"]}
    assert names=={"alpha","beta","pytest","prehnite"}
    assert report["resolved_versions"]["extras"]==["dev"]
    assert report["license_review"]["missing_or_ambiguous_metadata_count"]==2


@pytest.mark.parametrize("modify,code",[
    (lambda i,p: i["installed"].pop(2),"dependency_not_installed"),
    (lambda i,p: i["installed"][1]["metadata"].update(version="3.0"),"resolved_version_violates"),
    (lambda i,p: i["installed"][1]["metadata"].update(name="../alpha"),"unsafe_distribution_name"),
    (lambda i,p: i["installed"].append(i["installed"][1]),"ambiguous_duplicate"),
    (lambda i,p: p["project"].update(dependencies=["badpkg @ https://private.invalid/a"]),"direct_url_dependency"),
    (lambda i,p: p["project"].update(dependencies=["??broken"]), "unparseable_dependency"),
])
def test_invalid_or_unpinned_dependency_resolution_refuses(modify,code):
    module=script()
    ins,proj,pol=fixture()
    modify(ins,proj)
    with pytest.raises(module.InventoryRefused,match=code):
        module.generate(ins,proj,pol)


def test_unknown_or_duplicate_extras_cannot_change_denominator_silently():
    mod=script()
    ins,project,pol=fixture()
    for extras in (("dev","dev"),("remote-paid",)):
        with pytest.raises(mod.InventoryRefused,match="unknown_or_duplicate"):
            mod.generate(ins,project,pol,extras=extras)


def test_explicit_extra_dependency_edge_in_transitive_closure():
    mod=script()
    ins,proj,pol=fixture()
    proj["project"]["dependencies"]=["alpha[gpu]>=1,<2"]
    result=mod.generate(ins,proj,pol)
    assert {i["name"] for i in result["resolved_versions"]["components"]}=={
        "prehnite","alpha","beta","optional"}
    assert result["sbom"]["dependencies"][0]["dependsOn"]==[
        "pkg:pypi/beta@2.1","pkg:pypi/optional@2.3.0"]


def test_poor_policy_cannot_clear_non_python_license_rights():
    mod=script()
    ins,proj,pol=fixture()
    pol=deepcopy(pol)
    pol["known_exceptions"][0]["status"]="approved"
    with pytest.raises(mod.InventoryRefused,match="unapproved_or_unexplained"):
        mod.generate(ins,proj,pol)
    pol=deepcopy(policy())
    pol["known_exceptions"].pop()
    with pytest.raises(mod.InventoryRefused,match="missing_known_exception"):
        mod.generate(ins,proj,pol)


def test_generate_to_separate_folder_and_no_overwrite(tmp_path):
    mod=script()
    ins,proj,pol=fixture()
    data=tmp_path/"inspect.json"
    data.write_text(json.dumps(ins))
    root=tmp_path/"project"
    root.mkdir()
    (root/"pyproject.toml").write_text(
        '[project]\nname="Prehnite"\ndependencies=["alpha>=1,<2"]\n'
        '[project.optional-dependencies]\ndev=["pytest>=8,<10"]\n')
    (root/"progress").mkdir()
    (root/"progress/dependency_license_policy.json").write_text(json.dumps(pol))
    out=tmp_path/"audit-out"
    result=mod.write_result(data,out,root=root)
    assert result["license_review"]["scanned_component_count"]==3
    assert (out/"sbom.json").is_file()
    pins=(out/"resolved-versions.txt").read_text()
    assert pins=="alpha==1.2.3\nbeta==2.1\n"
    assert json.loads((out/"resolved_versions.json").read_text())["components"]
    with pytest.raises(mod.InventoryRefused,match="output_must_be_new"):
        mod.write_result(data,out,root=root)
    with pytest.raises(mod.InventoryRefused,match="output_must_be_new"):
        mod.write_result(data,data.parent,root=root)


def test_missing_root_or_spdx_data_is_not_a_legal_pass():
    mod=script()
    ins,proj,pol=fixture()
    ins["installed"]=[x for x in ins["installed"] if x["metadata"]["name"]!="Prehnite"]
    with pytest.raises(mod.InventoryRefused,match="project_must_be_installed"):
        mod.generate(ins,proj,pol)
    ins,proj,pol=fixture()
    ins["installed"][0]["metadata"]["license_expression"]=None
    output=mod.generate(ins,proj,pol)
    assert output["license_review"]["legal_clearance_established"] is False
    assert output["license_review"]["missing_or_ambiguous_metadata_count"]==2
