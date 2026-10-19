"""Readme graphics are offline, accessible and aligned with current Prehnite facts."""
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def test_readme_has_no_em_dashes():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "\u2014" not in readme
    assert "assets/diagrams/workflow.svg" in readme
    assert "assets/diagrams/roadmap.svg" in readme


def test_brand_diagrams_are_valid_local_accessible_svg():
    for name in ("workflow", "roadmap"):
        source = (ROOT / "assets/diagrams" / f"{name}.svg").read_text()
        root = ET.fromstring(source)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert root.attrib["viewBox"]
        assert root.find("{http://www.w3.org/2000/svg}title") is not None
        assert root.find("{http://www.w3.org/2000/svg}desc") is not None
        assert "#F6EFE2" in source
        assert "#075231" in source
        assert "#F7655B" in source
        assert "https://" not in source and "<script" not in source


def test_roadmap_svg_truthfully_marks_only_foundation_verified():
    image = (ROOT / "assets/diagrams/roadmap.svg").read_text()
    assert image.count("VERIFIED") == 1
    for gate in ("P1-M00", "P1-M01", "P1-M02", "P1-M03", "P1-M04", "P1-M05",
                 "P2-M01", "P2-M02", "P2-M03"):
        assert gate in image


def test_scoped_skill_includes_upstream_license_and_brand():
    skill = ROOT / ".agents/skills/diagram-design"
    assert (skill / "SKILL.md").is_file()
    assert (skill / "LICENSE.upstream").is_file()
    assert "MIT License" in (skill / "LICENSE.upstream").read_text()
    guide = (skill / "references/style-guide.md").read_text()
    for token in ("#F6EFE2", "#075231", "#A63D35"):
        assert token in guide


def test_readme_is_product_facing_and_backend_accurate():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "```text" not in readme
    assert "old ledger" not in readme.lower()
    assert "owner-mandated" not in readme.lower()
    assert "fal.ai" in readme
    assert "ComfyUI" in readme
    assert "60/80" in readme
    assert "75.0%" in readme
    assert "1/9" in readme


def test_diagram_coverage_matches_current_roadmap():
    import json

    current = json.loads((ROOT / "progress/roadmap.json").read_text())
    diagram = (ROOT / "assets/diagrams/roadmap.svg").read_text()
    total = len(current["tasks"])
    done = sum(t["state"] == "verified" for t in current["tasks"])
    assert (done, total) == (60, 80)
    assert "Engineering evidence 60 / 80" in diagram
    for m in current["milestones"]:
        assert m["id"] in diagram
        count = sum(
            next(t for t in current["tasks"] if t["id"] == task_id)["state"] == "verified"
            for task_id in m["gate_tasks"]
        )
        assert f"{count}/{len(m['gate_tasks'])}" in diagram
    workflow = (ROOT / "assets/diagrams/workflow.svg").read_text()
    for provider in ("COMFYUI", "FAL.AI", "DEMO", "Anthropic"):
        assert provider in workflow
