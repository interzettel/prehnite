"""Hardware probes: deterministic synthetic fixtures, no network or actual GPU requirement."""
from __future__ import annotations

from types import SimpleNamespace

import prehnite.hardware as hw


def test_linux_meminfo_records_observed_bytes(monkeypatch):
    monkeypatch.setattr(hw.Path, "read_text", lambda self, **kwargs:
                        "MemTotal:       8192000 kB\nMemAvailable:   4096000 kB\n")
    memory = hw._linux_ram()
    assert memory == {"total_bytes": 8192000 * 1024,
                      "available_bytes": 4096000 * 1024,
                      "source": "/proc/meminfo", "status": "observed"}


def test_linux_ram_missing_or_inconsistent_is_not_guessed(monkeypatch):
    monkeypatch.setattr(hw.Path, "read_text", lambda self, **kwargs:
                        "MemTotal: 1000 kB\nMemAvailable: 1001 kB\n")
    assert hw._linux_ram()["status"] == "unavailable"


def test_nvidia_smi_missing_does_not_claim_absent_gpu(monkeypatch):
    monkeypatch.setattr(hw.shutil, "which", lambda _: None)
    gpu = hw._nvidia_gpus()
    assert gpu["status"] == "unavailable"
    assert gpu["devices"] == []
    assert "not probed" in gpu["reason"]


def test_nvidia_smi_reports_measured_mib_not_vram_support_tier(monkeypatch):
    monkeypatch.setattr(hw.shutil, "which", lambda _: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(hw.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout="NVIDIA RTX Test, 566.01, 8192, 6400\n", returncode=0))
    gpu = hw._nvidia_gpus()
    assert gpu["status"] == "observed"
    assert gpu["devices"][0]["vram_total_bytes"] == 8192 * 1024 * 1024
    assert gpu["devices"][0]["vram_free_bytes"] == 6400 * 1024 * 1024


def test_unavailable_nvidia_vram_not_converted_into_zero(monkeypatch):
    monkeypatch.setattr(hw.shutil, "which", lambda _: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(hw.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout="NVIDIA RTX Test, 566.01, N/A, N/A\n", returncode=0))
    device = hw._nvidia_gpus()["devices"][0]
    assert device["vram_total_bytes"] is None
    assert device["vram_status"] == "unknown"


def test_nvidia_failed_query_refuses_device_claim(monkeypatch):
    monkeypatch.setattr(hw.shutil, "which", lambda _: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(hw.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout="NVIDIA RTX Test, 566.01, 8192, 99999\n", returncode=0))
    gpu = hw._nvidia_gpus()
    assert gpu["status"] == "unavailable"
    assert gpu["devices"] == []


def test_mac_total_ram_keeps_free_ram_unknown(monkeypatch):
    monkeypatch.setattr(hw.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout="17179869184\n", returncode=0))
    mac = hw._mac_ram()
    assert mac["total_bytes"] == 17179869184
    assert mac["available_bytes"] is None


def test_unsupported_os_never_converts_unknown_ram_to_zero(monkeypatch):
    monkeypatch.setattr(hw.platform, "system", lambda: "FreeBSD")
    monkeypatch.setattr(hw.shutil, "which", lambda _: None)
    report = hw.hardware_report()
    assert report["ram"]["total_bytes"] is None
    assert report["recipe_feasibility"] == "not_assessed"
    assert report["hardware_tier_certified"] is False
    assert report["paid_calls_or_downloads"] is False
    assert report["performance_benchmarked"] is False


def test_no_probe_output_contains_sensitive_environment(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "secret-value")
    monkeypatch.setattr(hw.shutil, "which", lambda _: None)
    report = hw.hardware_report()
    assert "secret-value" not in str(report)
