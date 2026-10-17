"""Read-only, fail-closed provenance audit for externally referenced models.

Does not download weights, call providers, or grant model/use rights. Review
sources are recorded with dates in progress/model_rights_inventory.json.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlsplit

from prehnite.registry import MODELS

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "progress/model_rights_inventory.json"
REPORT = ROOT / "docs/MODEL_RIGHTS_AUDIT.md"


class ModelTermsRefused(ValueError):
    """Unverified or overclaimed model rights provenance."""


def require(ok: bool, problem: str) -> None:
    if not ok:
        raise ModelTermsRefused(problem)


def valid_text(value: object, minimum: int = 20, maximum: int = 700) -> bool:
    return isinstance(value, str) and minimum <= len(value.strip()) <= maximum and "\x00" not in value


def valid_url(url: object) -> bool:
    if not isinstance(url, str) or len(url) > 800:
        return False
    parsed = urlsplit(url)
    # This is a documented set of upstream authorities, not evidence that
    # any linked page legally licenses a checkpoint or its generated outputs.
    upstream_hosts = {"fal.ai", "www.anthropic.com", "github.com",
                      "bfl.ai", "huggingface.co"}
    return (parsed.scheme == "https" and parsed.hostname in upstream_hosts
            and not parsed.username and not parsed.password and not parsed.fragment
            and not parsed.query)


def valid_date(value: object, now: date) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date(2025, 1, 1) <= date.fromisoformat(value) <= now
    except ValueError:
        return False


def validate(raw: dict, *, today: date | None = None) -> dict:
    """Verify registry coverage and unresolved status, NOT external legal facts."""
    today = today or date.today()
    require(isinstance(raw, dict) and raw.get("schema_version") == 1,
            "unsupported_model_rights_inventory_schema")
    require(raw.get("registry_module") == "prehnite.registry",
            "unexpected_registry_origin")
    require(raw.get("no_model_weights_bundled") is True,
            "bundled_model_weights_not_in_scope")
    require(valid_date(raw.get("checked_on"), today),
            "invalid_inventory_review_date")
    require(valid_text(raw.get("scope")), "missing_scope_disclaimer")
    records, candidates = raw.get("external_models"), raw.get("candidate_checkpoint_families")
    require(isinstance(records, list) and 0 < len(records) <= 100
            and isinstance(candidates, list) and 0 < len(candidates) <= 100,
            "invalid_inventory_count")
    expected = {(m.provider, m.model) for m in MODELS if m.provider != "demo"}
    observed = set()
    for item in records:
        require(isinstance(item, dict), "invalid_model_record")
        key = (item.get("provider"), item.get("model"))
        require(all(isinstance(x, str) and x for x in key), "invalid_registry_model_key")
        require(key not in observed, "duplicate_external_model")
        observed.add(key)
        require(item.get("execution") in ("hosted_api", "user_supplied_workflow"),
                "invalid_model_execution_boundary")
        require(valid_url(item.get("terms_url")), "missing_valid_model_terms_url")
        require(valid_date(item.get("license_reviewed_on"), today), "invalid_model_review_date")
        require(item.get("model_weights") == "not_bundled"
                and item.get("weight_license_approval") == "not_established"
                and item.get("source_code_license_inherited") is False
                and item.get("model_training_rights") == "not_established"
                and item.get("model_redistribution_rights") == "not_established"
                and item.get("external_terms_review") == "required",
                "unverified_model_rights_must_never_be_approved")
        require(valid_text(item.get("finding")) and valid_text(item.get("training_review")),
                "missing_model_specific_rights_rationale")
    require(observed == expected,
            f"external_model_coverage_mismatch:{sorted(expected-observed)}:{sorted(observed-expected)}")
    seen_refs = set()
    for item in candidates:
        require(isinstance(item, dict), "invalid_checkpoint_candidate")
        ref = item.get("ref")
        require(isinstance(ref, str) and ref and ref not in seen_refs,
                "duplicate_or_invalid_checkpoint_ref")
        seen_refs.add(ref)
        require(valid_text(item.get("name"), 5, 200), "missing_checkpoint_name")
        require(valid_url(item.get("source_url")) and valid_url(item.get("terms_url")),
                "missing_primary_checkpoint_terms_urls")
        require(valid_date(item.get("verified_on"), today), "invalid_checkpoint_review_date")
        require(item.get("checkpoint_hash_verified") is False
                and item.get("license_approval") == "requires_manual_review",
                "unverified_checkpoint_cannot_be_licensed_by_assumption")
        require(item.get("claim_type") in (
                "upstream_model_weight_license_label", "model_specific_noncommercial_terms",
                "model_code_and_weights_license_terms", "software_license_only"),
                "invalid_model_license_claim_type")
        for field in ("license_label", "training_review", "redistribution_review"):
            require(valid_text(item.get(field)), "missing_checkpoint_rights_rationale")
    require("black-forest-labs/FLUX.1-dev" in seen_refs,
            "missing_known_noncommercial_flux_example")
    return {"external_model_count": len(records), "checkpoint_examples": len(candidates),
            "rights_approved": 0, "weight_hashes_verified": 0,
            "source_license_grants_inferred": 0, "checked_on": raw["checked_on"]}


def cell(value: object) -> str:
    return str(value).replace("|", "/").replace("\n", " ").replace("\r", " ")


def markdown(raw: dict) -> str:
    stats = validate(raw)
    lines = [
        "# Prehnite — model and checkpoint rights provenance", "",
        "> Generated from §progress/model_rights_inventory.json§ using "
        "§python scripts/model_rights.py --write§. Upstream claims and terms "
        "review, **not legal clearance, permission to train, or authorization to spend**.",
        "",
        f"**Source-check date:** {stats['checked_on']} · "
        f"**External interfaces:** {stats['external_model_count']} · "
        f"**Optional checkpoint examples:** {stats['checkpoint_examples']} · "
        "**Weight hashes independently verified:** 0 · **Rights approved:** 0.",
        "",
        "## Hosted and user-supplied adapter boundaries", "",
        "The registry describes interfaces, not distributed weights. A hosted API's "
        "commercial-use label does not grant a license to rehost its checkpoints.",
        "",
        "| Provider | Exact model or workflow | Boundary | Original source | Still requires review |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in raw["external_models"]:
        lines.append(
            f"| {cell(item['provider'])} | §{cell(item['model'])}§ "
            f"| {cell(item['execution'])} | [Terms/endpoint]({item['terms_url']}) "
            f"| {cell(item['training_review'])} |"
        )
    lines += ["", "## Optional checkpoint examples — none bundled", "",
        "| Candidate | Upstream label | Terms | Review work |",
        "| --- | --- | --- | --- |"]
    for item in raw["candidate_checkpoint_families"]:
        lines.append(
            f"| [{cell(item['name'])}]({item['source_url']}) "
            f"| {cell(item['license_label'])} ({cell(item['claim_type'])}) "
            f"| [Read original terms]({item['terms_url']}) "
            f"| {cell(item['training_review'])} {cell(item['redistribution_review'])} |"
        )
    lines += ["", "## Boundaries and next evidence", "",
        "- **Proven by this register:** every external provider/model in the live "
        "capability registry has a separate rights-review entry and authoritative link.",
        "- **Not proven:** exact checkpoint revision and hash, training data provenance, "
        "commercial use, model redistribution, local hosting and output rights.",
        "- FLUX.1 dev uses a distinct non-commercial license; FLUX.1 schnell has "
        "a separately reported Apache-2.0 label. Neither license transfers to FLUX.3 hosted APIs.",
        "- SAM 3 materials use Meta's SAM License, but the precise rights for "
        "the hosted SAM 3.1 variant still need confirmation.",
        "- ComfyUI's GPL and Real-ESRGAN source BSD-3-Clause are software "
        "terms, not blanket permission to distribute all checkpoint weights or workflow nodes.",
        "- Hosted providers also have account-specific handling, output and training terms. "
        "This tool does not connect to any service or process private images.",
        "",
        "## Future closeout procedure", "",
        "1. Identify exact checkpoint revision, download and full SHA256.",
        "2. Record specific model weights, code, hosted API, training, output-use and "
        "redistribution terms independently with primary source and revision.",
        "3. Obtain explicit human legal/commercial review before lifting any restriction. "
        "Do not infer a license from MIT project code, GPL UI software, or API marketing.",
        "4. Regenerate this audit and pass §python scripts/model_rights.py --check§ "
        "on the same commit. Do not commit weights or owner's private media.",
        "",
        "**R06-A02 is a documented research inventory, not R06 release sign-off.** "
        "R06-A01 dependency closure, R06-A03 media audit, and R06-A04 human "
        "release compliance remain separate.", "",
    ]
    return "\n".join(lines).replace("§", chr(96))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = json.loads(INVENTORY.read_text(encoding="utf-8"))
    output = markdown(raw)
    if args.write:
        REPORT.write_text(output, encoding="utf-8")
    elif not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != output:
        raise SystemExit("Model rights report stale; run python scripts/model_rights.py --write")
    print("Model terms provenance checked, with zero rights granted.")


if __name__ == "__main__":
    main()
