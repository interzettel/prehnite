# Verified pixel-grid diagnostics — v1

**Issue:** [#98](https://github.com/interzettel/prehnite/issues/98) · **Parent:** [#6](https://github.com/interzettel/prehnite/issues/6).

This optional, offline command computes **technical differences in explicitly co-registered pixels**. It is deliberately *not* automatic image registration, semantic comparison, segmentation accuracy, provider latency measurement, aesthetic judgment, or a human-calibrated quality grade.

## Prerequisites: explicit coordinate-frame attestation

For an existing-image batch, compare the owner-supplied original against its accepted base:

```bash
prehnite compare my-batch --asset asset-014 --workspace workspace \
  --inputs /path/to/approved-originals --assume-same-grid
```

For a named accepted cutout, compare the accepted base and the named cutout in their intended shared pixel frame:

```bash
prehnite compare my-batch --asset asset-014 --workspace workspace \
  --cutout subject --assume-same-grid
```

Both calls are **read-only on accepted assets** and publish private evidence under `workspace/batches/my-batch/reviews/`. They never dispatch provider calls or modify the default export ZIP. The explicit `--assume-same-grid` is an operator attestation, **not a computed alignment transform**. It is required even if images have identical dimensions. Without it, the command refuses comparison. An original is eligible only if its *historical*, stored input SHA256 matches the owner-selected allowed input root.

The tool does not silently crop, stretch, rotate, warp, register, interpolate, denoise, decode another source instead of the recorded one, correct orientation, or convert ICC profiles. When unsupported it returns a machine-readable `not_comparable` record (to stdout only), with `metrics: null` and one of:

- `geometry_mismatch` — different width or height (including scale mismatch)
- `orientation_unresolved` — non-default EXIF orientation present
- `color_profile_mismatch` — different embedded ICC-profile bytes (including tagged vs untagged)
- `pixel_encoding_unsupported` — not RGB/RGBA
- `metric_pixel_budget_exceeded` — either frame above **4 million pixels** for this initial comparator

Unverified, malformed, missing, escaped or externally symlinked images are rejected *before* metrics or evidence generation. A same-sized translated image **cannot be automatically detected as unregistered**; the human/agent providing the attestation remains responsible. Without registration evidence, never treat numerical differences as degradation. This v1 implementation records `geometric_transform: null` rather than inventing a matrix.

## What the metric means

For explicitly comparable images, the tool composes RGB or RGBA over **both black and white backgrounds**, compares encoded channel values, and records these deterministic *observations*:

| Field | Meaning |
|---|---|
| `pixel_count` | Total identical-grid sample positions |
| `changed_pixel_count` / `changed_pixel_fraction` | Number/proportion of positions where **any** black- or white-composited channel differs |
| `mean_composited_channel_delta_0_1` | Mean absolute encoded RGB-channel difference over both backgrounds, normalized 0–1 |
| `reference_partial_alpha_fraction` / `candidate_partial_alpha_fraction` | Fraction of pixels whose alpha is strictly between 0 and 255 |
| `reference_transparent_fraction` / `candidate_transparent_fraction` | Fully transparent fraction |

Compositing on contrasting backgrounds avoids treating hidden RGB values under fully transparent pixels as visible differences. A red **difference heatmap** is generated at native pixel coordinates, with intensity from the strongest encoded-channel discrepancy. This is **not** an edge-alignment confidence score, perceptual distance, colorimetric ΔE, or a pixel-registered guarantee.

For both *untagged* images we compare encoded channel values without assuming a provable source color space. If ICC profiles are present, they must match byte-for-byte; even when matched we do **not** claim perceptually linear/channel-calibrated differences. No automatic ICC conversion occurs.

## Artifacts and security

Upon a comparable pair only, the private `reviews/` folder receives `<slot>-difference-original.*` or `<slot>-difference-cutout.*`:

- `.png`: red native-resolution delta heatmap
- `.html`: self-contained, CSP-restricted original/reference, candidate, heatmap comparison, with CSS-only Fit and Native 1:1 toggles
- `.json`: `schema_version: 1`, purpose, hash receipts, geometry, reason/status, metrics, no provider IDs or human score; written **last** as the publication marker

The image bytes in HTML are **private** and must not be publicly uploaded from real batches. The report JSON and PNG/HTML are excluded from normal accepted-output ZIPs and default dashboards. The comparator has a 4MP per-image working-frame cap (smaller than the **24MP read-only native inspector**) and **64MiB combined embedded-byte limit** for a single comparison. It is not a tiled 4K image comparator yet.

Privacy-aware field names in the JSON avoid raw prompts, original source paths, local operation keys, provider request IDs or free-form judge/error text. SHA256 digests are included to bind comparison evidence to the bytes; the JSON does not prove that a user assertion about alignment was objectively correct.

## Evidence and next gates

`python -m pytest -q tests/test_pixel_comparison.py` covers identical pixels, a single-pixel edit, same-sized unregistered shifts requiring explicit attestation, geometry mismatch, EXIF rotation, ICC mismatch, RGBA fringe/hidden RGB, integrity tampering, external symlink, 4MP boundary, CLI opt-in and default ZIP stability.

GitHub Actions must also pass the ordinary Windows and Ubuntu no-cost 90-slot pause/crash/resume, optional Parquet, MCP lifecycle, and clean-install jobs. No real GPU, paid inference, image quality calibration, dynamic geometric registration, color matching or model scoring is claimed.

Future separately-scoped work may add **explicit recorded alignment transforms** (with inverse and provenance), memory-bounded tiled 4K diagnostics, standardized color transforms, and owner-reviewed calibration. They must not retroactively turn current encoded-channel metrics into quality ratings.
