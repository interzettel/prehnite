"""Offline, deterministic dependency SBOM from pip's actual installed metadata.

No network calls, no runtime model weights, no legal-clearance assertions.
The exact-version lock is an *environment snapshot*, not an artifact-hash
lock or a promise of identical cross-platform resolution.

Use:
 python -m pip inspect --local > /private/pip-inspect.json
 python scripts/dependency_sbom.py --inspect /private/pip-inspect.json --extras dev --output /private/license-audit
"""
from __future__ import annotations

import argparse
from collections import deque
import json
from pathlib import Path
import re
import tomllib

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[1]
MAX_INSPECT_BYTES = 30_000_000
MAX_DISTS = 5000
MAX_DEPS = 10000
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
ALLOWED_EXCEPTIONS = {
    "model_checkpoint_weights", "hosted_provider_contracts",
    "third_party_media_rights", "missing_or_ambiguous_license_metadata",
}


class InventoryRefused(ValueError):
    """A missing or untrustworthy resolution cannot be an SBOM receipt."""


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise InventoryRefused(reason)


def _distribution(raw: dict) -> dict:
    require(isinstance(raw, dict), "invalid_distribution")
    meta = raw.get("metadata")
    require(isinstance(meta, dict), "distribution_missing_metadata")
    name, version = meta.get("name"), meta.get("version")
    require(isinstance(name, str) and NAME.fullmatch(name) is not None,
            "unsafe_distribution_name")
    require(isinstance(version, str) and len(version) < 128,
            "invalid_distribution_version")
    try:
        Version(version)
    except InvalidVersion as exc:
        raise InventoryRefused("invalid_distribution_version") from exc
    canonical = canonicalize_name(name)
    requires = meta.get("requires_dist") or []
    require(isinstance(requires, list) and len(requires) <= MAX_DEPS
            and all(isinstance(r, str) and len(r) < 2000 for r in requires),
            "invalid_installed_requires_dist")
    expression = meta.get("license_expression")
    fallback = meta.get("license")
    classifiers = meta.get("classifiers") or []
    require(expression is None or isinstance(expression, str), "invalid_license_expression")
    require(fallback is None or isinstance(fallback, str), "invalid_license_field")
    require(isinstance(classifiers, list) and all(isinstance(c, str) for c in classifiers),
            "invalid_license_classifiers")
    license_labels = sorted(
        c.removeprefix("License :: ").strip()
        for c in classifiers if c.startswith("License :: ")
    )
    if isinstance(expression, str) and expression.strip():
        license_source, signal = "spdx_expression", expression.strip()
    elif isinstance(fallback, str) and fallback.strip() and fallback.strip().upper() != "UNKNOWN":
        license_source, signal = "legacy_license_text", fallback.strip()[:500]
    elif license_labels:
        license_source, signal = "license_classifier", "; ".join(license_labels)[:500]
    else:
        license_source, signal = "missing", None
    return {
        "name": canonical, "version": version, "requires_dist": requires,
        "license_source": license_source, "license_signal": signal,
        # Inspect's direct_url/metadata_location may contain private paths or
        # credentials: deliberately never copy them to results.
    }


def _requirements(entries: list[str]) -> list[Requirement]:
    out = []
    for text in entries:
        require(isinstance(text, str) and len(text) < 2000, "bad_dependency_declaration")
        try:
            req = Requirement(text)
        except InvalidRequirement as exc:
            raise InventoryRefused("unparseable_dependency_declaration") from exc
        require(req.url is None, "direct_url_dependency_needs_manual_review")
        out.append(req)
    return out


def _selected(req: Requirement, extras: tuple[str, ...]) -> bool:
    return req.marker is None or any(
        req.marker.evaluate({"extra": extra}) for extra in (extras or ("",))
    )


def _load_policy(raw: dict) -> list[dict]:
    require(isinstance(raw, dict) and raw.get("schema_version") == 1,
            "invalid_license_policy")
    exceptions = raw.get("known_exceptions")
    require(isinstance(exceptions, list) and
            {x.get("kind") for x in exceptions if isinstance(x, dict)} == ALLOWED_EXCEPTIONS
            and len(exceptions) == len(ALLOWED_EXCEPTIONS),
            "missing_known_exception_categories")
    for item in exceptions:
        require(item.get("status") == "needs_separate_review"
                and isinstance(item.get("reason"), str) and len(item["reason"]) > 30,
                "unapproved_or_unexplained_license_exception")
    return sorted(exceptions, key=lambda x: x["kind"])


