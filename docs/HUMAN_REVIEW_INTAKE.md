# Human Review Studio → validated Prehnite feedback intake

Tracking: [#28](https://github.com/interzettel/prehnite/issues/28), [#32](https://github.com/interzettel/prehnite/issues/32), [#9](https://github.com/interzettel/prehnite/issues/9).

The owner uses a **separate, self-contained, private HTML Review Studio**
to inspect 12 WEARHOUSE apparel cutout candidates. The HTML app itself
remains private and works offline. This PR builds the **read-only consumer**
so that a completed review becomes structured, reproducible engineering
feedback instead of another informal image-by-image conversation.

## Run it when the owner finishes reviewing

The review app supports two ways to save:
- **Export results ZIP** (works across browsers)
- **Choose save folder** in Chrome/Edge (autosaves JSON, text and alpha PNGs)

Either input is accepted by the same command:

    python scripts/inspect_human_review.py \
      --input "/private/Review Studio results.zip" \
      --output "/private/prehnite-review-summary"

Or point \`--input\` at the local autosave folder instead of a ZIP.
\`--output\` must be a new, empty directory outside the input folder.
Pillow is already a required Prehnite dependency. No OpenCV, inference
models, network access, tokens, paid platforms or services are necessary.

Output (private):
- \`validated_review.json\`: redacted counts, explicit approval/rejection
  status, mask SHA256, foreground coverage, review issue tags and repair IDs
- \`triage.txt\`: concise defect counts and the **needs-work** queue

These are separate from the original export. The importer never writes
inside the original ZIP/autosave folder and never extracts mask images.
Review notes, reviewer initials and raw photo bytes are not copied to the
generated summary. Do not publish either the exported ZIP or reports
without separate permission: asset IDs and hashes can still be linkable.

## Integrity contract

Reject ZIP traversal, duplicate/unexpected members, symbolic links, oversized
files, JSON count forgery, unsupported schema, mismatching per-image review
state, invalid ratings/issue tags, wrongly claimed independent gold labels,
missing or extraneous alpha PNGs, corrupt PNGs, and wrong mask dimensions.
Approved masks must not be entirely transparent or entirely opaque.

The Review Studio's 12 objects carry claimed original image/mask SHA256
values; this importer validates that they are well-formed and preserves
the review report's own SHA256 receipt. **It cannot independently confirm
the source hashes without access to the private source images.** The
reviewer's accepted, corrected, or skipped alpha PNG remains a human
response to an existing GrabCut candidate: **not an independently annotated
reference matte**.

The summary therefore always distinguishes:
- \`visually_approved\`: accepted by a human in this review session
- \`needs_work\`: reviewer flagged actionable failures
- \`independent_ground_truth_count = 0\`: no separately created reference
- \`alpha_iou_measured = false\`: no fabricated mask-accuracy score

Simple mask coverage only detects gross geometry; it **does not** certify
the shape, strand fidelity or real cutout correctness.

## Next engineering loop

After the user's review, import their ZIP **privately**, inspect the
\`needs_work\` queue, group failure tags and prioritize cases covering
white-on-white products, hangers, handles, leg gaps and footwear.
Escalate contested cases to independent reference-alpha annotation and
a second human review. Only then compare candidate and reference with
\`scripts/evaluate_real_cutouts.py\` and propose bounded repair changes.

CI uses *synthetic review data only*. No private WEARHOUSE originals,
submitted reviews, generated alpha PNGs or reviewer notes are committed
to the public repository. This is evidence intake, not S03/S05/S06/S07
milestone completion; the roadmap ledger is unchanged.
