# S03-A04 — opt-in trusted soft-alpha evidence (experimental)

This is a **CPU-only, synthetic-first engineering increment**, not validated
general-photo matting, real glass reconstruction or visual acceptance.
The original S03-A04 criterion is "Hair, mesh and glass retained with measured
alpha and no halo artifacts"; this PR provides a narrow, measurable pathway
when an **independent soft-alpha matte and uncomposited straight foreground RGB**
have already been supplied. It **cannot** reconstruct hair, mesh or optical
glass alpha from a single binary SAM mask.

## Contract: two candidate modes

`cutout-qa` keeps its existing default `binary_feather` behavior unchanged.
To preserve supplied fractional alpha without re-binarizing/blur, the operator
can explicitly select a candidate with:

```json
{
  "id": "trusted-soft",
  "sigma_px": 0.65,
  "transition_mode": "preserve_trusted_soft",
  "soft_alpha_sha256": "<64-character SHA256 of exact mask PNG bytes>",
  "foreground_rgb_origin": "straight_foreground_rgb"
}
```

- The `mask` argument must be a same-size, unrotated **8-bit grayscale PNG
  (`L`)** with a matching SHA256. This is a *provenance declaration*, not
  proof the matte is physically correct. RGB/grayscale-converted masks,
  binary-only masks without any fractional transmission and resampling are
  refused for the trusted mode.
- The input `source` image, bound by the recipe's existing SHA256, must contain
  **unassociated straight foreground RGB** at partly transparent pixels. A
  normal photograph already composited against an unknown background is **not
  suitable**: preserving its pixels can retain backdrop color halos.
- The candidate keeps the input alpha bytes exactly and does not expand,
  decontaminate, unpremultiply or otherwise invent foreground RGB. Supplying
  premultiplied RGB as straight RGB can produce dark fringes; operator must
  obtain the right representation from its authorized matte pipeline.
- The optional uniform-background `color_spill` operation cannot be combined
  with this mode. It belongs to S03-A03 and has distinct assumptions.
- The original hard-component/holes/coverage safeguards still evaluate
  candidates. For this specific trusted-soft mode, coverage drift is measured
  against the original fractional alpha (not a thresholded binary mask);
  binary-feather candidates retain their existing hard-mask coverage baseline.
  The normal `qa.max_partial_alpha_fraction` default may need an
  **explicit recipe value** appropriate to a validated, highly translucent
  asset. Never loosen the value globally or silently.
- `candidate.status == passed` is only technical consistency, while
  `review_status == review_pending`, visual acceptance `not_recorded`,
  and owner acceptance `not_recorded`. The RGB origin is explicitly marked
  **unverified** even after input hashes match.
- Original source and accepted artifacts are not overwritten; candidate
  output still requires a new/empty destination.

## Independent oracle evidence

`prehnite.matte_evidence.evaluate_reference_matte(candidate, reference)`
compares two same-size **straight RGBA** rasters with oracle fractional alpha:

- raw alpha MAE on 0–255 scale across the full image;
- alpha MAE on the oracle's fractional-transmission pixels;
- RGB MAE of transition-band composites on **black, white and checkerboard**
  underlays, plus their maximum.

The transition band includes both reference/candidate semitransparency and its
one-pixel neighborhood. A non-fractional reference is refused, rather than
inventing a zero-error quality score. The caller must independently establish
the reference and permission to use it. `0` means pixel equality to that
reference, **not** professional quality or calibrated perceptual acceptance.

Offline tests construct independent alpha oracles with thin hair-like strands,
open mesh cells, and partially transmissive glass-like areas. They prove exact
alpha pass-through when input is already truthful, and that deliberately lost
strands or color-polluted edge pixels register nonzero errors. A glass-like
alpha panel is a compositing proxy, **not a physical glass/refraction/lighting
model**; real transparent material appearance needs separately justified
algorithms and human review.

## Completion boundary

No GPU/model execution, provider credentials, spending, source uploads or
private image evidence were used. The original S03-A04, S03-A05 and S03 parent
should remain open until independent review assesses whether the original
acceptance scope is met, and rights-cleared real-material reference cohorts
and human review exist for broader claims. This increment does not modify
either frozen progress ledger or any release gate.
