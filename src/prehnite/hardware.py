"""Offline, read-only hardware observation; never a model feasibility certificate."""
from __future__ import annotations

import csv
import ctypes
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def _linux_ram() -> dict[str, Any]:
    """Linux: MemAvailable approximates available RAM, not guaranteed allocatable."""
    try:
        data = Path("/proc/meminfo").read_text(encoding="ascii")
        matches = dict((key, int(value) * 1024) for key, value in
                       re.findall(r"^(MemTotal|MemAvailable):\s*(\d+)\s+kB\s*$", data, re.M))
        total = matches.get("MemTotal")
        available = matches.get("MemAvailable")
        if total is None or total <= 0 or (available is not None and available > total):
            raise ValueError("invalid /proc/meminfo")
        return {"total_bytes": total, "available_bytes": available,
                "source": "/proc/meminfo", "status": "observed"}
    except (OSError, UnicodeError, ValueError):
        return {"total_bytes": None, "available_bytes": None,
                "source": "/proc/meminfo", "status": "unavailable"}


def _windows_ram() -> dict[str, Any]:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in (
                "ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
                "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")
        ]
    try:
        memory = MemoryStatus()
        memory.dwLength = ctypes.sizeof(MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            raise OSError("GlobalMemoryStatusEx unsuccessful")
        total, available = int(memory.ullTotalPhys), int(memory.ullAvailPhys)
        if not total or available > total:
            raise ValueError("Invalid Windows memory report")
        report = {"total_bytes": total, "available_bytes": available,
                  "source": "GlobalMemoryStatusEx", "status": "observed"}
        # On Windows these are system commit limits, not pagefile disk capacity.
        limit = int(memory.ullTotalPageFile)
        remaining = int(memory.ullAvailPageFile)
        if limit > 0 and 0 <= remaining <= limit:
            report.update({"commit_limit_bytes": limit,
                           "commit_used_bytes": limit - remaining,
                           "commit_source": "GlobalMemoryStatusEx",
                           "commit_status": "observed"})
        else:
            report["commit_status"] = "unavailable"
        return report
    except (AttributeError, OSError, ValueError):
        return {"total_bytes": None, "available_bytes": None,
                "source": "GlobalMemoryStatusEx", "status": "unavailable"}


def _mac_ram() -> dict[str, Any]:
    try:
        proc = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                              text=True, timeout=3, check=False)
        total = int(proc.stdout.strip()) if proc.returncode == 0 else 0
        if total <= 0:
            raise ValueError("Invalid sysctl hw.memsize")
        return {"total_bytes": total, "available_bytes": None,
                "source": "sysctl hw.memsize", "status": "observed"}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"total_bytes": None, "available_bytes": None,
                "source": "sysctl hw.memsize", "status": "unavailable"}


def _nvidia_gpus() -> dict[str, Any]:
    """Query accessible NVIDIA adapters only; do not interpret missing CLI as no GPU."""
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"status": "unavailable", "source": "nvidia-smi",
                "reason": "nvidia-smi not found; AMD, Intel and Apple GPUs not probed",
                "devices": []}
    try:
        result = subprocess.run(
            [executable, "--query-gpu=name,driver_version,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode != 0:
            raise ValueError("NVIDIA query returned an error")
        rows = list(csv.reader(result.stdout.splitlines()))
        if not rows:
            raise ValueError("Empty NVIDIA GPU query")
        devices = []
        for index, row in enumerate(rows):
            if len(row) != 4 or any(not cell.strip() for cell in row):
                raise ValueError("Malformed NVIDIA query row")
            name, driver, total_text, free_text = [value.strip() for value in row]
            if len(name) > 128 or len(driver) > 64:
                raise ValueError("Invalid NVIDIA device metadata")
            def mib(value: str) -> int | None:
                if not value.isdecimal():
                    return None
                return int(value) * 1024 * 1024
            total = mib(total_text)
            free = mib(free_text)
            if total is not None and (total <= 0 or (free is not None and free > total)):
                raise ValueError("Invalid reported NVIDIA device memory")
            devices.append({"index": index, "name": name,
                            "driver_version": driver, "vram_total_bytes": total,
                            "vram_free_bytes": free,
                            "vram_status": "observed" if total is not None else "unknown"})
        return {"status": "observed", "source": "nvidia-smi", "devices": devices}
    except (OSError, ValueError, subprocess.TimeoutExpired, UnicodeError):
        return {"status": "unavailable", "source": "nvidia-smi",
                "reason": "NVIDIA query failed or returned unusable data", "devices": []}


def hardware_report() -> dict[str, Any]:
    """Diagnostic snapshot. No network access, model loading, downloads or writes."""
    system = platform.system()
    ram = {"Linux": _linux_ram, "Windows": _windows_ram,
           "Darwin": _mac_ram}.get(system, lambda: {
               "total_bytes": None, "available_bytes": None,
               "source": "unsupported-os", "status": "unavailable"})()
    try:
        disk = shutil.disk_usage(Path.home())
        disk_report = {"total_bytes": disk.total, "free_bytes": disk.free,
                       "source": "home-filesystem", "status": "observed"}
    except OSError:
        disk_report = {"total_bytes": None, "free_bytes": None,
                       "source": "home-filesystem", "status": "unavailable"}
    return {
        "schema_version": SCHEMA_VERSION,
        "os": {"system": system, "release": platform.release(),
               "architecture": platform.machine(), "source": "platform"},
        "python": {"version": platform.python_version(), "source": "platform"},
        "cpu": {"logical_count": os.cpu_count(), "source": "os.cpu_count",
                "status": "observed" if os.cpu_count() else "unknown"},
        "ram": ram, "disk": disk_report,
        "accelerators": {"nvidia": _nvidia_gpus(),
                         "other_gpu_backends": "not_probed"},
        "recipe_feasibility": "not_assessed",
        "performance_benchmarked": False,
        "model_checkpoints_verified": False,
        "hardware_tier_certified": False,
        "paid_calls_or_downloads": False,
    }
