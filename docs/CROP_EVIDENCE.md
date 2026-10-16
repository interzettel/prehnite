# Native-resolution detail evidence

Run `prehnite crops path/to/image.jpg --output inspection/example --edge 1024`
to create five **pixel-true** detail tiles (all four corners and center).
Add `--anchor-x 0.55 --anchor-y 0.28` for a sixth crop centered around
a manually selected normalized source-image point. No inferred subject is
claimed and no input pixels are upscaled.

Outputs: lossless PNG crops, a *downsampled navigation-only* overview.png,
and crops.json containing EXIF-transposed source geometry, each source-pixel
xyxy box (exclusive max), exact SHA256 and byte lengths. Crops can support
human detail inspection; a low-resolution overview cannot establish 4K
photographic quality.

Offline tests check native-pixel equality at 2160×3840, bounds, color/alpha,
EXIF orientation, reproducibility, CLI safety and atomic output behavior.
No provider/GPU/cloud requests are involved. A calibrated visual judge,
rights-cleared corpus and subject localization remain separate (#28, #63).
