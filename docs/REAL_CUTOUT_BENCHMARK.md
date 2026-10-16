# Real-image alpha benchmark: local intake (experimental)

Tracked under [#32](https://github.com/interzettel/prehnite/issues/32) with
human-review/corpus dependency [#28](https://github.com/interzettel/prehnite/issues/28).
This is a **scoring tool**, not a new segmenter, retouching model, live
provider workflow or automatic publication mechanism.

## Why a separate real-data path?

The synthetic 20-case challenge benchmark (merged [#120](https://github.com/interzettel/prehnite/pull/120))
is useful for deterministic safety regressions but not evidence that Prehnite
repairs hair, glass, fur, or natural photographs correctly. A real-image test
must compare a **separately annotated and inspected reference alpha matte**
with a candidate alpha matte for the *same original photographic source*.
RGB product edges are not equivalent to alpha color-spill correctness.

Do not copy downloaded reference images into the MIT source repository without
checking their **per-image** rights. A dataset's code or dataset wrapper license
may not settle the underlying photos' copyright. Owner portraits also have
privacy and personality-right considerations.

## Running without any uploads or accounts

Prepare a **private local directory** containing your authorized images:

```text
my-private-corpus/
  sample-001/
    source.webp        # real-world-style input; owner-approved AI-generated WebP also supported
    reference.png      # independently prepared/reviewed 8-bit grayscale alpha
    candidate.png      # Prehnite or baseline predicted 8-bit alpha; RGBA accepted
```

Create a local JSON manifest (not committed) as follows, replacing every example
hash with the actual file SHA256 and every placeholder with a real local path:

```json
{
  "schema_version": 1,
  "items": [{
    "cohort": "portrait-hair",
    "reference_review": "reviewed",
    "rights": {
      "source_type": "owner-authorized",
      "right_to_process_attested": true
    },
    "paths": {
      "source": "sample-001/source.webp",
      "reference": "sample-001/reference.png",
      "candidate": "sample-001/candidate.png"
    },
    "sha256": {
      "source": "REPLACE_WITH_64_CHARACTER_SHA256",
      "reference": "REPLACE_WITH_64_CHARACTER_SHA256",
      "candidate": "REPLACE_WITH_64_CHARACTER_SHA256"
    }
  }]
}
```

For third-party data, use `source_type: "third-party-licensed"` and supply
nonempty `creator`, `source_url`, `license_id`, `license_url` (HTTPS),
as well as `right_to_process_attested: true`. This is an owner assertion
of authorization, **not** independent validation by Prehnite.

Run locally:

```bash
python -m pip install -e ".[dev]"
python scripts/evaluate_real_cutouts.py \
  --manifest /private/local-manifest.json \
  --data-root /private/my-private-corpus \
  --report /private/private-matte-report.json
```

On Windows, use your own quoted Windows paths; the command is otherwise the
same. An input or output path outside its expected place, missing SHA256 match,
invalid image/alpha mode, blank reference matte, geometry mismatch, uncertain permission or EXIF
rotation without prior normalization **refuses** scoring.

The JSON report includes per-sample numerical metrics, cohort summaries and
SHA256 provenance but **never embeds image bytes, photos, original paths, author
names or license source URLs**. The report is still private: image hashes may
be correlatable to known photographs, so do not upload or publish it by default.

## Measurements and limitations

- **Binary IoU:** foreground at alpha >= 128; can hide important mistakes on
  fine/translucent details.
- **Normalized alpha MAE:** mean absolute difference over all alpha pixels;
  preserves soft-opacity differences.
- **Alpha SAD (equivalent pixel count):** absolute alpha difference divided
  by 255; scales with image size.
- **3×3 normalized edge MAE:** morphological-edge difference, sensitive to
  boundary errors; not a perceptual color-decontamination score.

Report separation is by cohort: opaque-product, portrait-hair, animal-fur,
glass, translucent-fabric, furniture-openings, occlusions and other.
Reference review is explicitly `reviewed` or `unreviewed`. Even a
`reviewed` self-attestation is not automatically a validated gold standard.
No score receives an "accepted" label or release threshold at this stage.

**Next gates:** acquire per-photo permitted sources and independent matte
references, obtain at least two human reviews for contested edge cases,
pre-register category thresholds and uncertainty/abstention handling,
evaluate actual pipeline candidates, and publish only aggregate results
with attribution where permitted. This PR does not meet S06 or S07 and
does not change the 42/61 evidence ledger.

## Possible source: P3M-10k (licensing still requires judgment)

The primary authors' dataset release agreement:
https://jizhizili.github.io/files/p3m_dataset_agreement/P3M-10k_Dataset_Release_Agreement.pdf

It describes MIT dataset distribution and original photographs remaining
copyrighted to their creators. We have **not** downloaded the dataset,
accepted legal terms on the owner's behalf, or committed any of its pixels.
For actual benchmark samples, inspect the applicable agreement and individual
reuse restrictions first; prefer privacy-blurred portraits when suitable.
For separately selected Commons photographs, check each file's exact license
and record correct attribution, permitted derivatives and personality rights:
https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia

**Costs:** zero provider calls or paid inference. **Privacy:** no image uploads,
no remote fetch, and no default public gallery.

## Private AI-generated product pilot: source-only intake

An owner-authorized AI-generated apparel pilot stored in an existing
Cloudflare R2 bucket is available for testing. As of the October 2026
inventory, it contains **18 front-view WebPs and 5 care-label WebPs**.
The owner's permission covers **testing**, not automatic public
redistribution. Raw images, dashboard addresses, object keys and the
private hash manifest should **not** be committed to the public repository.

The connected Cloudflare API confirms object metadata and GET responses,
but its binary-object bridge decodes arbitrary bytes as text. This
makes full image content untrustworthy to reconstruct from that API.
We therefore only count image-level decoding and local SHA256
verification after an exact-byte export. Cloudflare-provided
`sourceSHA256` values are metadata claims until compared with the
downloaded original bytes.

1. Export original R2 objects into a **private local directory** using
   your authorized R2 dashboard or personally configured S3-compatible
   client. Keep all raw bytes unchanged.
2. Save the separately provided private pilot manifest outside Git,
   with one `objects` entry per downloaded WebP: `path` relative to
   your export root, `role` (`front` or `care_label`), exact `size`,
   and 64-digit `sha256`.
3. Run the offline check:

```bash
python scripts/preflight_private_pilot.py \
  --manifest /private/pilot-manifest.json \
  --data-root /private/r2-pilot \
  --report /private/pilot-preflight.json
```

This verifies raw hash/length, file signature, full Pillow decoding,
dimensions, orientation and alpha presence. The JSON includes no raw
images, source filenames or absolute source paths. It explicitly reports
**zero reference masks** and **no cutout-quality IoU**.

To measure the actual cutout accuracy later, prepare a separate,
independently reviewed grayscale/alpha reference and a candidate matte for
the same WebP original, then use `scripts/evaluate_real_cutouts.py`.
An embedded WebP alpha channel is **not** automatically an independent
quality reference. Never synthesize ground truth from the candidate
being evaluated.

Source-only preflight, unsupported-image refusal and WebP scoring support
are exercised with **synthetic fixtures** in both Windows and Ubuntu CI.
The real R2 images are not silently downloaded or uploaded by CI.
