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
