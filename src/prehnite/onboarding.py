"""Safe, zero-cost first-run setup and opt-in local health checks."""
from __future__ import annotations

import importlib.util
import os
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx
import yaml

from .comfy import _base_url
from .schema import Endpoint, Manifest, Profile


def init_example(destination: Path, batch_id: str = "starter-batch") -> tuple[Path, Path]:
    """Create validated demo-only YAML files, never replacing user content."""
    manifest = Manifest.model_validate({
        "id": batch_id,
        "assets": [{
            "id": "example-001",
            "prompt": "An ordinary desk lamp on a quiet studio table",
            "aspect_ratio": "3:4",
            "target_size": [192, 256],
            "output": {"image": "photos/example-001.png"},
        }],
    })
    profile = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "segmentation": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified", "maximum_attempts": 1},
        "costs": {"allow_paid": False, "allow_cloud_uploads": False,
                  "max_usd": 0.0, "estimates_usd": {}},
    })
    destination = Path(destination)
    outputs = (
        (destination / "manifest.yaml",
         yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False)),
        (destination / "profile.yaml",
         "# Free synthetic test images. No API account or GPU required.\n"
         + yaml.safe_dump(profile.model_dump(mode="json"), sort_keys=False)),
    )
    if any(p.exists() or p.is_symlink() for p, _ in outputs):
        raise FileExistsError(
            "manifest.yaml or profile.yaml already exists; choose another --destination"
        )
    destination.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for path, text in outputs:
            # Exclusive create also protects against a race with another process.
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                created.append(path)
                stream.write(text)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return (outputs[0][0], outputs[1][0])


def _extra_available(package: str) -> bool:
    try:
        return importlib.util.find_spec(package) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def doctor_report(*, check_comfyui: bool = False,
                  comfyui_url: str = "http://127.0.0.1:8188") -> dict:
    """No network by default; optional ComfyUI check is loopback-only.

    Never return or log authentication values, model prompts or private files.
    Presence of a key is not proof that a service/account is working.
    """
    try:
        app_version = version("prehnite")
    except PackageNotFoundError:
        from ._version import __version__ as app_version

    result = {
        "runtime": {
            "python": ".".join(str(n) for n in sys.version_info[:3]),
            "platform": platform.system(),
            "prehnite_version": app_version,
        },
        "credentials": {
            "fal_key_present": bool(os.getenv("FAL_KEY")),
            "anthropic_key_present": bool(os.getenv("ANTHROPIC_API_KEY")),
            "validation": "presence_only_not_authentication",
        },
        "optional_clients": {
            "fal_client_installed": _extra_available("fal_client"),
            "anthropic_installed": _extra_available("anthropic"),
        },
        "local_comfyui": {"connection": "not_checked",
                          "model_execution": "not_tested"},
        "cloud_inference_performed": False,
        "gpu_benchmark_performed": False,
    }
    if check_comfyui:
        endpoint = Endpoint(provider="comfyui", model="local-healthcheck",
                            options={"base_url": comfyui_url})
        address = _base_url(endpoint)  # Strict localhost/127.0.0.1 allowlist.
        result["local_comfyui"]["connection"] = "unreachable"
        try:
            with httpx.Client(timeout=2, trust_env=False) as client:
                response = client.get(address + "/system_stats")
                response.raise_for_status()
                payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("system"), dict):
                result["local_comfyui"]["connection"] = "reachable"
            else:
                result["local_comfyui"]["connection"] = "unexpected_response"
        except (httpx.HTTPError, ValueError, OSError):
            # Do not expose arbitrary local server error messages or file paths.
            pass
    return result
