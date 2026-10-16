# V2 operator-authored affine registration contract — validation only

**Issue:** [#105](https://github.com/interzettel/prehnite/issues/105), child of [#100](https://github.com/interzettel/prehnite/issues/100).

This new validation stage is **not** an image warp, an automatic alignment predictor, a quality score, or a pixel-difference computation. It establishes a strict, versioned, SHA256-bound contract that a future approved resampler can execute without inventing correspondence.

## Pixel-center coordinates and direction

All coordinates refer to **raw encoded image pixels after requiring EXIF orientation 1**. The origin is the *center of the upper-left pixel* `(0, 0)`; x increases rightward, y downward. A forward affine mapping sends each *reference pixel center* to candidate coordinates:

```text
candidate_x = a * reference_x + b * reference_y + tx
candidate_y = c * reference_x + d * reference_y + ty
```

The inverse candidate-to-reference transform must be provided by the owner and numerically agree with the calculated inverse. We do not infer, estimate, or silently fix either transform.

Both reference and candidate image SHA256 values must match the locally **verified** selected output and the historical original source, or the named accepted cutout. The original path comes only from the explicit allowlisted `--inputs` root. No request IDs, arbitrary file paths, prompts, or operation keys enter the safe validation response.

## Operator-authored JSON example

The following illustrates a 3-pixel rightward, 2-pixel upward **translation**. This affine contract is deliberately distinct from the already shipped v1 integer-translation contract.

```json
{
  "schema_version": 2,
  "kind": "affine_2d",
  "reference_sha256": "<64 lower-case hex for reference>",
  "candidate_sha256": "<64 lower-case hex for candidate>",
  "reference_to_candidate": [[1, 0, 3], [0, 1, -2]],
  "candidate_to_reference": [[1, 0, -3], [0, 1, 2]],
  "coordinate_frame": "raw_unrotated_pixel_centers_origin_zero_exif_orientation_1",
  "interpolation": "bilinear_premultiplied_rgba",
  "boundary": "only_full_source_sampling_footprint",
  "color_profile_policy": "identical_icc_bytes_or_both_untagged_encoded_channels",
  "alpha_policy": "premultiplied_rgba",
  "attestation": "operator_asserted_not_inferred"
}
```

Replace hash placeholders with the true digest receipts and verify coordinates independently. This example is **not** a self-executing command and does not mean registration was objectively verified.

## Local validation command

```bash
prehnite validate-affine my-batch --asset asset-014 \
  --workspace workspace \
  --inputs /approved/original-root \
  --alignment alignment-v2.json
```

For cutouts use `--cutout subject` instead of `--inputs`. The command prints versioned JSON to stdout. It does **not** modify the image, write heatmaps or create artifacts, spend inference credits, or authorize upload.

Checks include:

- Exact v2 schema and known keys, serialized input ≤4 KiB, finite numeric coefficients with no booleans or nonnumeric strings.
- Operator-provided inverse agrees within 1e-8 relative / 1e-7 absolute tolerance; non-invertible, near-singular and numerically ill-conditioned matrices are rejected.
- Bounded coefficients (magnitude ≤8), bounded translations (≤8192 pixels) and bounded input frame dimensions/area (≤24 MP).
- EXIF Orientation 1, RGB/RGBA pixel formats, **identical ICC profile bytes or both untagged**. No automatic linearization/color matching or EXIF rotation.
- Transformed candidate bilinear-sampling domain intersected geometrically with reference sampling-center domain. Coverage below 10% is refused, rather than misreported as failure or blackened border pixels.
- The public response describes the continuous *center-domain polygon area* and fraction, **not discrete sample counts**, interpolation results, image quality, confidence of true registration, or meaningful visual differences.

### Resampling and alpha semantics reserved for executor

The contract fixes `bilinear_premultiplied_rgba` and the exclusion of invalid sampling footprints, to prevent future accidental changes between workers/platforms. **This stage validates those declarations but does not execute them.** The implementing executor must specify roundoff, premultiplication/color-profile policy, integer pixel-center masks, backend portability, and overlap denominator, then verify the output against fixtures and explicitly record its version.

Our existing no-resampling v1 CLI remains: `prehnite compare-tiles ... --alignment v1-integer-translation.json`. It supports exact integer translations on 4K frames and does not accept v2 transforms.

## Privacy, reproducibility and limitations

Do not confuse a syntactically valid matrix with a registration confirmed by a human or a computer-vision algorithm. The JSON marks `operator_attestation_not_verified: true`, `interpolation_executed: false`, `valid_discrete_sample_count: null`, `pixel_difference_metrics: null`, and `human_visual_quality_score: null`. It is a feasibility/provenance check, not any kind of aesthetic validation.

The polygon is a conservative **continuous-area proxy for possible bilinear samples**, not an exact count of aligned pixel centers or guaranteed image correspondence. Rotations, crops and scale changes can pass *contract validation* even when their semantic alignment is wrong; later human or independently tested computer-vision evaluation remains necessary.

Tests cover identities, translations, 90-degree rotations, scaling, crop overlap, non-finite values, boolean smuggling, singular/near-singular matrices, inverse mismatches, 24MP boundary, byte limits, historical hash tampering, ICC inconsistency, source symlink escape, and CLI refusal. Windows/Ubuntu CI must also pass the ordinary local-first synthetic 90-slot recovery and optional Parquet checks.

**Next separate increment:** an actual tiled v2 affine executor and human-reviewable overlay after correctness and memory tests. No paid inference, new mandatory dependencies, release, or unit completion claimed here.
