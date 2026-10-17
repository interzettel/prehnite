"""Offline regression checks for release archive and version gates."""

import importlib.util
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("release_check", SCRIPTS / "check_release_artifacts.py")
release_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_check)


@pytest.mark.parametrize(
    "member",
    [
        "../secret.env",
        "/etc/passwd",
        "prehnite-0.1.0a1/.env",
        "prehnite-0.1.0a1/src/private/keys.json",
        "prehnite-0.1.0a1/checkpoints/model.safetensors",
        "prehnite-0.1.0a1/src/prehnite/secret.pem",
        "prehnite-0.1.0a1\\..\\secret",
    ],
)
def test_release_archive_rejects_unsafe_or_private_paths(member):
    with pytest.raises(ValueError):
        release_check.safe_names([member])


def test_release_archive_accepts_package_and_docs_paths():
    release_check.safe_names([
        "prehnite-0.1.0a1/README.md",
        "prehnite-0.1.0a1/docs/PYPI_README.md",
        "prehnite-0.1.0a1/src/prehnite/_version.py",
    ], prefix="prehnite-0.1.0a1/")


def test_canonical_version_is_read_from_source():
    from packaging.version import Version

    assert Version(release_check.source_version(SCRIPTS.parent)).major == 0


def test_release_checks_refuse_mismatched_source_version(tmp_path):
    with pytest.raises(ValueError, match="Source version"):
        release_check.check(tmp_path, "9.9.9")


def test_release_checks_refuse_dev_release_before_archive_handling(tmp_path):
    with pytest.raises(ValueError, match="Public alpha"):
        release_check.check(tmp_path, "0.1.0.dev0", require_public_release=True)


def test_release_checks_refuse_noncanonical_version(tmp_path):
    with pytest.raises(ValueError, match="canonical PEP 440"):
        release_check.check(tmp_path, "0.1.0A1")


def test_release_checks_refuse_partial_or_extra_archives(tmp_path):
    version = release_check.source_version(SCRIPTS.parent)
    (tmp_path / f"prehnite-{version}.tar.gz").write_bytes(b"not a complete artifact")
    with pytest.raises(ValueError, match="only wheel"):
        release_check.check(tmp_path, version)
