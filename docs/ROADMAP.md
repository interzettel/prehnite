# Roadmap (issues should reference acceptance tests)

**Progress and agent tasks:** [Verified 61-unit release ledger](progress/STATUS.md) · [Atomic task dashboard and acceptance criteria](progress/ATOMIC.md) · [Frozen PR-sized register](../progress/atomic.json) · [Current iteration board](SPRINT.md). The atomic percentage is scoped only to the 19 unfinished release units from its initial baseline, not overall project progress.

## v0.1: executable architecture, no mandatory cloud costs
- [x] Strict manifest/profile validation and output path safety
- [x] Demo provider and documented opt-in fal generation/upscaling
- [x] Journaled stage execution and estimated budget reservations
- [x] Selectable image variants and bounded generation retry
- [x] Optional Haiku pair judgments and cutout QA
- [x] PNG cutouts from mask outputs with technical validation
- [x] JSON/CSV/HTML reports and ZIP containing accepted deliverables
- [x] CLI and stdio MCP entrypoint
- [ ] End-to-end paid API smoke test with actual model schemas and billing (requires credentials)
- [ ] Production validation on Windows AORUS RTX 4070 Laptop

## v0.2: robust production
- [x] Generic ComfyUI API graph/queue/history adapter (not hardware-validated)
- [ ] Tested ComfyUI graphs, model offloading, GPU resource management and cancellation
- [ ] Local ESRGAN/SAM/BiRefNet adapters with version-pinned checkpoints
- [ ] Local HPS/Q-ReAlign judges and crop-aware 4K QA
- [ ] Region-level detection, multi-object instance handling and proper alpha matting
- [ ] Structured corrective plans (segment alternate, refine, edit versus regenerate)
- [ ] Provider schema conformance tests, measured cost estimation and invoice reconciliation
- [ ] Shadow-mode evaluations, category thresholds and calibration tools
- [ ] Deterministic task-key/content-addressed cache, transaction-safe output writes
- [ ] Robust cancellation, job locking, concurrent readers and interrupted process recovery

## v0.3+: production ergonomics
- [ ] Inspectable HTML dashboard with image comparison / masks
- [ ] Native Parquet report export and performance/cost comparisons
- [ ] Cross-batch benchmark report and accepted-asset efficiency
- [ ] Optional HTTP MCP deployment with auth and threat model
- [ ] Provider packs and reusable workflow registry
- [ ] Installer and reproducible Windows/Linux integration tests

## Definition of done
The repo is only production-ready after a 90-asset mixed-resolution run, paid-call reconciliation, restart recovery tests, image/cutout visual auditing, security testing, licensing review and reproducible benchmark documentation.
