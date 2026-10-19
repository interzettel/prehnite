# README CLI hero and selected image

The owner selected the Prehnite laptop, green/coral crystal, desk and terminal illustration from the chat on 2026-10-19. This is the **source art**, not a new prompt for image generation.

## Asset production

The [offline GIF renderer](../scripts/build_cli_hero.py) animates the terminal of that exact source art and leaves the surrounding scene unchanged. It has no model calls, inference, network access, external font downloads or paid dependencies. Produce the GIF with:

```bash
python scripts/build_cli_hero.py \
    --source assets/prehnite-selected-hero.png \
    --output assets/prehnite-cli-hero.gif
```

The source file must be the owner-selected 1672x941 image. The renderer's pixel coordinates are tied specifically to that composition; do not treat it as a generic input-image transformer. The PIL/Pillow dependency is already present in the Python application.

**Packaging limitation:** The cloud authoring environment produced and inspected a real 720x405 animated GIF from the owner's selected original. However, the GitHub connector available to this session only accepts UTF-8 text or in-message base64 and does not ingest sandbox files by path. Do **not** place a broken GIF image link in README, falsely claim the GIF is in the repository, or replace the source art with another generated variant. Keep the source and GIF as independently supplied artifacts pending a separate binary upload. The project README retains the previous approved Riso artwork as the top banner meanwhile.

Once source and GIF have been checked into `assets/`, replace the current README hero `img` path with `assets/prehnite-cli-hero.gif`, preserve a PNG/WebP fallback for reduced-motion readers, and record the committed bytes/hash in this document.

## Diagrams and CLI introduction

- [Architecture/process diagram](../assets/diagrams/workflow.svg) and [product roadmap diagram](../assets/diagrams/roadmap.svg) are **editable, semantic, offline SVGs** using `src/prehnite/brand.py` tokens and actual v2 milestones.
- The `prehnite` bare command prints real ASCII startup art from `src/prehnite/banner.py`. It does not pollute JSON or automation commands.
- The scoped [Diagram Design agent skill](../.agents/skills/diagram-design/UPSTREAM.md) records its MIT upstream source and reviewed installation scope. `npx skills add cathrynlavery/diagram-design` requires a network-connected development machine.
