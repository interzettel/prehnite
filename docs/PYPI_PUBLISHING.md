# Publishing Prehnite on PyPI — isolated, reviewed workflow

**Released (2026-10-17):** [Prehnite 0.1.0a1 on PyPI](https://pypi.org/project/prehnite/0.1.0a1/) and [GitHub prerelease](https://github.com/interzettel/prehnite/releases/tag/v0.1.0a1). The [manual publishing run #39030551706](https://github.com/interzettel/prehnite/actions/runs/39030551706) passed both jobs, proving OIDC Trusted Publishing and project creation. The remainder of this document records the first-release procedure historically and its reusable safety gates; subsequent releases require reviewed version/workflow updates.

**Immutable uploaded checksums:** wheel SHA256 `098560a9de1c06afa01a605c5a7d8d3a02f3197a0c00c2e9fbba8914f6637908`; source archive SHA256 `d2eb9e662933b334e6be55b449850ec04b2bcbe29db810b74bec6167c549e4c2`. PyPI identifies `yigit-denktas` as the Owner. A pending publisher alone never reserved the project; the first upload did.

## Workflow separation

- **`.github/workflows/ci.yml` — CI only.** Runs on pushes and PRs, tests on Windows/Linux, builds/inspects source and wheel distributions, saves temporary `candidate-python-distributions` artifact. No OIDC permission, publish credentials, tagging or release creation.
- **`.github/workflows/publish.yml` — release only.** Dispatch manually from `main` with *exactly* `0.1.0a1` and typed `PUBLISH PREHNITE TO PYPI`; refuses other refs and versions. Reads a **completed successful push CI run for the exact SHA**, fetches only its validated candidate wheel/sdist, verifies filenames, content and Twine metadata, and creates the approved release artifact set.
- The publishing job waits for the GitHub environment **`pypi`**. After review, it re-verifies the same SHA/archived bytes, creates an **annotated** `v0.1.0a1` tag without overwriting old tags, uploads via commit-pinned `pypa/gh-action-pypi-publish` using OIDC (no API token), and creates a GitHub **prerelease** if PyPI succeeds. Failed uploads may leave a matching tag; reruns check it before proceeding.

## Original account-side setup (completed for 0.1.0a1)

### 1. Update the existing PyPI pending Trusted Publisher

The owner registered `prehnite` on PyPI for `interzettel/prehnite`, workflow `ci.yml`, PyPI environment *Any*, on 17 October 2026. **That old registration will not authenticate the new `publish.yml` workflow.**

On [PyPI trusted publisher management](https://pypi.org/manage/account/publishing/), **remove only the old pending `prehnite` / `interzettel/prehnite` / `ci.yml` entry**, then register a new pending publisher with:

| PyPI setting | Correct value |
| --- | --- |
| Project name | `prehnite` |
| Owner | `interzettel` |
| Repository | `prehnite` |
| Workflow filename | **`publish.yml`** (no path prefix) |
| Environment name | **`pypi`** (bind PyPI to the exact GitHub environment rather than Any) |

Ensure the new pending publisher confirmation is visible before dispatch. If PyPI reports that `prehnite` already exists, **stop** and check ownership; do not hijack another project name.

### 2. Protect the GitHub publishing environment

At [repository Settings → Environments](https://github.com/interzettel/prehnite/settings/environments) add or edit **`pypi`**:

1. Configure **required reviewers** (someone with appropriate repository permissions), disable self-review when GitHub offers that option, and ensure selected reviewer(s) will be able to approve the workflow.
2. Restrict deployment branches/tags to protected branches or specifically `main` as supported by GitHub plan/rules. The release workflow additionally hard-checks `refs/heads/main`, exact repository and SHA.
3. Prefer ruleset protection for `v*` release tags to prevent rewriting them, provided it permits the designated GitHub Actions bot to create new release tags.

A GitHub environment *name* is **not** proof that reviewers are configured. Without a required reviewer, do not manually dispatch the publishing workflow. The connected GitHub App cannot read/change repository environment protection or access the logged-in PyPI account.

## Versioned release procedure

1. Merge the dedicated workflow split PR and review the separate **`0.1.0a1` version PR**. The version PR changes `src/prehnite/_version.py`, dated `CHANGELOG.md` release notes, versioning/README status and nothing that silently asserts physical model validation.
2. On the merged version commit in `main`, check that [GitHub CI](https://github.com/interzettel/prehnite/actions/workflows/ci.yml) has finished **successfully**. In particular, inspect its saved `candidate-python-distributions` and checksums. Do **not** create a Git tag manually: the reviewed release job creates the annotated tag after its final owner environment approval.
3. Update PyPI Trusted Publisher and configure GitHub required-reviewer environment as above; then select **Actions → Publish PyPI → Run workflow** on `main`. Set `release_version = 0.1.0a1`, `confirmation = PUBLISH PREHNITE TO PYPI`.
4. `verify` refuses all but the approved version/main SHA and fetches **the exact successful CI run's** artifacts. It checks version/metadata and publishes only a short-lived GitHub artifact for release approval.
5. At the pending **`pypi` environment** job, inspect SHA, changelog, full build output and artifact SHA256. The reviewer can reject here. After approval, the job creates an immutable annotated tag, uploads to PyPI using OIDC, then publishes the GitHub prerelease and attaches exact distributions.
6. Verify [PyPI project](https://pypi.org/project/prehnite/), wheel/sdist hash, provenance and its upload attestations. Test a fresh `pip install prehnite==0.1.0a1` in a clean environment. Update issue #144, A2A #9 and changelog evidence. The pending publisher should be promoted after the first successful upload; check rather than assume.
7. If PyPI upload fails after creating the tag, **do not overwrite/tag-force, replay blindly, or claim a release**. Inspect PyPI first. Since uploaded filename/version pairs are immutable, genuine changes require a new version.

## Local non-publishing build check

```bash
python -m pip install build twine packaging
python -m build --outdir dist
python scripts/check_release_artifacts.py
python -m twine check --strict dist/*
```

The wheel/sdist and CI demonstrations do not establish real model quality, permitted checkpoint weights, physical GPU support, live API billing or production release status. All images/models run independently from the published orchestration package. Review [version policy](VERSIONING.md), [release policy](RELEASING.md), [public package description](PYPI_README.md).
