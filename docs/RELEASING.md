# Release playbook (manual releases only)

**Current state:** development baseline only. No release tag, GitHub Release or PyPI distribution is created merely by adding publishing infrastructure. A legitimate early alpha can ship only after explicit owner approval. See [PyPI OIDC publication runbook](PYPI_PUBLISHING.md) for the registered `ci.yml` workflow, artifact validation, annotated-tag and protected-environment requirements.

## Release candidate checklist

1. Decide scope and evidence from [AGILE.md](AGILE.md), [SPRINT.md](SPRINT.md), PRs and release gates in [PROGRESS.md](PROGRESS.md) (currently introduced by PR #10).
2. Ensure strict manifests, provider and output contracts, model/weight licenses, provenance, cost limits and recovery are validated. Run synthetic, platform-specific and separately approved live-provider integration tests as applicable.
3. Audit dependencies/security and redact any keys, internal prompts, private source images or personal data.
4. Open a **version-bump PR** updating only \`src/prehnite/_version.py\` to the target stable version, moving finished notes out of \`[Unreleased]\` in \`CHANGELOG.md\` into \`[X.Y.Z] - YYYY-MM-DD\`, and updating docs/migrations if required.
5. Obtain human review and green CI on that exact commit. Build wheel/sdist and test clean-install imports/CLI; verify their embedded version equals the target and validate hashes.
6. Obtain explicit owner approval for shipping, including any public distribution or external publishing. **Do not tag before approval.**
7. Only *after* approval, make one immutable annotated \`vX.Y.Z\` tag at the approved release commit, draft release notes from the changelog and create a GitHub Release. Publishing to PyPI is a separately authorized action, not an automatic consequence of Git tagging.
8. After publishing, bump to the next \`.dev0\` series in a separate follow-up PR. Keep \`[Unreleased]\` ready for further changes.
9. Record the release commit, tag, checksums, release URL, known limitations and deployment notes in #9 and roadmap.

## Prohibited by default

- No push-tag automation, automatic publishing, public package releases or API charges in routine PR/main CI. Ordinary CI builds inspectable candidate wheels and sdists, but cannot upload them.
- No assumption that third-party models inherit MIT permissions.
- Never rewrite already published version tags. If a release is wrong, issue a new version and document the correction.
