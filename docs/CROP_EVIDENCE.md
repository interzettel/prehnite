# Native-resolution crop evidence

A low-resolution preview can conceal motion blur, poor texture, haloing,
distorted details or compression. Prehnite can extract **pixel-for-pixel**
square tiles from an existing image, without resizing the crop or asking
an image model to interpret it.

## Run it

```bash
prehnite crops path/to/portrait.png --output detail-evidence --edge 1024
prehnite crops path/to/portrait.png --output detail-evidence \
  --edge 1024 --anchor-x 0.42 --anchor-y 0.36
```

The second command adds a manually positioned detail crop around the
normalized focal point `(0.42, 0.36)`. A focal point is **not** an
automatically detected subject or a segmentation result.

The output folder contains:

- Five full-resolution PNGs: `top-left.png`, `top-right.png`,
  `center.png`, `bottom-left.png`, `bottom-right.png`.
- `anchor.png` only when both focal coordinates are provided.
- `overview.png`, a smaller annotated *navigation image*, never passed
  off as a full-resolution quality check.
- `crops.json` with SHA256 for the source and each tile; exact
  half-open `[x0, y0, x1, y1]` pixel bounds; EXIF-rotated source
  dimensions; the tile edge and an explicit `quality_judgment=none`.

```python
from pathlib import Path
from prehnite.crops import verified_crop_paths

tiles = verified_crop_paths(
    Path("detail-evidence"),
    source=Path("path/to/portrait.png"),
)
# The verified Path objects are suitable for a local viewer or later
# opt-in model-based quality judge; no API call is made automatically.
center = tiles["center"]
```

## Quality and cost boundaries

The crop files are losslessly encoded PNGs from the EXIF-transposed
source pixels, not upscaled or JPEG-recompressed tiles. Each rectangle
can be mapped back exactly to the source's displayed orientation. The
source is never modified and new PNG files are atomically promoted after
Pillow verifies them. The manifest is stored atomically. A tampered tile,
changed source image or altered filename is rejected by
`verified_crop_paths`.

The overview is downscaled to at most 900px on either axis. It is
**not suitable for judging 4K texture/detail quality**. Crop evidence
does not itself judge realism or prompt fidelity. A future opt-in
quality judge may consume these already verified paths, but sending
images to paid providers still requires user permission, price
estimates and spending authorization.

The 24-megapixel source guard is aligned with the current image engine.
The optional anchor is manually supplied (range 0–1); wrong or missing
anchors are rejected instead of guessed. Images smaller than the crop
edge are refused rather than silently enlarged. There is no claim of
hardware-validated 4K model quality.

See [issue #26](https://github.com/interzettel/prehnite/issues/26),
[quality judge rules](../src/prehnite/judges.py), and
[the progress dashboard](progress/STATUS.md).
