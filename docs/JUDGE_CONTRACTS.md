# Judge verdict contracts (offline safety layer)

Image-judging models are **optional**. The demo quality check only validates
pixels/dimensions and should never be described as aesthetic assessment.

## Typed response schema

A judgment must be one JSON object containing:

- `winner`: exactly one candidate ID, `tie`, or `neither`.
- `scores`: one finite JSON number in `[0, 1]` for *every* candidate, no
  missing or extra labels, no numeric strings or booleans.
- `reason`: a nonempty explanation (trimmed to 600 characters in storage).

A named winner must be within 0.02 of the top score; ties require a score
difference of at most 0.02, and `neither` requires every score below 0.5.
These numerical rules are consistency checks **not calibrated probabilities
or learned thresholds**. They can be refined through the future human
reference/calibration work in #28, provided any changes are documented.

## Two-rubric decision

For paired visual alternatives, the blind quality rubric views `A,B` while
the prompt-aware rubric views `B,A`. This inexpensive deliberate order swap
helps reveal obvious first-position favoritism, but **does not statistically
measure positional bias**: the rubrics differ, so their scores cannot be
treated as controlled repeated trials. Q03 remains unverified pending
controlled fixed-rubric A/B and B/A trials and human calibration.

Each submitted judge call is journaled separately. Existing paid-call failure
recovery remains fail-closed. Stored completed verdicts are type-checked
again on replay, without re-calling Anthropic. If a stored candidate-order
annotation contradicts the expected ordering, manual review is required.
Previously stored results without order annotations remain readable but
cannot substantiate an order-bias claim.

If the two rubrics disagree about the winner, or either abstains, no candidate
is automatically accepted. The engine stops that attempt rather than
purchasing another generated batch simply to arbitrate the disagreement.

## Still not demonstrated

No real paid judge calls, visual-quality calibration, reliable ranking
accuracy, or measured model positional bias have been completed in CI.
The mocked tests cover malformed scores, contradiction, cached replay,
first-position bias simulation and agreement across reversed display order.

The final published acceptance rubric is gated by issue #28 and separately
authorized actual-provider trials; model terms and per-request pricing must
be checked before any external image upload.
