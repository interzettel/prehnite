# Offline hardware doctor (read-only preview)

After installing Prehnite, run `prehnite hardware` (or `python scripts/hardware_doctor.py` from the repository root). The command prints JSON and does **not** infer, load or download any model, contact external services, benchmark a GPU, write private hardware receipts or enable paid inference.

## Contract

- `schema_version: 1` identifies this diagnostic JSON shape; it is not a benchmark schema or compatibility certificate.
- OS, architecture and Python runtime come from Python's `platform` APIs; logical CPU count comes from `os.cpu_count`, not a measured processor throughput score.
- Linux RAM is read from `/proc/meminfo`; Windows RAM from `GlobalMemoryStatusEx`; macOS total RAM from `sysctl hw.memsize` (macOS available RAM is not measured). Unknown values are `null`, **not zero**.
- Free/total disk space refers to the current user's home filesystem; it does **not** promise that a proposed checkpoint fits another destination.
- NVIDIA GPU name, driver and dedicated VRAM come from local `nvidia-smi` if the executable responds with usable data. Absence or failure of `nvidia-smi` means **not measured**, not "no GPU". AMD, Intel, Apple, unified-memory, and shared GPU allocations are currently unprobed. `nvidia-smi` may not report allocatable VRAM under container/virtualization restrictions.
- Explicit `recipe_feasibility: not_assessed`, `hardware_tier_certified: false` and `performance_benchmarked: false` remain true even if the probe reports 4, 6, 8 or 12 GiB VRAM.

The report does not enumerate local checkpoint files, hash model weights, inspect private prompts/images, or transmit machine inventory. It is a current-state diagnostic, not consent to inventory other folders.

## Next stages of issue #134

1. Add opt-in probing for other GPU backends (e.g. Windows DXGI, macOS Metal and Linux AMD/Intel), with tested provenance and explicit support boundaries.
2. Add versioned, explicitly **user-run** per-recipe benchmark receipts pinned to model/revision/checkpoint hash, graph/backend version, image size/steps, cold/warm measurements, peak host RAM/VRAM, p50/p95 latency and failure/OOM recovery.
3. Compare accepted outputs against human-reviewed references; never equate synthetic technical pass rates with real cutout quality, or infer supported hardware tiers without physical measurements.

See [architecture epic #132](https://github.com/interzettel/prehnite/issues/132), [hardware issue #134](https://github.com/interzettel/prehnite/issues/134), and [model/weight rights #40](https://github.com/interzettel/prehnite/issues/40).
