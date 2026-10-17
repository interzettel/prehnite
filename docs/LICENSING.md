# License policy

Prehnite's original source code is MIT-licensed (see LICENSE). Optional model weights, hosted APIs and separately installed software retain their own licenses and terms. Neither MIT nor the Prehnite package changes those terms.

No checkpoint or dataset is bundled. Users must independently review commercial-use, redistribution, training and output-use restrictions for any model they choose. In particular, Black Forest Labs FLUX weights are not simply MIT because the adapter is MIT. ComfyUI is separately licensed and accessed as a standalone process through an API, not vendored into the core.

When adding a provider, record its model identifier, purpose, endpoint schema, source, terms URL, version, applicable restrictions, and the date verified. Third-party dependency licenses must be reviewed before distribution and publishing on PyPI. No warranty of permission is made for third-party model use.


## Offline SBOM for dependency and transitive-license audit (R06-A01)

Prehnite does not bundle third-party model weights or proprietary training data.
The following generates a **CycloneDX 1.5 dependency SBOM** of the installed,
exact-version **Python distribution closure** for one interpreter/extras
selection. This is evidence for a human license audit, **not** proof that
Prehnite and all its models, media and redistributions are legally cleared.

Run in a fresh, representative Python environment:

```bash
python -m pip install -e ".[dev]"
python -m pip inspect --local > /private/pip-inspect.json
python scripts/dependency_sbom.py \
  --inspect /private/pip-inspect.json \
  --extras dev \
  --output /private/prehnite-license-audit
```

The output directory must not exist beforehand:

- `sbom.json` — CycloneDX 1.5 dependency graph, package/version and
  **license metadata signal**; environment-local private paths and direct
  URLs from pip inspect are intentionally removed.
- `resolved_versions.json` and `resolved-versions.txt` — **exact installed
  versions**, with a clear warning: no wheel file hashes, and not a
  universally reproducible Linux/Windows artifact lock. Do not silently
  confuse an environment snapshot with a reviewed hash-pinned lock.
- `license_review.json` — packages with absent, classifier-only or legacy
  non-SPDX license metadata requiring confirmation, plus the known unresolved
  categories in `progress/dependency_license_policy.json`.

The script refuses missing distributions, duplicate installed package names,
unexpected direct URL requirements, unknown extras and incompatible version
specifiers. The inspection input never needs an upload or network connection.
Windows and Ubuntu CI independently produce 14-day downloadable SBOM artifacts
using free package installation; source and user-private image bytes stay out
of those artifacts.

**Scope limits:** A declared SPDX expression is a machine-readable *claim
in package metadata*, not legal sign-off. The Python SBOM does not inspect
model checkpoint licenses, provider output-use agreements, trained model
redistribution conditions, fonts, photos or other third-party media.
Those are the separately scoped R06-A02/R06-A03 tasks; final compliance
approval remains R06-A04 and its parent release gate #40.

No release, PyPI upload, paid model inference or license waiver is authorized.
