"""Smoke-test the *public PyPI wheel*, not the local repository checkout.

Run on independent GitHub Actions Windows and Linux runners after alpha release.
No API keys, inference, model checkpoints or package publishing.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys
import tempfile

VERSION = "0.1.0a1"
WHEEL = f"prehnite-{VERSION}-py3-none-any.whl"
EXPECTED_SHA256 = "098560a9de1c06afa01a605c5a7d8d3a02f3197a0c00c2e9fbba8914f6637908"


def run(*args: str) -> None:
    subprocess.run(list(args), check=True, timeout=180)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="prehnite-public-alpha-") as working:
        root = Path(working)
        wheels = root / "wheels"
        wheels.mkdir()

        # Deliberately contact the public index; no local build and no source checkout.
        run(
            sys.executable, "-m", "pip", "download",
            "--index-url", "https://pypi.org/simple",
            "--no-deps", "--no-cache-dir", "--only-binary=:all:",
            "--dest", str(wheels), f"prehnite=={VERSION}",
        )
        files = sorted(wheels.iterdir())
        if [f.name for f in files] != [WHEEL]:
            raise RuntimeError(f"Wrong public PyPI distribution: {[f.name for f in files]}")
        digest = hashlib.sha256(files[0].read_bytes()).hexdigest()
        if digest != EXPECTED_SHA256:
            raise RuntimeError(f"Published PyPI wheel hash mismatch: {digest}")

        venv = root / "venv"
        run(sys.executable, "-m", "venv", str(venv))
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(str(python), "-m", "pip", "install", "--no-cache-dir", str(files[0]))

        # Do not import from the repository's working directory.
        check_code = (
            "import importlib.metadata, prehnite; "
            f"assert prehnite.__version__ == '{VERSION}'; "
            f"assert importlib.metadata.version('prehnite') == '{VERSION}'"
        )
        subprocess.run([str(python), "-c", check_code], cwd=root, check=True, timeout=30)
        prehnite_cli = venv / ("Scripts/prehnite.exe" if os.name == "nt" else "bin/prehnite")
        subprocess.run([str(prehnite_cli), "--help"], cwd=root, check=True, timeout=30)
        subprocess.run([str(prehnite_cli), "doctor"], cwd=root, check=True, timeout=30)
        print(f"PUBLIC PYPI INSTALL OK: {WHEEL}, SHA256={digest}, {sys.platform}")


if __name__ == "__main__":
    main()
