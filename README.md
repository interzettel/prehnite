# Prehnite

**Quality-gated, batch-first visual asset production.** Open source, local-first, agent-accessible, with optional pay-per-inference model APIs. MIT licensed.

Prehnite turns a structured asset specification into generated images, optional cutouts, metadata, cost/quality reports, and an exact ZIP directory tree. Its purpose is producing *accepted, usable assets* rather than counting raw generations.

> **Current status: v0.1 foundation.** The zero-cost demo backend is executable and intended for testing orchestration, not for producing photorealistic assets. The fal provider is opt-in and requires actual credentials and paid API calls. Advanced local GPU judges, ComfyUI execution and real-world image quality have not yet been validated. Do not mistake technical checks for human-calibrated visual quality.

## Principles

- Free MIT orchestration. No mandatory SaaS subscriptions or platform fees.
- Explicit authorization and hard budget reservation for every paid stage.
- Model/provider adapters rather than an application coupled to FLUX or ComfyUI.
- Versioned manifests, strict output-path validation, immutable intermediates.
- Per-asset quality thresholds, bounded targeted retries, no silently accepted failures.
- SQLite state and provider request IDs for recovery, machine-readable telemetry.
- Optional MCP tools for agent access; CLI remains fully usable without an agent.

## Quick start (Windows PowerShell)

    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -e ".[dev]"
    prehnite validate examples/manifest.yaml --profile examples/profile-demo.yaml
    prehnite estimate examples/manifest.yaml --profile examples/profile-demo.yaml
    prehnite run examples/manifest.yaml --profile examples/profile-demo.yaml --workspace workspace

This demo generates synthetic fixtures, not AI photographs. Review the output under workspace and inspect the CSV, JSON, HTML and ZIP report artifacts.

For local ComfyUI, run a separate ComfyUI server, export your workflows in API format into PREHNITE_WORKFLOWS, and configure matching node IDs in examples/profile-comfyui.yaml. Example node IDs are placeholders; a tested model graph is not bundled.

To enable fal inference, install the optional dependency and set FAL_KEY:

    pip install -e ".[fal]"
    $env:FAL_KEY = "<your API key>"
    prehnite validate examples/manifest.yaml --profile examples/profile-fal.yaml
    prehnite run examples/manifest.yaml --profile examples/profile-fal.yaml

Real fal requests may incur costs. The example fal profile enables paid processing and has a $10 maximum estimated budget; adjust it before use. Cloud prompts and images are shared with the provider.

## Manifest and profiles

- [Example manifest](examples/manifest.yaml) defines asset IDs, prompts or local sources, 9:16/3:4 targets, filenames and optional named cutouts.
- [Demo profile](examples/profile-demo.yaml) uses zero-cost synthetic workers.
- [fal profile](examples/profile-fal.yaml) demonstrates cloud generation and 2× upscale; the price estimates are provisional configuration, **not live prices**.

Jobs have separate source/variant/selected/derived stages. Only accepted images enter the requested output paths. Failed assets are explicitly recorded.

## Command surface

    prehnite models
    prehnite validate MANIFEST --profile PROFILE
    prehnite run MANIFEST --profile PROFILE --workspace workspace
    prehnite estimate MANIFEST --profile PROFILE
    prehnite status BATCH_ID --workspace workspace
    prehnite export BATCH_ID --workspace workspace
    prehnite-mcp

See [Readiness and work limits](docs/PROGRESS.md), [Architecture](docs/ARCHITECTURE.md), [Security](docs/SECURITY.md), [Evaluation](docs/EVALUATION.md), [Licensing](docs/LICENSING.md), and [Roadmap](docs/ROADMAP.md).

## Licensing

Core source code: MIT, copyright 2026 Studio Zettlerei. Model weights, datasets, and external applications are **not bundled** and keep their own licenses. The fal client and other optional integrations are separately licensed dependencies. See docs/LICENSING.md.

Contributions welcome after the contracts and security boundaries are stabilized.
