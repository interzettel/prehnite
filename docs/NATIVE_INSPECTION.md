# Native-pixel inspection — one asset, private and offline

**Child issue:** [#93](https://github.com/interzettel/prehnite/issues/93) of dashboard initiative #6.

The ordinary `gallery.html` uses downsampled embedded thumbnails so 90 assets do not create an enormous HTML file. For a close review of accepted images and PNG cutouts, generate one **on-demand full-resolution** HTML page instead:

```bash
prehnite inspect my-batch --asset asset-014 --workspace workspace
```

The output lives in `workspace/batches/my-batch/reviews/asset-014.html`. For a **source-backed** slot, you may additionally run `prehnite inspect my-batch --asset asset-014 --workspace workspace --inputs /path/to/original-input-root` to show the recorded original alongside the base/cutouts. The original must match the **historical SHA256** stored when the batch was first processed; no source-root guessing, no implicit re-fingerprinting, and no original panel for prompt-generated slots. Open it locally in a browser. Select **Fit to panel** for a side-by-side overview or **Actual pixels (1:1)** for scrolling/panning at the original image's native pixel dimensions. Each named cutout is displayed against a checkerboard so alpha edges are visible. The browser can still apply OS display scaling; use 100% browser zoom for meaningful 1:1 inspection.

## Safety and fidelity

- Reads **only** recorded selected deliverables for the requested accepted or base-accepted/failed-cutout slot. No model inference or provider billable calls.
- Verifies the original file with the recorded SHA256 and image decoder; embeds the *same original bytes*, **without resampling/reencoding**, and hashes bytes a second time before writing the HTML.
- Rejects missing/changed/broken images and paths escaping `selected/`, including symlinked external files. Any previously generated detail remains unchanged when validation fails.
- Caps embedded raw bytes to 64 MiB and displayed panels to 12 so a full 90×4K batch is **never** embedded into one document. The ordinary gallery, reports, data exports and accepted-output ZIP remain unchanged.
- Page has **no JavaScript, network fetches, remote CSS/fonts or external images**, and enforces a strict CSP (`connect-src 'none'`, `img-src data:`).
- Only a local asset identifier and selected output labels are displayed. Raw prompts, provider request IDs and error strings are not added to the page. The page **does contain private image bytes and filenames**: don't publish or upload it without specific consent.

This is a *visual inspection instrument*, not a numerical quality score or a claim that an AI model passed calibrated human review. No per-pixel image diff, color profile normalization or native-resolution browser screenshot automation is claimed.

## Evidence

`python -m pytest -q tests/test_native_inspection.py` covers byte-for-byte embedded originals, 1:1/fit toggles, named alpha cutouts, output tampering, symlinks escaping the workspace, blocked rejected slots, oversized images, CLI usage and only-one-slot preview from a 90-slot manifest. Existing Windows and Ubuntu offline 90-asset CI must remain green.

## Future

This is the bounded first step of #93. Richer work may add anchored pan/zoom, variant-vs-variant comparisons, visual diff overlays and explicit agent-guided human review. These should remain offline, opt-in and fail closed when images or their provenance cannot be verified.
