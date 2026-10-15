# Architecture & execution contracts

Prehnite is a Python service/CLI, not a ComfyUI workflow or an image generator in its own right.

## Layers
1. Strict Pydantic manifest: asset IDs, source or prompt, aspect ratio, exact output size and named cutout filenames.
2. Profile: ordered generation variants, selected providers/models/options, thresholds, permitted uploads, bounded retries, cost estimates.
3. Provider adapters: normalized generate/upscale/segment outputs; hosted requests persist request IDs before waiting.
4. Sequential production engine: variants -> image technical checks -> quality judgment -> winner -> named cutouts -> quality checks -> archive.
5. SQLite journal: task status, request IDs, paths, model, reserved spending, token usage, stage metadata and batch fingerprints.
6. Reporting: JSON, CSV, standalone HTML, accepted-asset ZIP.
7. Agent access: stdio MCP, with long jobs executed in a detached subprocess.

## Current contracts (v0.1)
- Generate: prompt, aspect ratio, resolution tier, seed -> image artifact.
- Upscale: input image -> enhanced output artifact.
- Segment: image, named target -> mask image. Actual alpha is applied locally.
- Judge: two image candidates -> explicit normalized scores and a winner/tie. Blind and prompt-aware reviews are distinct, fresh API calls.
- Accepted assets always have safe unique output paths.
- Unverified assets require explicit policy opt-in. A basic technical check does not constitute image-quality validation.

## State / recovery
Tasks have states running, submitting, submitted, completed, failed or uncertain. Successful stages are reused by task key and immutable configuration fingerprint. A fal request ID is recorded immediately after submission; a resumed worker can reconnect to the same request. An exception during a paid submission before its ID is recorded is **uncertain**, not safely retryable. Inspect provider billing before manual resolution.

A config change cannot reuse the same batch ID. Start a new batch to guarantee traceable comparisons.

## Choice and rejection
The pairwise Haiku judge runs a blind visual review and an exact-prompt review in independent conversations. Candidate quality is the minimum of the two scores. The highest eligible score must exceed the configured threshold. Scores are subjective rubrics, not probabilities. With no visual judge, policy is either reject or explicitly accept as unverified. Strict unattended production should use reject.

Generation quality failure changes the attempt seed, creating a genuinely new candidate. Cutout failures attempt a different local edge treatment using the same previously generated mask; this cannot fix a completely wrong object selection, which remains rejected. No unlimited retry loop.

## Deferred integrations
Hardware-tested ComfyUI inference and model lifecycle (generic API adapter exists), non-demo local inference, local typed quality/preference judges, multiple cutout segmentation backends, robust visual region-level evaluation, a browser dashboard, parquet reports, cancellation and fine-grained progress APIs. See ROADMAP.
