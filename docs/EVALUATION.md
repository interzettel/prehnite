# Evaluation policy

The production goal is accepted useful assets per unit cost, **subject to** visual and technical constraints. This is not an objective image benchmark and does not claim to measure human preference without humans.

## Image judgments
1. Validate format, decodability, orientation, expected target dimensions.
2. Blind A/B review of realism, composition, defects and oversharpening.
3. Prompt-aware A/B review using the exact original prompt to catch wrong objects and missing constraints.
4. Gate each candidate on the weaker of its two 0..1 scores. Select the highest passing candidate, or create a new generation attempt with a different seed within the retry limit.
5. Report judgments, reasons, version and input/output token usage.

A model's score is not calibrated: changing judges or prompt rubrics changes threshold semantics. Evaluate quality at normal viewing size plus native-resolution crops in a future release; current Haiku previews are downsized and cannot assess all 4K detail.

## Cutout judgments
Validate that target name is supplied, mask is non-empty and not entirely opaque, coverage is above the configured minimum, transparent PNG is decodable. Optionally compare the original with a cutout on a contrasting background using a visual judge. Keep crop-aligned masks and immutable originals.

A cutout score is an LLM preference, **not** a pixel-accurate IoU measured against ground truth. Binary foreground and alpha matting differ; thin objects, fur, glass and occlusion remain difficult. Failure of a cutout does not cause regeneration of an accepted source image.

## Budget and failure
Before a paid operation, reserve its configured upper-bound estimate. Record billed usage only if the provider actually returns it. Unknown exact prices must not be presented as actual charges. A paid task with uncertain submission must halt for reconciliation. Neither judges nor repair loops can spend indefinitely.

## Calibration path
Later: HPS, Q-ReAlign, VQAScore, masked-edge/crop judges, judge position-order checks, content-addressed caching and per-category policies. The v0.1 registry lists only implemented adapters; a model named in research is not evidence of a working adapter.
