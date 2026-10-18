"""Read-only, operator-declared implicit ComfyUI dependency attestation.

No file is deserialized, imported, executed, installed or downloaded here.
ComfyUI custom nodes may load undeclared dependencies or different runtime
bytes: this is a static, bounded operator claim rather than runtime proof.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schema import relative_name

_SHA = re.compile(r"^[0-9a-f]{64}$")
_REV = re.compile(r"^[0-9a-f]{40,64}$")
_ROLE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_EXTENSIONS = {".pt", ".pth", ".safetensors", ".bin", ".onnx",
               ".gguf", ".json", ".txt", ".py", ".yaml", ".yml", ".model"}
_MAX_MANIFEST = 96 * 1024
_MAX_FILE = 32 * 1024 * 1024 * 1024


def _safe_https(value: str) -> str:
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname
            or parts.username or parts.password
            or parts.hostname.lower() in ("localhost", "127.0.0.1", "::1")
            or parts.fragment):
        raise ValueError("Dependency provenance requires an official HTTPS reference")
    return value


class FileClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: str
    kind: Literal["weight", "config", "tokenizer", "custom_node_source"]
    path: str
    sha256: str
    source_url: str
    source_revision: str
    license_url: str

    @model_validator(mode="after")
    def validate_claim(self) -> "FileClaim":
        if not _ROLE.fullmatch(self.role):
            raise ValueError("Invalid dependency role")
        if relative_name(self.path) != self.path:
            raise ValueError("Dependency path must be canonical and relative")
        if Path(self.path).suffix.lower() not in _EXTENSIONS:
            raise ValueError("Unsupported declared dependency extension")
        if not _SHA.fullmatch(self.sha256):
            raise ValueError("Dependency requires canonical SHA256")
        if not _REV.fullmatch(self.source_revision):
            raise ValueError("Dependency source_revision must be an immutable hex commit")
        _safe_https(self.source_url)
        _safe_https(self.license_url)
        if self.kind == "weight" and Path(self.path).suffix.lower() not in {
                ".pt", ".pth", ".safetensors", ".bin", ".onnx", ".gguf"}:
            raise ValueError("Weight role must reference a recognized model weight")
        return self


class DependencyManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    files: list[FileClaim] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def check_uniqueness(self) -> "DependencyManifest":
        names = [f.path.casefold() for f in self.files]
        roles = [f.role for f in self.files]
        if len(names) != len(set(names)) or len(roles) != len(set(roles)):
            raise ValueError("Duplicate dependency path or role")
        return self


def _stream_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_implicit_dependencies(manifest_path: Path, model_root: Path,
                                 expected_manifest_sha256: str) -> dict:
    """Verify all declared model/config/tokenizer bytes without model loading.

    The caller separately verifies that manifest_path belongs to its approved
    private input root. model_root is an explicit, user-owned trusted boundary.
    """
    if not _SHA.fullmatch(expected_manifest_sha256):
        raise ValueError("Invalid pinned implicit manifest digest")
    if not model_root.is_dir() or model_root.is_symlink():
        raise ValueError("Dependency root must be an existing real directory")
    root = model_root.resolve(strict=True)
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("Implicit manifest must be a regular non-symlink file")
    size = manifest_path.stat().st_size
    if not (0 < size <= _MAX_MANIFEST):
        raise ValueError("Implicit manifest file is empty or exceeds size limit")
    if _stream_sha(manifest_path) != expected_manifest_sha256:
        raise ValueError("Implicit dependency manifest SHA256 mismatch")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid implicit-dependency manifest JSON") from exc
    spec = DependencyManifest.model_validate(payload)
    sanitized = []
    for claim in spec.files:
        file = root
        for part in claim.path.split("/"):
            file = file / part
            if file.is_symlink():
                raise ValueError("Symlinked implicit dependency path refused")
        resolved = file.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError("Implicit dependency escapes approved root")
        bytes_count = resolved.stat().st_size
        if not (0 < bytes_count <= _MAX_FILE):
            raise ValueError("Implicit dependency is empty or oversized")
        if _stream_sha(resolved) != claim.sha256:
            raise ValueError(f"Implicit dependency SHA256 mismatch for role {claim.role}")
        sanitized.append({
            "role": claim.role, "kind": claim.kind,
            "sha256": claim.sha256, "bytes": bytes_count,
            "source_revision": claim.source_revision,
            "source_url": claim.source_url, "license_url": claim.license_url,
        })
    return {
        "schema_version": 1,
        "manifest_sha256": expected_manifest_sha256,
        "file_count": len(sanitized),
        "files": sorted(sanitized, key=lambda f: f["role"]),
        "coverage": "operator_declared_implicit_only",
        "graph_coverage_verified": False,
        "runtime_loaded_bytes_verified": False,
        "model_rights_independently_approved": False,
        "model_execution_tested": False,
    }
