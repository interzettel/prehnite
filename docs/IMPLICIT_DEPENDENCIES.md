# Operator-declared implicit segmentation dependencies

The locally hosted GroundingDINO/SAM2/BERT stack can load files that are
**not explicit ComfyUI graph string inputs**: GroundingDINO checkpoints and
config, BERT model/config/tokenizer/vocab, SAM2 weights/config, and potentially
custom-node resources. The existing [graph-bound model receipt](MULTIFILE_PROVENANCE.md)
cannot discover these automatically.

For the **new reviewed-source cutout batch only**, Prehnite now accepts a
strict private dependency manifest. This is **opt-in, offline, read-only file
attestation**, not proof of what custom-node Python code loads at runtime.
Do not treat it as model installation, an approved licence or permission
to execute the reviewed cutout.

## Files and roots

Take the [public placeholder format](../examples/implicit-dependencies.example.json)
and create a PRIVATE version with **every relevant file** from the local
segmentation installation plan. Entries have:

- A unique role and type: `weight`, `config`, `tokenizer`, or `custom_node_source`.
- Canonical POSIX-relative path beneath **one explicit, existing** model/dependency root.
- SHA256 of the exact bytes (including small configs and tokenizer files).
- Official HTTPS source URL, an exact 40–64-character immutable hexadecimal
  source commit, and HTTPS licence reference. These values are operator supplied;
  Prehnite does not fetch or independently certify them.

Read-only hashing streams in 1 MiB chunks rather than loading large model
weights into RAM. It rejects missing/changed files, symlinked components,
root traversal, duplicate roles/paths, disallowed extensions, non-HTTPS source
and missing immutable revisions. Python `.py` configs are **hashed, never
imported or executed**.

Put `implicit-dependencies.json` in the *same private inputs folder* as the
already reviewed SDXL image/attestation. Keep all large checkpoint bytes under
the separate user-controlled `--dependencies-root`; never copy them into
the repository or source PNG directory.

Add two OPTIONAL fields to the existing private reviewed-source manifest,
without rewriting `review-handoff.json` or changing its SHA:

```yaml
handoff:
  # Keep ALL existing candidate/review SHA and exact target fields.
  implicit_manifest: implicit-dependencies.json
  implicit_manifest_sha256: REPLACE_WITH_ACTUAL_64_CHARACTER_SHA256
```

Both fields must be provided together. When supplied, the root is mandatory.
Use the **current source checkout** (not published PyPI `0.1.0a1`):

```powershell
$lab = "C:\Users\yigit\Documents\repos\prehnite-local-lab"
$prehnite = "C:\Users\yigit\Documents\repos\prehnite"
& "$prehnite\.venv\Scripts\prehnite.exe" validate `
  "$lab\_private\sdxl-1k\handoff-v2\manifest-reviewed-cutout.yaml" `
  --profile "$prehnite\examples\profile-reviewed-cutout.yaml" `
  --inputs "$lab\_private\sdxl-1k\handoff-v2\inputs" `
  --dependencies-root "$lab\_private\segmentation-downloads"
```

The root path above is illustrative: use the **actual verified staging or
installed-model root** from the local Codex environment. For a later authorized
`prehnite run`, pass the **same** `--dependencies-root`. Both `validate`
and the engine fail closed if the manifest is pinned but root is missing.
The engine rehashes declared files at preflight, before executing the new batch,
and before cutout, rejecting drift/resume identity changes. It stores a
separate `implicit_dependency_attestation` inside
`human_review_handoff`, including hashes, official-source *claims* and
negative quality/runtime flags. The original rejected generation batch is
unchanged. Legacy reviewed-source manifests without these optional fields
still work and are **not** represented as having implicit dependency coverage.

## Deliberate limitations and next gates

This verifies **only files listed by the operator**. It cannot discover
hidden custom-node dependencies, prove graph references, verify a model
actually loaded those bytes, attest pip packages or authenticate the reviewer's
identity. The SHA record is not a complete SBOM. Actual ComfyUI-SAM2 model
placement and node revision must be reviewed separately after installation,
and the run is still blocked on explicit owner GPU authorization. A valid
cutout remains `review_pending` until separately reviewed.

Nothing here downloads weights, installs Python packages or makes paid API
calls. See [issue #156](https://github.com/interzettel/prehnite/issues/156)
for further runtime-adjacent attestation and complete model inventory.