def generate(inspection: dict, pyproject: dict, policy: dict, *, extras: tuple[str, ...] = ()) -> dict:
    """Build a closed version-pinned dependency graph for selected root extras."""
    require(isinstance(inspection, dict) and isinstance(inspection.get("installed"), list),
            "invalid_pip_inspect_document")
    require(len(inspection["installed"]) <= MAX_DISTS, "too_many_installed_packages")
    project = pyproject.get("project", {})
    raw_name = project.get("name")
    require(isinstance(raw_name, str) and NAME.fullmatch(raw_name) is not None,
            "project_missing_name")
    root = canonicalize_name(raw_name)
    optional = project.get("optional-dependencies") or {}
    require(isinstance(optional, dict) and
            all(isinstance(k, str) and isinstance(v, list)
                for k, v in optional.items()), "invalid_project_extras")
    require(len(extras) == len(set(extras))
            and all(x in optional for x in extras), "unknown_or_duplicate_requested_extra")
    exceptions = _load_policy(policy)
    dist: dict[str, dict] = {}
    for raw in inspection["installed"]:
        p = _distribution(raw)
        require(p["name"] not in dist, "ambiguous_duplicate_installed_distribution")
        dist[p["name"]] = p
    require(root in dist, "project_must_be_installed_for_sbom")
    roots = _requirements(project.get("dependencies", []))
    for extra in extras:
        roots.extend(_requirements(optional[extra]))
    resolved: dict[str, dict] = {}
    edges: dict[str, set[str]] = {}
    # Carry explicitly selected extras through transitive declarations,
    # including e.g. package[socks], without downloading packages.
    queue = deque([(root, extras)])
    for req in roots:
        if _selected(req, extras):
            queue.append((canonicalize_name(req.name), tuple(sorted(req.extras))))
    visited: set[tuple[str, tuple[str, ...]]] = set()
    while queue:
        name, active_extras = queue.popleft()
        pair = (name, active_extras)
        if pair in visited:
            continue
        visited.add(pair)
        require(len(visited) <= MAX_DEPS, "dependency_expansion_limit")
        require(name in dist, "dependency_not_installed:" + name)
        package = dist[name]
        resolved[name] = package
        edges.setdefault(name, set())
        # Root requirements are the authoritative pyproject declarations;
        # installed metadata is authoritative for the transitive set.
        requirements = roots if name == root else _requirements(package["requires_dist"])
        for req in requirements:
            if not _selected(req, active_extras):
                continue
            child = canonicalize_name(req.name)
            require(child in dist, "dependency_not_installed:" + child)
            require(req.specifier.contains(dist[child]["version"], prereleases=True),
                    "resolved_version_violates_requirement:" + child)
            edges[name].add(child)
            queue.append((child, tuple(sorted(req.extras))))
    components = []
    license_review = []
    refs = {name: f"pkg:pypi/{name}@{p['version']}" for name, p in resolved.items()}
    for name, p in sorted(resolved.items()):
        licenses = []
        if p["license_source"] == "spdx_expression":
            licenses = [{"expression": p["license_signal"]}]
        elif p["license_signal"] is not None:
            licenses = [{"license": {"name": p["license_signal"]}}]
        review = p["license_source"] != "spdx_expression"
        if review:
            license_review.append({
                "name": name, "version": p["version"],
                "reason": "missing_or_non_spdx_license_metadata",
                "license_metadata_kind": p["license_source"],
                "license_metadata_signal": p["license_signal"],
                "status": "needs_separate_review",
            })
        components.append({
            "type": "library" if name != root else "application",
            "name": name, "version": p["version"], "bom-ref": refs[name],
            "purl": refs[name], "licenses": licenses,
            "properties": [
                {"name": "prehnite:license_signal_origin", "value": p["license_source"]},
                {"name": "prehnite:legal_approval", "value": "not_established"},
            ],
        })
    sbom = {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"component": {
            "type": "application", "name": root, "version": resolved[root]["version"],
            "bom-ref": refs[root],
        }},
        "components": components,
        "dependencies": [
            {"ref": refs[name], "dependsOn": sorted(refs[child] for child in children)}
            for name, children in sorted(edges.items())
        ],
    }
    locked = {
        "schema_version": 1, "kind": "environment_resolved_versions_only",
        "scope": "installed_prehnite_and_selected_dependency_closure",
        "extras": list(extras),
        "artifact_hashes_recorded": False,
        "cross_platform_reproducibility_proven": False,
        "components": [{"name": name, "version": p["version"]}
                       for name, p in sorted(resolved.items())],
    }
    license_report = {
        "schema_version": 1, "kind": "dependency_license_metadata_audit",
        "legal_clearance_established": False, "model_weights_included": False,
        "scanned_component_count": len(components),
        "needs_license_review": license_review,
        "known_exceptions": exceptions,
        "missing_or_ambiguous_metadata_count": len(license_review),
        "missing_dependency_count": 0,
    }
    return {"sbom": sbom, "resolved_versions": locked, "license_review": license_report}


def write_result(inspection: Path, output: Path, *,
                 extras: tuple[str, ...] = (), root: Path = ROOT) -> dict:
    source = inspection.resolve(strict=True)
    destination = output.resolve()
    require(destination != source and not destination.is_relative_to(source.parent)
            and (not destination.exists() or
                 (destination.is_dir() and not any(destination.iterdir()))),
            "output_must_be_new_and_separate")
    require(source.stat().st_size <= MAX_INSPECT_BYTES, "inspect_json_too_large")
    try:
        input_json = json.loads(source.read_text(encoding="utf-8"))
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        policy = json.loads((root / "progress/dependency_license_policy.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise InventoryRefused("malformed_dependency_inventory_input") from exc
    artifacts = generate(input_json, project, policy, extras=extras)
    destination.mkdir(parents=True, exist_ok=False)
    for name, value in artifacts.items():
        (destination / (name + ".json")).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    # Version pins only, NOT artifact-hash lock; do not pip install from it as
    # though it were vetted universal Python platform constraints.
    pins = "".join(
        f"{p['name']}=={p['version']}\n" for p in artifacts["resolved_versions"]["components"]
        if p["name"] != canonicalize_name(project["project"]["name"])
    )
    (destination / "resolved-versions.txt").write_text(pins, encoding="utf-8")
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extras", nargs="*", default=[])
    args = parser.parse_args()
    output = write_result(args.inspect, args.output, extras=tuple(args.extras))
    report = output["license_review"]
    print(json.dumps({
        "components": report["scanned_component_count"],
        "metadata_needing_manual_review": report["missing_or_ambiguous_metadata_count"],
        "legal_clearance_established": False,
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
