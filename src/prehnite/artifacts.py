"""Crash-safe local artifacts: only verified complete files are published."""
from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .images import image_info, resize_to


class ArtifactIntegrityError(ValueError):
    """A previously accepted artifact is missing, undecodable, or changed."""


@contextmanager
def temporary_sibling(destination: Path):
    """Temporary filename in the SAME filesystem, preserving image extension."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(
        prefix=".prehnite-", suffix=destination.suffix, dir=destination.parent
    )
    os.close(fd)
    temp = Path(filename)
    try:
        yield temp
    finally:
        temp.unlink(missing_ok=True)


def verified_image(path: Path, expected_sha256: str | None):
    if not expected_sha256:
        raise ArtifactIntegrityError(f"Missing SHA256 evidence for {path.name}")
    if not path.is_file():
        raise ArtifactIntegrityError(f"Missing accepted image: {path.name}")
    try:
        info = image_info(path)
    except (OSError, ValueError) as exc:
        raise ArtifactIntegrityError(f"Undecodable accepted image: {path.name}") from exc
    if info["sha256"] != expected_sha256:
        raise ArtifactIntegrityError(f"SHA256 mismatch for accepted image: {path.name}")
    return info


def atomic_resize(source: Path, destination: Path, size: tuple[int, int]) -> dict:
    with temporary_sibling(destination) as temp:
        info = resize_to(source, temp, size)
        os.replace(temp, destination)
        return info


def atomic_copy_image(source: Path, destination: Path) -> dict:
    with temporary_sibling(destination) as temp:
        shutil.copyfile(source, temp)
        info = image_info(temp)
        os.replace(temp, destination)
        return info


def atomic_text(destination: Path, content: str) -> None:
    with temporary_sibling(destination) as temp:
        temp.write_text(content, encoding="utf-8")
        os.replace(temp, destination)
