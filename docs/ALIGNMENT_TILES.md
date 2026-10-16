# Alignment provenance and tiled 4K diagnostics — first #100 tranche

This document defines **v1 integer-pixel translation only**, the first bounded implementation of issue #100. It must NOT be described as an automatically computed affine transform, subject alignment, perceptual image quality, model evaluation, or a decoder-proof constant-memory raster processor. Work on arbitrary affine transforms and recorded interpolation is a separately reviewed extension.

## Why registration provenance matters

Previously, `prehnite compare` accepted a *human asserted same-grid* flag and computed pixel differences up to 4 MP. It could not describe a known shift or compare 4K images without excessive full-image working arrays. This new command requires a saved **operator-authored JSON transform**, bound to the actual SHA256 checksums of both inspected files, and only compares their explicitly overlapping source coordinates.

Coordinate definition (raw unrotated encoded pixels, EXIF Orientation 1):

`candidate[x + dx_pixels, y + dy_pixels] ↔ reference[x, y]`

Only exact integer translation is supported. No auto-registration, rotations, scaling, shear, crops-to-fit, subpixel shifts, nearest-neighbor or bilinear interpolation. Pixel margins outside the valid overlap are **not** scored as changes. The change fraction denominator is **overlap pixels only**; reference and candidate overlap fractions are recorded independently.

## Example owner-authored alignment JSON

```json
{
  "schema_version": 1,
  "kind": "integer_translation",
  "dx_pixels": 3,
  "dy_pixels": -2,
  "reference_sha256": "<64 lowercase hex of historical original>",
  "candidate_sha256": "<64 lowercase hex of selected accepted image>",
  "coordinate_frame": "raw_unrotated_encoded_pixels_exif_orientation_1",
  "interpolation": "none",
  "attestation": "operator_asserted_not_inferred"
}
```

Replace the hash placeholders with actual SHA256 values from the batch evidence. Do not paste this example unchanged into a workflow. The reference and candidate hash values are exactly checked before any pixels are compared; arbitrary extra JSON fields, ambiguous types including booleans, shifts beyond ±8192 pixels, absent hashes, unsupported versions or implicit transforms are refused.

Example for a source-backed slot:

```bash
prehnite compare-tiles my-batch --asset asset-014 \
  --workspace workspace --inputs /approved/original-root \
  --alignment recorded-translation.json
```

For a named accepted cutout, use `--cutout subject` instead of `--inputs`. A corresponding alignment record must use the *selected base* as reference and the cutout as candidate. No new model requests, cloud uploads, provider billing or default ZIP changes occur.

## Metrics and privacy

Valid overlap is scanned with 512×128-pixel tiles, accumulating `changed_pixel_count`, `changed_pixel_fraction_of_overlap`, a normalized **encoded-channel** RGB delta over both black/white RGBA composites, and reference/candidate partial/fully transparent fractions. As in #98, hidden RGB under zero alpha is not counted as a visible difference. Recorded transform parameters, exact source hashes, transform record SHA256, both dimensions, overlap size/fractions, frame semantics, and receipt for the heatmap are kept in a **private versioned JSON**.

A streamed RGBA PNG stores the delta intensity as red and uses alpha=0 for **non-overlap**. The PNG is generated strip-by-strip; no full-RGBA difference canvas is built in Python. The JSON is written last as a publication marker. Both live under `reviews/` and never enter the ordinary accepted-output ZIP.

**Important memory limitation:** Pillow may decode and hold the full original source frame in its internal decoder when random-access crops are requested. We bound each input image to **24 million pixels** and our *comparison tile/PNG output working buffers* to 512×128 chunks plus a reference-width 128-row strip, but do not claim constant total decoder memory. This is not an out-of-core TIFF/EXR/image-container decoder. The predecessor's 4 MP cap remains unchanged for `prehnite compare`.

**No aesthetic score:** these metrics are encoded pixel observations only, with `human_visual_quality_score: null`, `registration: operator_attested_not_computed`, and `inference_cost_usd: 0`. The source alignment record is not evidence that a human or model independently validated correspondence. Require separately reviewed photographs and perceptual studies before using differences for acceptance decisions.

## Refusal policy

Comparison refuses tampered accepted files, source hash mismatch, paths escaping the authorized original root, selected outputs not listed in the manifest, unsupported ICC differences, any non-1 EXIF orientation, unsupported pixel modes, images over 24 MP, non-integer transform offsets, or overlap under 10% of the reference frame. No automatic color-profile conversion, alignment correction, or upscaling is attempted.

The red heatmap is a **diagnostic data color**, not the project’s decorative Riso coral token; the rest of any future HTML interface should follow [the owner's forest/coral palette](BRAND_PALETTE.md).

## Reproducible synthetic 4K example

Run `python scripts/synthetic_alignment_demo.py --output alignment-4k-synthetic`. The script creates a **3840×2160** owner-palette-inspired *synthetic* source and shifted candidate with exactly one visible changed pixel. It writes the fixed attested transform, versioned metrics and RGBA overlap-masked delta PNG, plus SHA256 receipts. The GitHub Actions Windows/Ubuntu synthetic benchmark uploads these files under `alignment-4k-synthetic/` (14-day artifact retention). Never upload real owner batch imagery or transform provenance as public artifacts.

## Evidence and future increments

Run `python -m pytest -q tests/test_tiled_alignment.py`. The fixtures cover correct and wrong translation, changed-pixel and alpha semantics, transform fingerprints, 4K (3840×2160) lossless identity, EXIF/ICC refusal, no-overlap, default ZIP parity and explicit CLI. CI must also pass all regular offline 90-slot pause/crash/recovery, PyArrow optional, MCP lifecycle and clean-install checks on Windows/Ubuntu.

Follow-up work under #100: owner-attested *arbitrary affine* matrices with explicit frame bounds and a stable interpolation policy; reusable verified alignment receipts; further memory-mapped decoders for truly strict overall RAM ceilings; controlled alpha/color science benchmarks; and an interactive inspection overlay. Treat these as pending research, not features of this first tranche.
