# Experiment 002 — challenging cutout safety matrix

Issue [#29](https://github.com/interzettel/prehnite/issues/29), benchmark dependency [#32](https://github.com/interzettel/prehnite/issues/32), foundational merged [PR #119](https://github.com/interzettel/prehnite/pull/119).

## Offline reproduction

Install with `python -m pip install -e ".[dev]"` and run:

    python scripts/repair_challenge_benchmark.py --workspace ./prehnite-challenges

Open `prehnite-challenges/evidence/experiment-002/report.html` for a
self-contained side-by-side visual grid. The corresponding `report.json`
contains source, defective mask, benchmark reference, and final output SHA256;
expected and observed technical decision; reason code; alpha IoU, normalized
alpha MAE, and a normalized 3×3 morphological-edge MAE for eligible repairs.

**The benchmark-only reference mask is never supplied to the repair engine**.
Its purpose is to expose whether accepted alpha edits actually improve the
deliberately constructed synthetic reference. Report scores are objective
pixel metrics, not human perceptual ratings, calibrated VLM judgments or
ground truth derived from any real person's photograph.

## Challenge cases

20 independent deterministic fixtures include opaque products with alternate
backdrops, small exposure variation and thinner alpha leaks; smooth lighting
gradients, checkerboard and noisy backgrounds, frame-reaching shadows;
overlapping and separate subject concerns; cropped objects, alpha fringes too
wide for the authorized four-pixel band, a valid mask requiring no repair,
masked product detail matching the background color, incorrect interior
transparency, and objects with genuine through-holes. Portrait hair/fur,
declared glass, sheer fabric and unknown material remain review-only.

An accepted synthetic candidate must improve alpha IoU, absolute alpha error
and edge error compared with its *independent* reference. Refusals must leave
original source, mask and benchmark reference unchanged, record zero spend,
and refrain from fabricating an output. The entire matrix is replayed
to validate stable input/output receipts and one logical operation.

## Safety boundaries

The first algorithm is still limited to **opaque, locally isolated products
whose exact material is explicitly declared**. An absent or unqualified
material declaration causes review. Declaration is a *caller assertion*;
the algorithm cannot verify optical material properties by itself.

Opaque cleanup refuses internally disconnected transparency and masked pixels
that match the uniform backdrop far from the exterior fringe, because those
could be an incorrectly filled furniture opening or legitimate similarly
colored foreground. Such conservative abstentions may reject otherwise
repairable assets; the aim is to avoid ungrounded destructive automation.

This matrix **does not certify** robust natural-image matting or provide a
human-rated/rights-cleared real corpus. It cannot demonstrate that all harmful
repairs are caught: narrow, background-colored foreground strips and complex
occlusions remain difficult or inherently ambiguous without more evidence.
Do not grant S03/S05/S06/S07 roadmap credit on the basis of synthetic-only
test results, and do not connect the result to production `Engine.cutout`
without a new explicitly reviewed acceptance gate.

No hosted model requests, paid inference, keys, user uploads or restrictive
model weights are needed. CI publishes synthetic-only evidence artifacts.
