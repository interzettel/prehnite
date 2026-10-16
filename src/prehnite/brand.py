"""The only project-brand palette source of truth.

Riso visual identity is editorial/illustrative. Diagnostic maps (such as red
pixel deltas) remain semantic data visualization, not interchangeable brand ink.
Offline HTML embeds these tokens so it stays portable with strict no-network CSP.
"""
from __future__ import annotations

from types import MappingProxyType

LIGHT = MappingProxyType({
    "bg": "#F6EFE2",        # paper
    "paper": "#FFF9EC",     # raised cards
    "panel": "#FFF9EC",
    "ink": "#075231",       # dark forest green
    "fg": "#075231",
    "sub": "#53675A",
    "line": "#D8CBB8",
    "accent": "#075231",    # strong contrast on warm paper
    "coral": "#F7655B",     # decorative Riso ink, not small text on paper
    "coral_text": "#A63D35",  # AA text contrast on paper
})
DARK = MappingProxyType({
    "bg": "#132820",
    "paper": "#203A2E",
    "panel": "#203A2E",
    "ink": "#F6EFE2",
    "fg": "#F6EFE2",
    "sub": "#CED4C2",
    "line": "#465C4E",
    "accent": "#FD8276",   # illuminated coral on dark forest
    "coral": "#FD8276",
    "coral_text": "#FD8276",
})


def embedded_theme_css() -> str:
    """CSS variable override, inserted *last* into existing inline style.

    No external font, image, stylesheet or browser request is introduced.
    """
    variables = ("bg", "paper", "panel", "ink", "fg", "sub", "line", "accent",
                 "coral", "coral_text")
    def rule(values: dict) -> str:
        return ":root{" + ";".join("--" + key.replace("_", "-") + ":" + values[key]
                                  for key in variables) + "}"
    return (
        rule(LIGHT) +
        "@media(prefers-color-scheme:dark){" + rule(DARK) + "}"
        ".fill{background:var(--accent)}"
        ".fill-alert{background:var(--coral)}"
        "input{accent-color:var(--accent)}"
    )
