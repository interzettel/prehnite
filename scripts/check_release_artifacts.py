#!/usr/bin/env python3
"""Strict offline wheel/sdist preflight; no network, publishing, or model execution."""

from __future__ import annotations

import argparse
import hashlib
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile

from packaging.version import Version


NAME = "prehnite"
FORBIDDEN_SUFFIXES = {
    ".pem", ".p12", ".pfx", ".key", ".db", ".sqlite", ".sqlite3", ".env",
}
FORBIDDEN_COMPONENTS = {
    ".git", ".github", ".venv", "__pycache__", "workspace", "checkpoints",
    "private", "secrets", "models", "input-images",
}


def source_version(root: Path) -> str:
    source = (root / "src" / NAME / "_version.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"\s*$', source, re.MULTILINE)
    if match is None:
        raise ValueError("Cannot read canonical __version__ from the checked-out source")
    return match.group(1)


def safe_names(names: list[str], *, prefix: str | None = None) -> None:
    for member in names:
        if not member or member.startswith("/") or "\\" in member:
            raise ValueError(f"Unsafe archive entry: {member!r}")
        p = PurePosixPath(member)
        if any(part in ("", ".", "..") for part in member.split("/")) and not member.endswith("/"):
            raise ValueError(f"Noncanonical archive entry: {member!r}")
        if ".." in p.parts or p.is_absolute():
            raise ValueError(f"Unsafe archive entry: {member!r}")
        if prefix is not None and not member.startswith(prefix):
            raise ValueError(f"Source archive entry escapes expected top folder: {member!r}")
        if set(part.lower() for part in p.parts) & FORBIDDEN_COMPONENTS:
            raise ValueError(f"Private or generated content may be packaged: {member!r}")
        if p.name.lower().startswith(".env") or p.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise ValueError(f"Secret-like artifact may be packaged: {member!r}")


def check(dist: Path, version: str, *, require_public_release: bool = False) -> list[Path]:
    parsed = Version(version)
    if str(parsed) != version:
        raise ValueError("Expected version must be canonical PEP 440")
    if require_public_release and (parsed.is_devrelease or parsed.is_postrelease or parsed.local):
        raise ValueError("Public alpha/release cannot use a dev, post, or local build suffix")

    root = Path(__file__).resolve().parents[1]
    if source_version(root) != version:
        raise ValueError("Source version does not match the approved version")

    expected = {
        f"{NAME}-{version}-py3-none-any.whl",
        f"{NAME}-{version}.tar.gz",
    }
    files = sorted(path for path in dist.iterdir() if path.is_file())
    if set(path.name for path in files) != expected:
        raise ValueError(
            f"Expected only wheel+sdist for {version}; got {[path.name for path in files]}"
        )

    wheel = dist / f"{NAME}-{version}-py3-none-any.whl"
    sdist = dist / f"{NAME}-{version}.tar.gz"
    if any(path.stat().st_size < 1024 for path in files):
        raise ValueError("Suspiciously small distribution")

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        safe_names(names)
        meta = f"{NAME}-{version}.dist-info/METADATA"
        scripts = f"{NAME}-{version}.dist-info/entry_points.txt"
        if meta not in names or scripts not in names or f"{NAME}/cli.py" not in names:
            raise ValueError("Wheel is missing package metadata or CLI")
        allowed = (f"{NAME}/", f"{NAME}-{version}.dist-info/")
        if any(not item.startswith(allowed) for item in names):
            raise ValueError("Wheel contains unexpected top-level paths")
        metadata = BytesParser().parsebytes(archive.read(meta), headersonly=True)
        entries = archive.read(scripts).decode("utf-8")
        if "prehnite = " not in entries or "prehnite-mcp = " not in entries:
            raise ValueError("Wheel lacks required CLI entrypoints")
        if metadata["Name"].lower() != NAME or metadata["Version"] != version:
            raise ValueError("Wheel metadata has wrong name/version")
        if metadata["Requires-Python"] != ">=3.11":
            raise ValueError("Wrong Python compatibility metadata")

    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        safe_names(names, prefix=f"{NAME}-{version}/")
        if any(m.issym() or m.islnk() or m.isdev() for m in members):
            raise ValueError("Source archive must not contain links or device files")
        required = {
            f"{NAME}-{version}/pyproject.toml",
            f"{NAME}-{version}/README.md",
            f"{NAME}-{version}/src/{NAME}/_version.py",
        }
        if not required.issubset(names):
            raise ValueError("Source archive lacks package source/metadata")

    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"Artifact SHA256 {path.name}: {digest} ({path.stat().st_size} bytes)")
    print(f"Validated {version}: wheel + sdist (no upload performed)")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--expected-version", required=False)
    parser.add_argument("--require-public-release", action="store_true")
    args = parser.parse_args()
    version = args.expected_version or source_version(Path(__file__).resolve().parents[1])
    check(args.dist, version, require_public_release=args.require_public_release)


if __name__ == "__main__":
    main()
