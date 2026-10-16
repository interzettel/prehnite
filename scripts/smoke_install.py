"""Clean-wheel installation smoke test for Linux and Windows CI runners.

Builds wheel and sdist locally, installs the wheel into a new isolated
virtual environment, exercises the free synthetic CLI, and does not publish.
Requires `python -m pip install build` in the invoking environment.
"""
from __future__ import annotations

import email
import json
import os
import platform
import re
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(argv: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        argv, cwd=ROOT, env=env, capture_output=True,
        text=True, check=False, timeout=180,
    )
    if completed.returncode:
        # We intentionally do not print captured secrets or environment.
        raise RuntimeError(f"Smoke command failed: {Path(argv[0]).name} "
                           f"(exit {completed.returncode})")
    return completed.stdout


def package_metadata(data: str, *, wheel: bool) -> tuple[str, str]:
    if wheel:
        with zipfile.ZipFile(data) as archive:
            metadata = [name for name in archive.namelist()
                        if name.endswith(".dist-info/METADATA")]
            if len(metadata) != 1:
                raise AssertionError("Exactly one wheel METADATA is required")
            raw = archive.read(metadata[0]).decode("utf-8")
    else:
        with tarfile.open(data, mode="r:gz") as archive:
            metadata = [m for m in archive.getmembers()
                        if m.isfile() and m.name.endswith("/PKG-INFO")]
            if len(metadata) != 1:
                raise AssertionError("Exactly one sdist PKG-INFO is required")
            member = archive.extractfile(metadata[0])
            if member is None:
                raise AssertionError("Cannot read sdist PKG-INFO")
            raw = member.read().decode("utf-8")
    document = email.message_from_string(raw)
    if document.get("Name", "").lower() != "prehnite":
        raise AssertionError("Package metadata has the wrong project name")
    value = document.get("Version")
    if not value:
        raise AssertionError("Package metadata omits Version")
    if not document.get("Requires-Python"):
        raise AssertionError("Package metadata omits Requires-Python")
    return (document["Name"], value)


def smoke() -> dict:
    version_text = (ROOT / "src/prehnite/_version.py").read_text(encoding="utf-8")
    matched = re.search(r'^__version__ = "([^"]+)"', version_text, re.MULTILINE)
    if not matched:
        raise AssertionError("Missing canonical source version")
    __version__ = matched.group(1)
    with tempfile.TemporaryDirectory(prefix="prehnite-install-smoke-") as tmp:
        area = Path(tmp)
        out = area / "artifacts"
        execute([sys.executable, "-m", "build", "--outdir", str(out), str(ROOT)])
        wheels = sorted(out.glob("prehnite-*.whl"))
        sources = sorted(out.glob("prehnite-*.tar.gz"))
        if len(wheels) != 1 or len(sources) != 1:
            raise AssertionError("Expected exactly one wheel and one sdist")
        for pkg, is_wheel in ((wheels[0], True), (sources[0], False)):
            _, found = package_metadata(str(pkg), wheel=is_wheel)
            if found != __version__:
                raise AssertionError("Distribution metadata version drift")
        virtual = area / "venv"
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(virtual)
        bin_dir = virtual / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        cli = bin_dir / ("prehnite.exe" if os.name == "nt" else "prehnite")
        env = os.environ.copy()
        env.pop("FAL_KEY", None)
        env.pop("ANTHROPIC_API_KEY", None)
        env["PYTHONNOUSERSITE"] = "1"
        execute([str(python), "-m", "pip", "install",
                 "--disable-pip-version-check", "--no-input",
                 str(wheels[0])], env=env)
        # Verify the fresh wheel does not pull in paid clients or GPU stacks
        # as mandatory dependencies. This runs *inside* the clean venv.
        probe = ("import json,importlib.util; print(json.dumps({"
                 "m:importlib.util.find_spec(m) is not None for m in "
                 "('torch','fal_client','anthropic','mcp')}))")
        forbidden = json.loads(execute([str(python), "-c", probe], env=env))
        if any(forbidden.values()):
            raise AssertionError("Optional GPU or provider extras were installed by default")
        starter = area / "starter"
        commands = [
            [str(cli), "init", "--destination", str(starter),
             "--batch-id", "smoke-batch"],
            [str(cli), "doctor"],
            [str(cli), "validate", str(starter / "manifest.yaml"),
             "--profile", str(starter / "profile.yaml")],
            [str(cli), "run", str(starter / "manifest.yaml"),
             "--profile", str(starter / "profile.yaml"),
             "--workspace", str(area / "workspace")],
        ]
        outputs = [execute(cmd, env=env) for cmd in commands]
        doctor = json.loads(outputs[1])
        if doctor["runtime"]["prehnite_version"] != __version__:
            raise AssertionError("Wheel runtime version differs from metadata")
        if doctor["credentials"]["fal_key_present"] or doctor["credentials"][
                "anthropic_key_present"]:
            raise AssertionError("Clean smoke environment unexpectedly has API keys")
        if doctor["cloud_inference_performed"] or doctor["gpu_benchmark_performed"]:
            raise AssertionError("Smoke test must never invoke inference")
        if "Valid: smoke-batch, 1 assets" not in outputs[2]:
            raise AssertionError("Packaged CLI validate failed")
        archive = (area / "workspace" / "batches" / "smoke-batch" /
                   "prehnite-smoke-batch.zip")
        if not archive.is_file():
            raise AssertionError("Clean install did not export an archive")
        with zipfile.ZipFile(archive) as result:
            if result.testzip() is not None:
                raise AssertionError("Archive CRC failed")
            if "photos/example-001.png" not in result.namelist():
                raise AssertionError("Synthetic selected asset missing")
        return {"platform": platform.system(), "python": platform.python_version(),
                "package_version": __version__, "wheel": wheels[0].name,
                "sdist": sources[0].name,
                "commands": ["init", "doctor", "validate", "run"],
                "clean_venv": True, "billed_inference_calls": 0,
                "gpu_hardware_benchmarked": False,
                "publication_or_tag_created": False}


if __name__ == "__main__":
    print(json.dumps(smoke(), indent=2))
