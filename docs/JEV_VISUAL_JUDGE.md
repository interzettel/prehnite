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
