# Offline asset review gallery

Each `prehnite run` or `prehnite export` now produces
`workspace/batches/<batch-id>/gallery.html`, included inside the
delivery ZIP at `_prehnite/gallery.html`.

Open the HTML file directly in a browser. There is no web server,
JavaScript, external CSS, font, image request, CDN or analytics tag.
All images visible on that page are **small locally generated base64
thumbnails**, not links to a hosted image endpoint.

The gallery displays each manifest asset, acceptance/rejection state,
reason for rejection or failed cutout, selected delivered image, any
accepted transparent PNG cutout on a checkerboard, and up to four
local generated variant previews from the intermediates directory.
The distinction between a verified accepted file and an intermediate
candidate is kept explicit. For jobs built from privately supplied input
images, the input file is **not** silently imported and embedded into
the HTML; user-approved source inclusion belongs to a separate future
opt-in feature.

## Security and privacy

- The generated HTML has a restrictive Content Security Policy:
  `default-src 'none'; img-src data:; connect-src 'none'`.
  No browser network requests are required.
- Asset names, variant names and failure notes are HTML-escaped.
- Accepted files are decoded and compared with recorded SHA256 values
  before inclusion. A missing digest or corrupted file aborts the gallery
  update instead of incorrectly advertising accepted results.
- Files outside the batch directory are never read as intermediate
  candidates. Images in this report remain on your machine unless **you**
  share the HTML/ZIP file.
- **Sharing the HTML file shares the embedded thumbnail pixels.** Do not
  publish it blindly if the source material is private.
- Gallery thumbnails are downsampled previews, **not pixel-true 4K
  quality evidence**. Use [native detail crops](CROP_EVIDENCE.md) for
  review of image texture and fine details.

## What it doesn't prove

This report does not measure photographic realism, automatically
find subjects, compare full-resolution regions, or certify any model.
A score shown in the report is a separately acquired, uncalibrated
judge score if one exists. A missing score is not silently treated as
quality approval.

See [issue #33](https://github.com/interzettel/prehnite/issues/33),
[review source](../src/prehnite/gallery.py), and the
[engine's documented readiness gates](PROGRESS.md).
