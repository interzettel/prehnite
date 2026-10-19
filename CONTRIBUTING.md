# Contributing to Prehnite

Issues and focused pull requests are welcome. Use the MIT license for contributions.

Keep the Python core independent from image inference packages. Add providers behind typed adapters rather than importing their SDKs at module import time. Add unit tests that run without credentials or network access. A feature that consumes funds must be disabled by default and pass the configured cost gate.

Workflow and versions: [docs/AGILE.md](docs/AGILE.md), [docs/SPRINT.md](docs/SPRINT.md), [docs/VERSIONING.md](docs/VERSIONING.md), [CHANGELOG.md](CHANGELOG.md). Follow the pull request template; never tag or publish from an ordinary feature PR.

For v2 roadmap work, claim a task in `progress/roadmap.json`, state whether it is research, implementation, experiment or human acceptance, link the existing GitHub issue and attach the matching evidence. Run `python scripts/roadmap.py --write` after reviewed changes (or `--check` when unchanged). The original 61-unit and 73-task ledgers are immutable historical archives. Physical GPU tests require separate authorization.

Before opening a PR:
- Run unit tests and bytecode compilation.
- Verify CLI help and a synthetic demo ZIP.
- Avoid modifying unrelated accepted artifact metadata.
- Update provider license and capabilities documentation.
- Do not include real user images, API keys, prompts from private projects, or model weights.

For a clean packaging check on a machine with Python 3.12 and network access
to install ordinary Python dependencies, run `python -m pip install build`
followed by `python scripts/smoke_install.py`. CI runs this on Ubuntu and
Windows, using a new isolated venv and only the bundled synthetic generator.
This is distinct from actual GPU model testing.
