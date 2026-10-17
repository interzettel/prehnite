# PyPI alpha publication: explicit owner-only gate

**Status:** Release tooling is under review. No PyPI upload, release tag or GitHub Release has occurred through this work. A pending publisher **does not reserve** the PyPI package name.

## Registered identity and security

On 17 October 2026 the owner registered a **pending** PyPI Trusted Publisher:

| Field | Expected |
| --- | --- |
| Project name | `prehnite` |
| GitHub owner / repository | `interzettel` / `prehnite` |
| Workflow filename | `ci.yml` |
| PyPI environment field | Any (no environment restriction in the PyPI registration) |
| GitHub publication job environment | `pypi` |

The publishing gate therefore lives in `.github/workflows/ci.yml`, **not** in a differently named workflow that PyPI could reject. The `pypi` GitHub environment is a distinct control and is compatible with a PyPI registration whose environment is unrestricted. Before the first release, the owner must open [GitHub repository environments](https://github.com/interzettel/prehnite/settings/environments), configure or verify the `pypi` environment, **require manual approval from a trusted reviewer**, and prohibit self-review if available. Refer to [PyPI security guidance](https://docs.pypi.org/trusted-publishers/security-model/). A named environment **without reviewer protections is not itself a manual approval**.

**PyPI can issue an OIDC-scoped short-lived token** only for the matching registered workflow. The publish job has `id-token: write`; all other jobs have no ID-token elevation. No personal or repository-wide `PYPI_TOKEN` secret is used. Publishing uses `pypa/gh-action-pypi-publish@release/v1`, which generates PyPI attestations under Trusted Publishing.

## Every pull request / normal main CI

- All existing zero-cost package/tests/rights/security evidence runs normally. No hosted inference or checkpoint downloads.
- `release-dist-audit` builds a wheel and source archive with `python -m build` and validates:
  - exactly one `prehnite-<VERSION>-py3-none-any.whl` and `prehnite-<VERSION>.tar.gz`;
  - canonical source, wheel and sdist versions and expected CLI entry points;
  - archive structure, source metadata and filename guardrails against private files/model checkpoints;
  - strict Twine package long-description/metadata rendering.
- The candidate archives are stored as a **temporary private-to-repo CI artifact**, not uploaded to PyPI. Review the archive hashes and contents. The temporary CI artifact is not a release.
- A separate, dedicated alpha version-bump PR changes only the authoritative `src/prehnite/_version.py` and release note/version documents; merging a tooling PR **does not bump the version**.

## First legitimate alpha release

1. Review and merge the release tooling PR and its CI; ensure other open PRs do not silently replace or weaken the release workflow.
2. Owner reviews a **dedicated** `0.1.0a1` version PR and makes an explicit public-alpha release decision. No inference quality, checkpoint licensing or production suitability is asserted by this prerelease.
3. Verify every CI job passed on the exact approved `main` commit, and download/inspect candidate wheel/sdist from its Actions run.
4. Owner creates the **immutable annotated tag** `v0.1.0a1` at that exact reviewed `main` commit (not a branch tip that might subsequently move). Protect `v*` tags using GitHub rulesets where available. Do not tag before approval.
5. In GitHub **Actions → CI → Run workflow** select branch **`main`**, enable `publish_to_pypi`, enter **`0.1.0a1`** as `release_version`, and enter the exact confirmation **`PUBLISH PREHNITE TO PYPI`**. The `release-verify` job refuses non-main runs, unrelated/missing/lightweight tags, mismatched source/package versions, missing artifact checks, failed CI gates, invalid/empty confirmation and non-alpha version strings.
6. The `publish-pypi` job waits for **GitHub environment `pypi` required reviewer approval**. The owner checks the SHA, built archive SHA256s, changelog, packaging metadata and version again, then explicitly approves. It downloads **only** the verified archives and uploads via OIDC (never from a PR/push/scheduled run).
7. After successful first upload, verify [the PyPI project](https://pypi.org/project/prehnite/) actually exists, wheel/sdist metadata matches, attestations are present, and the package installs from PyPI in an empty venv on Windows and Linux. The pending publisher should become an active project publisher automatically.
8. Create the accompanying approved GitHub Release pointing to the immutable tag; link documentation, source and distribution hashes, known limitations and license boundaries. Update the handoff issue #9 and the changelog evidence. Increment to the next development version in a separate PR.

**Failure:** If the PyPI project name is already taken before upload, stop and verify ownership/name policy; do **not** use a near-spelling impersonation or skip OIDC errors. If the environment has no required reviewer protection, **do not approve a public release**; configure it before dispatch. If upload status is uncertain, inspect the PyPI project/file list before trying again because package filenames/version uploads are immutable.

## Workstation inspection commands (offline)

```bash
python -m pip install build twine packaging
python -m build --outdir dist
python scripts/check_release_artifacts.py
python -m twine check --strict dist/*
python -m pip install --no-deps --force-reinstall dist/prehnite-*.whl
prehnite --help
prehnite-mcp --help
```

The packaging smoke test confirms import/CLI integrity, **not** functional model inference, true model licenses or GPU quality. Version policy: [VERSIONING.md](VERSIONING.md); wider release governance: [RELEASING.md](RELEASING.md).
