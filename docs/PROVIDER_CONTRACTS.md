# fal adapter — offline provider conformance

This page records the **input/output shapes tested using a local fake fal client**.
It is not a certification that the hosted endpoints work with our code, nor a
substitute for checking live prices before spending money.

## Supported generation request schemas

| Endpoint | Size input | Seed | Output key | Evidence |
|---|---|---|---|---|
| blackforestlabs/flux-3/klein/text-to-image | image_size width/height, up to 4096 per edge | Explicit seed | images list | [fal Klein API](https://fal.ai/models/blackforestlabs/flux-3/klein/text-to-image) and corresponding Klein edit API schema |
| blackforestlabs/flux-3/text-to-image | aspect_ratio + resolution 2k/4k | Not advertised in documented input schema; omitted | images list | [fal FLUX.3 Image API](https://fal.ai/models/blackforestlabs/flux-3/text-to-image/api) |
| fal-ai/esrgan | image_url + scale=2 + named model | Not applicable | image object | [fal ESRGAN API](https://fal.ai/models/fal-ai/esrgan/api) |

The Klein image_size defaults use the following 2K long-edge dimensions
(width x height), doubled for the 4K variant:

- 9:16: 1152 x 2048
- 3:4: 1536 x 2048
- 1:1: 2048 x 2048
- 4:3: 2048 x 1536
- 16:9: 2048 x 1152

**Do not confuse a request size with an observed output resolution.** The
actual returned pixels must be inspected; our local fixture is only 192x256.
Prehnite's output size is independently enforced by the image pipeline.
The 2K/4K tier terminology is specific to each model API, and cannot be
blindly reused across providers.

## Queue and replay

The first submit produces an opaque request ID, immediately persisted by the
Engine callback. A restarted task **gets that same request** instead of
submitting again. A resumed upscale/segmentation task **does not re-upload**
its private source image. Paid calls with a lost request ID remain ambiguous
and require human/provider reconciliation. A missing ID, unexpected response,
empty image list, invalid URL or malformed image fails closed.

The local tests use a fake fal_client module and deterministic PNG fixtures.
They assert the outbound arguments, response parsing, request IDs, output
host allowlist and no repeat of source uploads. CI has **zero network
inference** and does not use a valid FAL_KEY.

## Open limitations

- Model endpoint schema drift and exact Klein size behavior need a
  separately approved live call (#7).
- Provider bills/quote reconciliation is a separate task (#17).
- SAM segmentation payload/output formats have their own ticket (#20).
- Other fal model IDs are rejected rather than guessed; model-agnostic
  capability negotiation is the next task (#21).
- The generic FLUX.3 Image API does not document a controllable seed here.
  Do not promise deterministic replay based solely on the requested seed.

## SAM 3.1 segmentation contract (offline)

The documented fal image endpoint is
[fal-ai/sam-3-1/image](https://fal.ai/models/fal-ai/sam-3-1/image/api).
Do not substitute an undocumented alias such as `fal-ai/sam3.1`.
The adapter requests a single text-prompted PNG mask, with `apply_mask=false`,
`return_multiple_masks=false` and `include_scores=true`. The response
schema documents a list of masks and optional metadata/scores/boxes.

Prehnite **rejects ambiguous multiple masks** instead of silently taking the
first. It validates that the source and mask have the same displayed aspect
ratio (the mask may have proportionally different pixel dimensions), refuses
empty or full-frame masks, and accepts either grayscale L/1, equal-channel
grayscale RGB, or a meaningful RGBA alpha. Colorized RGB masks are rejected,
not interpreted as luminance. EXIF source orientation is applied before
comparing mask geometry. An unknown coordinate transform or padding strategy
is not guessed, since stretching a square mask onto a portrait can misplace
the subject.

This provides deterministic technical *mask-format safety*, **not semantic
segmentation accuracy**. SAM could still select the wrong person. Production
proof requires source/ground-truth evaluation (#32) and an explicitly
authorized real-provider pilot (#7). The tests use synthetic input masks with
no API requests or invoices.

## Provider capability registry and preflight (offline)

`prehnite models` reports adapter contracts in
[`src/prehnite/registry.py`](../src/prehnite/registry.py): provider,
supported operations, prompt/image inputs, intermediate output formats,
resolution tiers, aspect ratios, maximum declared dimensions where known,
source-upload behavior, accepted endpoint options, external schema links,
license warnings, and **whether the adapter has offline tests**.

As of 2026-10-16, the paid fal adapters allowed by Prehnite are:
- `blackforestlabs/flux-3/klein/text-to-image` — prompt; 2k/4k; custom dimensions
  for the five Prehnite aspect ratios; maximum 4096 pixels per side;
  optional `enable_prompt_expansion`. Does not imply 4K photorealistic
  quality was actually measured.
- `blackforestlabs/flux-3/text-to-image` — prompt; 2k/4k; model-native
  aspect_ratio + resolution, with no seed support claimed.
- `fal-ai/esrgan` — image upload; `scale=2`, documented RealESRGAN model
  variants, intermediate PNG; other scaling factors are unsupported in this
  adapter, **even though fal's API supports more options**.
- `fal-ai/sam-3-1/image` — image + text upload; exactly one PNG mask.
- `fal-ai/birefnet/v2` is visible as a **future candidate**, NOT an
  installed/run-capable matting adapter.

All paid model entries require **user-supplied price estimates**. The
catalogue deliberately provides *no hard-coded current USD price*, no
invoice assertions, and no implication that advertised model/license
terms have been independently cleared. fal's documented API input schemas
are linked per model; check live pricing and your model/provider rights
before approving the first paid test. Third-party weights are not covered
by Prehnite's MIT code license.

Validation runs in `validate_job` before the engine creates a journal or
sends a request. It checks only stages that the manifest actually needs;
an existing-image-only batch does not have to activate an unused generator.
Unknown paid model names, mismatched operations (for example using an
upscaler as a generator), unsupported tiers/ratios, undeclared options,
4x ESRGAN requests, cloud upload without permission, or missing user
cost estimates are rejected with an actionable error.

ComfyUI remains intentionally user-extensible: the `model` field is a
local label, not a marketplace ID; the caller supplies an API-format
`options.workflow` JSON file and any model weights under their separate
terms. Local workflows and the Anthropic judge's user-specified model are
**not** a promise of verified runtime compatibility. The CLI lists these
as unverified, rather than inventing a model allowlist.

This catalogue is versioned **adapter contract evidence**, not a live
provider inventory, price API or automatic licensing approval.
