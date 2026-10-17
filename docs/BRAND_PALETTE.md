# Prehnite visual identity — Green/Coral Riso

**Selected by the project owner on 16 October 2026:** the **first** of two submitted Riso wordmark compositions. The chosen image is the warm-paper, dark-forest-green and coral variant. The image is now supplied as a [2020 × 779 full-resolution PNG](../assets/prehnite-riso-green-coral.png), derived from the owner's original upload with original dimensions and composition preserved. A palette-optimized PNG keeps the Riso paper/ink textures at full pixel resolution; actual transparent rounded corners are baked into the asset because GitHub strips inline CSS. The obsolete low-resolution WebP and nonmatching full wordmark SVG are deleted. The separate [mineral mark SVG](../assets/prehnite-mark.svg) remains available.

This document and [`src/prehnite/brand.py`](../src/prehnite/brand.py) establish the source-of-truth color roles for new Prehnite user-facing surfaces. If a new UI, diagram, presentation or chart requires brand colors, use these tokens, not ad hoc mint/teal/gold. Offline HTML embeds these tokens inline: **no external CSS or remote font is needed**. Diagnostic pixels, heatmaps and status colors must retain meaning rather than being arbitrarily replaced by coral.

## Repository hero and secondary mark

The README intentionally **displays the artwork rather than explaining its implementation**. The owner-selected **forest green / coral / warm paper** Riso colorway uses a [2020 × 779 rounded-corner PNG](../assets/prehnite-riso-green-coral.png). The image itself contains transparent clipped corners; this remains visually rounded on GitHub even when GitHub sanitizes custom inline CSS. Preserve the original paper grain and separation texture rather than replacing it with CSS approximations or a low-resolution WebP.

Shared accessible light/dark token roles below also apply to other project surfaces. The separate [mineral symbol SVG](../assets/prehnite-mark.svg) remains available for compact applications; it is not a replacement for the full wordmark. The main README should contain only the visual hero and useful navigation, not this production rationale.

## Palette roles

| Role | Light mode | Dark mode | Usage |
| --- | --- | --- | --- |
| Background / warm paper | `#F6EFE2` | `#132820` | Editorial canvas |
| Raised surface | `#FFF9EC` | `#203A2E` | Cards, tables, panels |
| Main text / forest | `#075231` | `#F6EFE2` | Text, navigation, headings |
| Secondary text | `#53675A` | `#CED4C2` | Captions and labels |
| Border | `#D8CBB8` | `#465C4E` | Muted dividers |
| Accent | `#075231` | `#FD8276` | Buttons, checkbox accents, charts |
| Coral Riso ink | `#F7655B` | `#FD8276` | Decorative print layers and strong marks |
| Coral text | `#A63D35` | `#FD8276` | Text/status labels on matching background |

The supplied bitmap uses *organic paper grain, coarse halftones, misregistration and uneven ink coverage*. Preserve those as **artwork characteristics**; do not replace the wordmark with gradients, glossy UI, or generic gem-icon styling. Avoid redrawing this hero with a synthesized approximation when the actual source image is available.

## Contrast

- Dark green `#075231` on paper `#F6EFE2`: approximately **8.1:1** (passes WCAG AA for normal text).
- Bright coral `#F7655B` against paper: approximately **2.6:1**, **not suitable for small text**; use `#A63D35` instead (around **5.5:1**).
- Dark-mode light text `#F6EFE2` on `#132820`: above **12:1**.
- Dark-mode coral `#FD8276` on `#132820`: around **6:1**.

These are representative sRGB contrast comparisons for token pairing, not a substitute for checking full component states and real screenshots. Keep semantic red error maps, positive/negative data encodings and exact alpha-checkerboard contrast separate from decorative Riso coral.

## Practical requirements

For new UI, import `prehnite.brand.embedded_theme_css` and insert its return value **last** in an offline page's inline `<style>`. This keeps the already shipped no-network CSP and supports `prefers-color-scheme: dark`. The gallery, native inspector and pixel diagnostics use this shared override. Updates to the palette must update the source module, this documentation, contrast tests and synthetic HTML fixtures together.

**Licensing:** the Riso image was supplied by the project owner for use in this project. Do not assume separate model weights, third-party assets, or fonts inherit Prehnite's MIT code license.
