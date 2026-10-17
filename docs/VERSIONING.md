# Versioning policy

**Canonical version:** [src/prehnite/_version.py](../src/prehnite/_version.py), currently \`0.1.0.dev0\` (development only).

The \`[project]\` metadata in \`pyproject.toml\` specifies \`dynamic = ["version"]\`, and Hatchling reads the value from \`src/prehnite/_version.py\`. The public \`prehnite.__version__\` imports from that same file; no copy-pasted version constant exists elsewhere in executable metadata.

## Public compatibility rules

- Use **Semantic Versioning** for release intentions (\`MAJOR.MINOR.PATCH\`) and **PEP 440** for Python development/pre-release suffixes.
- Until 1.0, minor versions may introduce breaking API changes, which must be documented prominently.
- Development builds are \`X.Y.Z.devN\`, beta builds \`X.Y.ZbN\`, release candidates \`X.Y.ZrcN\`, stable \`X.Y.Z\`.
- Prefix Git annotated release tags with \`v\` (e.g. \`v0.1.0\`) **only once approved**. Tags must point to a tested release commit and match the package version without the \`v\`.
- \`CHANGELOG.md\` always has an **Unreleased** section; move changes to a dated version section only when actually shipping.
- Do not bump version for every issue/PR; make dedicated release-candidate/version PRs so the source of truth cannot drift.
- Do not claim an API/CLI format is stable until contracts and migration behavior are tested.

## Alpha release packaging

The planned first public developer preview is `0.1.0a1`, subject to separately approved artifacts and release authorization; this section **does not bump** the canonical `0.1.0.dev0` source version. Review [the PyPI runbook](PYPI_PUBLISHING.md) and the [release playbook](RELEASING.md) before a dedicated version PR, annotated tag, protected GitHub environment approval and manual OIDC upload. The PyPI long description is the deliberately small [PyPI README](PYPI_README.md), rather than relying on repository-relative links or CSS in the full GitHub README.

## Validation

Install editable package and run:
\`\`\`bash
python scripts/check_governance.py
python scripts/board.py --check
python -m pip wheel --no-deps -w dist .
\`\`\`

The governance check compares \`prehnite.__version__\`, the installed package metadata and Hatch's configured source; it rejects duplicated static project versions, missing changelog, or a malformed version.
