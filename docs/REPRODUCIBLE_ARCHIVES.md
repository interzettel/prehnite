# Reproducible ZIPs and digest receipts

Prehnite writes each accepted image and included report using a stable ZIP
timestamp (1980-01-01), platform-neutral permissions and lexicographic entry
ordering. A deterministic `_prehnite/archive-manifest.json` records the
SHA256 of every included image and report (excluding the manifest itself).
The archive is verified for CRC and each manifest digest **before** atomic
promotion to its final path. An interrupted ZIP operation preserves the last
good archive. Source file modification timestamps have no effect on ZIP bytes.

This is *repeatable packaging for identical contents*, not guaranteed
reproduction of inference across models, machines or changing providers.
Mutating a report's contents changes the archive by design. The private
batch journal is not included. Provenance and report JSON may still contain
details the user should review before distributing a ZIP.

Tests verify exact repeated archive bytes after modifying source mtimes,
fixed entry metadata, sorted names and manifest digests. All tests are
offline and do not purchase inference.
