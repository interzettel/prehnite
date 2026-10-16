# Owner-provided apparel pilot: private technical evaluation

Related work: [#32](https://github.com/interzettel/prehnite/issues/32),
merged source-intake PR #122, and synthetic challenge PR #120.

## What was actually tested

The owner supplied an **AI-generated photo ZIP** for Prehnite's private
evaluation. This archive is distinct from the earlier 23-WebP R2 subset and
must **not** be checked against those WebP hashes.

- **84 JPEG sources**, all valid RGB at **1086 × 1448**, with complete decode
- **50 product front views**; **34 care-label closeups**
- **Zero independently reviewed foreground alpha reference masks**
- 50 **unreviewed** OpenCV GrabCut rectangle-baseline candidate masks, at
  approximately 360 × 480 pixels, tested offline and without paid inference
- **Zero** ground-truth IoU/alpha MAE results; **zero** automatic approvals

This is a **real input archive test**, not a photographic matting quality
certification. The pictures are AI-generated photos supplied by the owner.
The label photos belong to a distinct closeup/OCR cohort and are not
interchangeable with product front-cutout tests.

### Observations from the private side-by-side review

Flat-laid garments often produced plausible coarse shapes. Visible failure
modes include stray background/cloth patches, ambiguity on white fabric,
hangers/straps being retained as foreground, and confused separation on
footwear against textured backgrounds. Automated geometry-only checks can
miss these perceptual errors. Do not report a healthy mask from area or
component count alone.

The archive contains no valid ground-truth alpha; a predicted mask must
never be recycled as its own gold reference.

## Repeat offline with zero subscription or inference costs

Inspect **only**; requires the existing Pillow dependency:

```bash
python scripts/inspect_apparel_pilot.py \
  --zip "/private/owner-supplied-apparel.zip" \
  --output "/private/pilot-inventory"
```

Optional local OpenCV/NumPy **exploratory**, one-off baseline:

```bash
python -m pip install opencv-python-headless numpy
python scripts/inspect_apparel_pilot.py \
  --zip "/private/owner-supplied-apparel.zip" \
  --output "/private/pilot-unreviewed" \
  --unreviewed-grabcut
```

The optional packages are not part of the mandatory Prehnite installation;
the second command's output is a NEW empty private directory. The baseline
uses 4 GrabCut iterations at a downscaled image size, not an ML-backed
high-fidelity cutout and not a reference-alpha evaluator. It always leaves
`human_accepted=0` and `actual_segmentation_iou=null`.

The tool never extracts the source ZIP to disk or uploads input pixels, and
limits the number/expanded size of members to avoid unsafe ZIP files.
It checks JPEG encoding and complete decode before any preview operation.

## Next genuine evidence gate

1. Human-review the visible candidates to triage representative good,
   ambiguous and failed apparel cutouts; retain original and candidate pairs.
2. Create **independent** ground-truth alpha masks for a stratified sample,
   especially white fabric, hanger/strap ambiguity, shoes and textured
   backgrounds. Confirm rights to use the photographs for testing; owner
   authorization does not automatically grant public redistribution.
3. Only then use the merged `scripts/evaluate_real_cutouts.py` to measure
   IoU, continuous alpha MAE and boundary error by category.
4. Compare calibrated models or repair policies with the trivial baseline,
   and never promote a synthetic reference or unchecked OpenCV output as
   production quality.

Do not commit raw images, private mask candidates, media bundles or raw user
hash manifests to the public repository. This work **does not** complete
the S03/S05/S06/S07 roadmap units.
