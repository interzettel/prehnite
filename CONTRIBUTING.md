# Contributing to Prehnite

Issues and focused pull requests are welcome. Use the MIT license for contributions.

Keep the Python core independent from image inference packages. Add providers behind typed adapters rather than importing their SDKs at module import time. Add unit tests that run without credentials or network access. A feature that consumes funds must be disabled by default and pass the configured cost gate.

Before opening a PR:
- Run unit tests and bytecode compilation.
- Verify CLI help and a synthetic demo ZIP.
- Avoid modifying unrelated accepted artifact metadata.
- Update provider license and capabilities documentation.
- Do not include real user images, API keys, prompts from private projects, or model weights.
