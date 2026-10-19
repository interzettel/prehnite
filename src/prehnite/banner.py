"""Small, offline ANSI/ASCII Prehnite greeting for human CLI launches.

Never displayed for JSON-oriented subcommands, CI, pipes or --help.
"""
from __future__ import annotations

import os
import sys

GLYPHS = {
    "P": ("#### ", "#   #", "#### ", "#    ", "#    "),
    "R": ("#### ", "#   #", "#### ", "# #  ", "#  ##"),
    "E": ("#####", "#    ", "#### ", "#    ", "#####"),
    "H": ("#   #", "#   #", "#####", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #"),
    "I": ("#####", "  #  ", "  #  ", "  #  ", "#####"),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  "),
}
WORD = "PREHNITE"
TAGLINE = "make the images. keep the experiments."
CORAL = "\x1b[38;2;247;101;91m"
FOREST = "\x1b[38;2;7;82;49m"
RESET = "\x1b[0m"


def logo_lines() -> tuple[str, ...]:
    """Render PREHNITE as compact fixed-width printable ASCII."""
    return tuple(" ".join(GLYPHS[ch][i] for ch in WORD).rstrip() for i in range(5))


def banner(color: bool = False) -> str:
    art = "\n".join(logo_lines())
    if color:
        art = CORAL + art + RESET
        tagline = FOREST + TAGLINE + RESET
    else:
        tagline = TAGLINE
    return f"{art}\n{tagline}\n"


def allow_ansi() -> bool:
    if os.environ.get("NO_COLOR") is not None or os.environ.get("PREHNITE_NO_BANNER"):
        return False
    return sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"
