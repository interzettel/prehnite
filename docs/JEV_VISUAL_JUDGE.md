# Experimental Jev visual judge — Stage A mock / offline safety contract

**Tracking:** [#107](https://github.com/interzettel/prehnite/issues/107) / [#109](https://github.com/interzettel/prehnite/issues/109). Independent of the production technical judge. **NOT connected to TypeSafe's API; no requests, uploads, API keys, paid inference, or automated acceptance can happen in this stage.**

TypeSafe [announced Jev 1.14](https://typesafe.ai/blog/jev-1-14) with experimental image, Box and long-context features. Its [image documentation](https://docs.typesafe.ai/images) explicitly calls image and Box support **not ready for production**, requires `TypeSafe-Danger-Zone-Images: true`, and says image inputs must be still PNG/JPEG (280–1568px on each axis, maximum 16 MiB/image, and 32 MiB request/expanded context). EXIF orientation is **not** applied by the provider, and original metadata is stripped.

**Video:** the docs show ordered **extracted still frames** in the request state; native video/audio upload is not documented. A future frame adapter must require rights/consent to every frame, limit timestamps/count/cost, and acknowledge that sparse frames cannot establish what happens between them. This stage deliberately accepts only one still image.

## Contract implemented

`src/prehnite/typed_visual.py` defines a local, provider-neutral internal format, **not yet the TypeSafe SDK's wire JSON**:

- `Question(key, "noul")` — atomic yes/no.
- `Question(key, "choice", options=("ok","review"))` — one declared category.
- `Question(key, "score")` — an uncalibrated scalar 0..1, **not human quality**.
- `Question(key, "box", presence_key="subject_visible")` — normalized x0/y0/x1/y1 box, **only after a matching Noul presence gate**.

`parse_mock_answers` checks the exact question IDs, response types, value bounds, finite confidences and box ordering; absence must produce `box=None`. The result explicitly carries `automatic_acceptance_authorized=false`, `human_verified=false`, and `status=mock_evaluation_only_no_provider_dispatch`. A model can be wrong even when an answer parses correctly, and its confidence must not be treated as calibrated in this project before matched human evaluation.

## Image privacy and size preflight

`prepare_still_image(root, relative_path, historical_sha256)` verifies the SHA256 of the authorized source and refuses traversal or symlink escapes. It enforces a 24MP source cap and locally creates a new still with pixels upright (EXIF-transposed), resized down to 1568px maximum edge, and no forwarded image metadata. RGB becomes baseline JPEG; alpha becomes PNG. It rejects ICC-tagged input until we implement/document a trusted color transform rather than silently throwing away the profile; it also refuses animated inputs, images narrower than 280px and payloads above 16 MiB.

**These sanitized still pixels are private.** No media file is uploaded or saved into a public CI artifact. Users remain responsible for rights to source photographs; do not auto-pull third-party subscriptions or licensed images.

## Explicit budget gates — still no dispatch

`preflight` requires **all three** `allow_paid=True`, `allow_cloud_uploads=True` and `allow_experimental_images=True`. Box has an additional, separate `allow_experimental_box=True` gate. Longer context needs `allow_long_context=True`; without it the maximum entered token ceiling is 64,000, while explicitly experimental mode permits 262,000.

You must supply your own **conservative input-token ceiling** and positive owner-approved `max_usd: Decimal`. It uses the *quoted* TypeSafe price of **$0.042 per million input tokens** to check `token_ceiling × price`, not an estimate silently inferred from image file bytes. The model must be pinned to `jev-1.14.0`, not the moving latest alias. A permit is only an offline check; it cannot spend money or grant transport authorization. Before a future live adapter, verify the vendor's current actual model availability, image tokenization, repeated image references, pricing, context and data-retention policy, **then** introduce an independently reviewed persistent reservation and safe-idempotency journal. Any ambiguous billing state must fail closed.

Image bytes and request references may expand inside TypeSafe's system. Our current one-image receipt checks a conservative body bound but does not purport to calculate real expanded provider tokens. A separate live connector must ensure repeated references never consume more than the model's budget unexpectedly and decline any unknown token bound.

## Test and promotion gates

Run `python -m pytest -q tests/test_typed_visual.py`; normal CI runs the same test suite across the existing Windows/Ubuntu matrix. Fixtures are generated **locally from colored PIL pixels**, not owner assets. Cases cover malformed and unknown typed decisions, all consent switches, immutable SHA receipts, source traversal/symlink, EXIF and ICC, RGB/RGBA media preparation, image dimensions, budget floor, price unknown, Box-on-absent and malicious extra fields. **No provider network tests, screenshots of private user images or cloud-based evaluations.**

**Next PRs:** vendor-specific request/response mapping with deterministic mocked HTTP fixtures; human-reviewed gold dataset and calibration/error/cost comparisons; only then an explicitly approved live smoke test under a separately configured budget. TypeSafe experimental vision must not automatically approve, reject, delete or replace an existing Prehnite accepted original without the owner's policy decision.


## Stage B — official-shape **offline fixtures**, still no API transport

[Issue #111](https://github.com/interzettel/prehnite/issues/111) adds `src/prehnite/jev_wire_fixture.py`: an **inert request JSON builder** and strict parser of vendor-shaped **synthetic** responses. It uses published TypeSafe 1.14 [Noul](https://docs.typesafe.ai/primitives/noul), [Choice](https://docs.typesafe.ai/primitives/choice), [Score](https://docs.typesafe.ai/primitives/score), [Box](https://docs.typesafe.ai/primitives/box), and [Images](https://docs.typesafe.ai/images) documentation. There is still **no TypeSafe HTTP client, SDK import, API key read, request send, provider billing or automatic decision integration**.

The internal Stage A `parse_mock_answers` uses a deliberately simplified Boolean Noul / 0–1 rubric-score shape and should **never** be sent to or confused with TypeSafe. Stage B instead understands the actual documented response fields:

- **Noul**: `{"type":"noul","noul":0.91}` is *yes probability*; the vendor does not return a Boolean and does not include a separate confidence field. Thresholding requires an explicit cost-sensitive policy.
- **Choice**: one declared option name plus the probability distribution over **all** declared options, and a separate `confidence`. The selected option must match the distribution.
- **Score**: numeric position across the *declared ordered levels* (for three levels the range is **0–2**, not 0–1), plus per-level probabilities, legend and confidence; verifies the position against the probability-weighted mean.
- **Box**: `left/top/right/bottom` in normalized 0–1 coordinates, plus confidence. The provider returns a box **even for absent objects**. Stage B refuses malformed edges and masks the box if its linked Noul presence probability is below an operator-supplied threshold (default 0.85, **not calibrated**).

`build_offline_request_fixture` requires a Stage A media receipt and non-dispatch `Preflight` permit already bound to its image SHA256, question count, pinned model and approvals. It constructs an **in-memory fixture only** with one reference to one sanitized image in `state.image`. Instructions point to that state field rather than repeating the raw asset ref, avoiding unnecessary image re-expansion. Candidate danger-zone headers remain inert dictionary values. The serialized body must be within 32 MiB, with a conservative extra media expansion allowance; a future wire transport must re-validate actual measured token count and re-encoding.

`parse_official_mock_response` fails closed on model mismatch, missing/extra question IDs, malformed token counts, invalid probabilities/confidence, inconsistent Choice distributions or Score expected values, and invalid or un-gated boxes. It emits `automatic_acceptance_authorized=false` and `confidence_calibrated_on_our_images=false`.

The tests in `tests/test_jev_wire_fixture.py` use fixed **synthetic response objects** (no provider output is presented as real or personally sourced), including experimental Box and score examples. These tests verify **parsing behavior**, not Jev's visual accuracy, cost, latency, actual calibrated probabilities, data retention, or billing.

**Remaining #111 work:** create an owner-reviewed matched image-and-label evaluation dataset, implement Brier/ECE, false-accept/false-reject and abstention analysis with uncertainty bands and reproducible reports. Only after those are reviewed should a separately approved live smoke test or image/video-frame workflow be considered.
