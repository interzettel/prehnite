# Versioned local artifact provenance

Prehnite writes `provenance.json` into the local batch directory whenever it
writes `report.json`. This is a **deterministic, machine-readable evidence
record**, not a model quality certificate or a provider invoice. The format
uses `schema_version: 1` and deliberately contains no timestamp, random
identifier or absolute user path, so an unchanged resumed batch can
regenerate the same bytes.

## What is recorded

- Batch ID and SHA256 of the exact manifest/profile configuration.
- Per asset: requested dimensions, processing state, selected variant,
  attempt, prompt SHA256 **or** original-input content SHA256, and the
  SHA256 of its source *reference* instead of its private pathname.
- Accepted output's relative name, SHA256, dimensions, color mode and byte
  count, reverified against the journal before export.
- Per stage: hashed task key, stage/status, provider/model, reserved
  **estimated** dollars, hashed request ID, output SHA256, and generation
  seed when known.
- Typed judge winner and rubric scores, when available. Uncalibrated.

The private SQLite `state.sqlite3` still retains operational information,
including original manifest/profile and actual provider request IDs. Treat
the working directory as sensitive; do not publish/upload it.

## Original input immutability

For batches using pre-existing photos, Prehnite records the SHA256 of each
original input **before processing**. Later resumes with different bytes are
refused, including inside the same Engine instance. Previously completed
source-image batches without historical fingerprints cannot be silently
backfilled: manually verify and start a new batch ID.

## Privacy, integrity and limitations

Raw prompts, original source paths, cloud artifact URLs, raw request IDs,
credentials, free-form judge rationales and request bodies are omitted.
SHA256 is not anonymization: hashes of known files/prompts can be
correlated. User-selected output names and provider/model IDs remain.

This record proves local consistency with its SQLite journal, not protection
against a person editing both files and their hashes. It does not verify
provider invoices, image aesthetics or semantic accuracy.

The record currently stays **beside**, not inside, the ZIP. A stable
digest-bearing archive manifest is separately tracked in
[issue #36](https://github.com/interzettel/prehnite/issues/36).
[Offline regression tests](../tests/test_provenance.py) exercise
reproducibility, image tampering, source mutation and private-field redaction.
