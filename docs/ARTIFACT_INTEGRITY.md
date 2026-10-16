# Atomic artifacts and integrity-aware resume

Prehnite uses **same-directory temporary files** and a final filesystem
rename (os.replace) to publish a validated stage result, selected image,
cutout, report or ZIP. The temporary artifact uses the same image extension
to preserve Pillow/provider encoder behavior. The staging directory must
remain on the same filesystem. A process crash can leave a temporary file;
it cannot publish a half-written image through the validated stage path.

## Trust boundaries

- Each completed image stage records SHA256 and byte size in the SQLite task
  metadata. An apparently completed cached file must decode and match its
  recorded digest before reuse.
- If a paid task's bytes are missing/corrupt but its **remote request ID is
  known**, the engine may retrieve that **same** remote request and publish
  it atomically. It must not submit a new billable request. Lost/ambiguous
  request IDs continue to fail closed.
- Accepted selected files have explicit per-output SHA256 references. On
  resume, missing, altered or undecodable accepted assets are marked as
  integrity errors rather than silently regenerated or included in exports.
- The ZIP is constructed off to the side, checked with ZIP CRC and verified
  against the accepted asset SHA256 hashes, then atomically moved into place.
  The last good ZIP survives packaging errors or output corruption.
- Legacy batches that predate hash metadata cannot prove unchanged output
  bytes. They must be revalidated manually or recreated under a fresh batch
  ID; existing accepted bytes are **not** silently grandfathered in.

## Limitations

This is local file integrity, **not cryptographic authenticity**: a user who
can change both SQLite facts and file contents could forge matching hashes.
Nor is it full power-loss durability: fsync of parent directories and disk
failure recovery are not guaranteed on all operating systems. Accepted stage
files are protected by the batch worker lock, but external programs editing
the selected directory remain outside that lock.

Reusing already-completed accepted outputs with no SHA256 evidence is
refused intentionally. Atomic publishing reduces partial writes but it
does not prove source-image rights, generation quality, true provider prices,
or pixel-accurate segmentation.

The tests exercise interrupted provider writes, recovered paid request IDs,
valid-but-modified photos, corrupt masks, absent files, legacy hashes and
failed ZIP construction—all with mocked or local demo assets at $0.
