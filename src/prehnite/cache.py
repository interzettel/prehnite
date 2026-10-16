"""Immutable, opt-in, privacy-scoped stage cache; never stores prompts or API keys.

Cache scopes are local filesystem isolation labels, not cryptographic access
controls. Permissions and tenant separation remain the workspace owner's duty.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from pathlib import Path

from PIL import Image

from ._version import __version__
from .artifacts import ArtifactIntegrityError, temporary_sibling
from .images import image_info
from .schema import CachePolicy, Endpoint

MAX_CACHE_IMAGE_BYTES = 100_000_000
CACHE_SCHEMA = 1


class CacheIntegrityError(ArtifactIntegrityError):
    """An existing immutable cache record is corrupt or untrustworthy."""


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


class StageCache:
    def __init__(self, workspace: Path, policy: CachePolicy):
        if not policy.enabled or not policy.namespace:
            raise ValueError("Cannot create a disabled or unscoped cache")
        self.policy = policy
        self.scope_hash = hashlib.sha256(policy.namespace.encode("utf-8")).hexdigest()
        self.root = (Path(workspace).resolve() / ".prehnite-cache" /
                     self.scope_hash)

    def key(self, stage: str, endpoint: Endpoint, request: dict) -> str | None:
        if stage not in ("generation", "upscaling", "segmentation"):
            return None
        if endpoint.provider == "disabled":
            return None
        if endpoint.provider in ("fal", "anthropic") and not self.policy.allow_paid:
            return None
        revision = self.policy.model_revisions.get(stage)
        if endpoint.provider != "demo" and not revision:
            # Hosted endpoints and owner workflows can silently change behind
            # a model alias. No revision pin => no reuse across batches.
            return None
        revision = revision if revision else ("bundled-demo-" + __version__)
        payload = {
            "schema": CACHE_SCHEMA, "scope_hash": self.scope_hash,
            "pipeline_version": __version__, "stage": stage,
            "provider": endpoint.provider, "model": endpoint.model,
            "model_revision": revision, "endpoint_options": endpoint.options,
            "request": request,
        }
        return hashlib.sha256(_canonical(payload)).hexdigest()

    def _path(self, key: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("Invalid cache key")
        return self.root / key[:2] / (key + ".zip")

    def _read(self, key: str) -> bytes | None:
        file = self._path(key)
        if not file.exists():
            return None
        if file.is_symlink():
            raise CacheIntegrityError("Cache record must not be a symlink")
        try:
            with zipfile.ZipFile(file) as archive:
                if set(archive.namelist()) != {"artifact.png", "receipt.json"}:
                    raise CacheIntegrityError("Unexpected cache record entries")
                metadata = archive.getinfo("artifact.png")
                if metadata.file_size > MAX_CACHE_IMAGE_BYTES:
                    raise CacheIntegrityError("Cache image exceeds size limit")
                receipt_raw = archive.read("receipt.json")
                if len(receipt_raw) > 4096:
                    raise CacheIntegrityError("Cache receipt exceeds size limit")
                receipt = json.loads(receipt_raw)
                if not isinstance(receipt, dict):
                    raise CacheIntegrityError("Cache receipt must be an object")
                if receipt != {
                    "schema": CACHE_SCHEMA,
                    "key": key,
                    "scope_hash": self.scope_hash,
                    "sha256": receipt.get("sha256"),
                }:
                    raise CacheIntegrityError("Cache key/scope receipt mismatch")
                data = archive.open("artifact.png").read(MAX_CACHE_IMAGE_BYTES + 1)
                if len(data) > MAX_CACHE_IMAGE_BYTES:
                    raise CacheIntegrityError("Cache payload exceeds size limit")
                if hashlib.sha256(data).hexdigest() != receipt["sha256"]:
                    raise CacheIntegrityError("Cache artifact digest mismatch")
                return data
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
            if isinstance(exc, CacheIntegrityError):
                raise
            raise CacheIntegrityError("Cannot validate immutable cache record") from exc

    def restore(self, key: str, destination: Path) -> dict | None:
        data = self._read(key)
        if data is None:
            return None
        destination = Path(destination)
        with temporary_sibling(destination) as temp:
            temp.write_bytes(data)
            try:
                with Image.open(temp) as im:
                    if im.width * im.height > 24_000_000:
                        raise CacheIntegrityError("Cached image exceeds pixel limit")
                    im.load()
                info = image_info(temp)
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                raise CacheIntegrityError("Cached image is not decodable") from exc
            os.replace(temp, destination)
        return info

    def store(self, key: str, image: Path) -> bool:
        """Insert a single immutable ZIP. Existing content cannot be overwritten."""
        target = self._path(key)
        if target.exists():
            self._read(key)  # Corruption is not treated as a cache miss.
            return False
        info = image_info(image)
        if image.stat().st_size > MAX_CACHE_IMAGE_BYTES:
            raise ValueError("Stage result too large to cache")
        payload = image.read_bytes()
        if hashlib.sha256(payload).hexdigest() != info["sha256"]:
            raise CacheIntegrityError("Stage changed during cache snapshot")
        target.parent.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": CACHE_SCHEMA, "key": key,
            "scope_hash": self.scope_hash, "sha256": info["sha256"],
        }
        with temporary_sibling(target) as temp:
            with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("receipt.json", _canonical(receipt))
                archive.writestr("artifact.png", payload)
            try:
                # Link only when absent: competing batches with the same key
                # cannot silently replace each other's immutable result.
                os.link(temp, target)
                return True
            except FileExistsError:
                self._read(key)
                return False
