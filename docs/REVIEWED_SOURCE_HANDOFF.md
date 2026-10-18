# Reviewed-source handoff — exact bytes, separate quality gates

> **Status update (2026-10-18):** A later, separately authorized private
> desk-lamp segmentation job succeeded, followed by CPU-only alpha
> refinement and **independent visual acceptance of Candidate A** at the
> inspected comparison scale. See the [first real accepted cutout](LOCAL_LAB_MILESTONE_2026-10-18.md).
> This does **not** retroactively accept the original SDXL generation batch
> or turn the source-only attestation into owner-signed cutout acceptance.
> The CLI example and placeholders below are a **pre-execution template**,
> not instructions to rerun the already completed lamp.

Prehnite can process a human-approved generated image into a cutout candidate without regenerating it, changing its original rejected batch or weakening `uncertain: reject`. **A source approved for the next stage is not an accepted alpha cutout.** This is unpublished development work, not PyPI `0.1.0a1`.

## Private files required

Put all three files under the approved private `--inputs` root (never commit them):

1. `reviewed-source.png`, unchanged from the reviewed SDXL 768×1024 original (SHA256 `282e6d4af8ab3a68cafef674ff33d8bd20001be3b4dfedfb216c853fca6832d3`).
2. `original-human-review.md`, an unchanged private copy of the original owner's review document (reported SHA256 `97f66bcd94f2752894279576276facd5839d652cbdd605226834f67551c15dad`).
3. `review-handoff.json`, a NEW structured operator attestation. Compute its own SHA256 after it is written, and put that value into a private manifest. An attestation is not an authenticated digital signature.

Typed JSON receipt content for this specific lamp (the original review's hash stays unchanged):

    {
      "schema_version": 1,
      "source_batch": "sdxl-1k-generation",
      "candidate_sha256": "282e6d4af8ab3a68cafef674ff33d8bd20001be3b4dfedfb216c853fca6832d3",
      "original_review_sha256": "97f66bcd94f2752894279576276facd5839d652cbdd605226834f67551c15dad",
      "verdict": "accepted_for_next_stage",
      "target_phrase": "table lamp",
      "include": ["lamp body", "lampshade"],
      "exclude": ["power cord", "tabletop", "cast shadow", "background"]
    }

Use `Get-FileHash -Algorithm SHA256` for `review-handoff.json`, then replace the zero-filled placeholder in a **private copy** of [the example manifest](../examples/manifest-reviewed-cutout.example.yaml). The old review document and the generated PNG are never modified.

## Validation and execution

- Exactly one source asset, one cutout target, and a **new batch ID** different from the original `source_batch`. No prompts or generation stage.
- Use [the generation-disabled local profile](../examples/profile-reviewed-cutout.yaml). Empty variants are allowed only with a handoff; generation/judge/upscale must be disabled, segmentation must be local ComfyUI, and the attempt limit must be one. Paid/cloud/cache modes, automatic repair and `accept_unverified` are forbidden.
- Candidate image, original review and structured receipt hashes are all rechecked before **creating a new journal** and again before segmentation; the typed receipt must match the manifest's verdict, source, target and include/exclude declarations exactly.
- The actual segmentation text is `table lamp` rather than the output filename slug `table-lamp`.
- Outputs go under `review_pending/`, never `selected/`. Report has a separate `human_review_handoff` fact and `cutout_status: awaiting_human_review` or `failed`; no pending image is silently packaged as accepted.
- Failed cutouts have no automatic retry; a subsequent owner decision must authorize further attempts. The original source batch remains untouched.

## Safe local smoke

After copying the reviewed source/document, writing the structured receipt and replacing its SHA, run (PowerShell, from a current development checkout):

    $env:PREHNITE_WORKFLOWS = 'C:\Users\yigit\Documents\repos\prehnite-local-lab\_private\workflows'
    & 'C:\Users\yigit\Documents\repos\prehnite\.venv\Scripts\prehnite.exe' validate 'PATH_TO_PRIVATE_HANDOFF_MANIFEST.yaml' --profile 'C:\Users\yigit\Documents\repos\prehnite\examples\profile-reviewed-cutout.yaml' --inputs 'PATH_TO_PRIVATE_HANDOFF_INPUTS'

Only validation is safe without installed segmentation models. The profile node IDs are **placeholders**, not verified against ComfyUI-SAM2, and a later `prehnite run` will execute actual local segmentation. Do not run until model rights, installed nodes, graph mappings, and explicit user approval are established.

## Optional strict implicit-model byte attestation

For a GroundingDINO/SAM2/BERT custom-node stack, add a separate
[operator-declared dependency manifest](IMPLICIT_DEPENDENCIES.md) to the
private reviewed-source packet, pin its SHA256 with
`handoff.implicit_manifest` and `handoff.implicit_manifest_sha256`,
and pass `--dependencies-root` to both `prehnite validate` and the later
separately authorized `prehnite run`. The engine rehashes declared model,
config and tokenizer files before execution and cutout, then records them
under `human_review_handoff.implicit_dependency_attestation`. An old packet
without this optional extension remains valid but cannot claim implicit
dependency coverage. No inference or download is authorized by attestation.

## Limits

These hashes establish file integrity and a claimed operator review, **not** independent human authentication, runtime GPU model provenance, actual cord exclusion, mask accuracy or automatic quality acceptance. Implicit GroundingDINO/BERT dependencies in custom nodes still need separate, byte-pinned runtime-adjacent model evidence. See [multi-file provenance](MULTIFILE_PROVENANCE.md).
