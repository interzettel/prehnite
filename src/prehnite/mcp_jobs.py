"""Persistent MCP worker lifecycle without PID-based process identification.

Only local, pre-staged manifest/profile filenames are accepted. This manager
never kills processes. Operator commands are acknowledged at stage boundaries.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .engine import fingerprint
from .manifest import load_manifest, load_profile, validate_job
from .schema import Asset
from .store import Journal

LAUNCH_GRACE_SECONDS = 30


class JobManager:
    def __init__(self, home: Path):
        self.home = home.resolve()
        self.requests = self.home / "requests"
        self.profiles = self.home / "profiles"
        self.inputs = self.home / "inputs"
        self.workspace = self.home / "workspace"
        for directory in (self.requests, self.profiles, self.inputs, self.workspace):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def allowed(root: Path, filename: str) -> Path:
        if (not isinstance(filename, str) or not filename
                or "/" in filename or "\\" in filename or filename.startswith(".")
                or filename in (".", "..")):
            raise ValueError("Only bare filenames within allowlisted directories are accepted")
        path = (root / filename).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("File missing or outside approved directory")
        return path

    def validate(self, manifest_filename: str, profile_filename: str):
        manifest = load_manifest(self.allowed(self.requests, manifest_filename))
        profile = load_profile(self.allowed(self.profiles, profile_filename))
        validate_job(manifest, profile, self.inputs)
        return manifest, profile

    def _existing(self, job_id: str) -> Journal | None:
        Asset.check_id(job_id)
        if not (self.workspace / "batches" / job_id / "state.sqlite3").is_file():
            return None
        return Journal(self.workspace, job_id)

    @staticmethod
    def _fresh_launch(record: dict) -> bool:
        return record["status"] in ("launching", "pause_requested", "cancel_requested") and (
            time.time() - record["launched_at"] < LAUNCH_GRACE_SECONDS
        )

    def submit(self, manifest_filename: str, profile_filename: str, *,
               resume: bool = False) -> dict:
        manifest, profile = self.validate(manifest_filename, profile_filename)
        job_id = manifest.id
        Asset.check_id(job_id)
        fp = fingerprint(manifest, profile)
        journal = Journal(self.workspace, job_id)
        try:
            with journal.launch_exclusive():
                known_fp = journal.fact("configuration_sha256")
                if known_fp is not None and known_fp != fp:
                    raise ValueError("Batch ID reused with changed configuration")
                record = journal.job_record()
                if record and record["config_sha256"] != fp:
                    raise ValueError("Job configuration changed; choose a new batch ID")
                if journal.worker_active():
                    return {"job_id": job_id, "status": "already_running"}
                if record:
                    status = record["status"]
                    if status == "completed":
                        return {"job_id": job_id, "status": "completed"}
                    if status in ("cancelled", "cancel_requested"):
                        return {"job_id": job_id, "status": status,
                                "resume_allowed": False}
                    if self._fresh_launch(record):
                        return {"job_id": job_id, "status": "already_starting"}
                    if not resume:
                        return {"job_id": job_id,
                                "status": "paused" if status == "paused" else "needs_resume",
                                "resume_allowed": True}
                elif resume:
                    raise ValueError("No prior MCP job to resume")
                token = uuid.uuid4().hex
                journal.set_fact("requested_asset_count", len(manifest.assets))
                journal.job_launch(token, manifest_filename, profile_filename, fp)
                log_path = journal.root / "worker.log"
                command = [
                    sys.executable, "-m", "prehnite.cli", "run",
                    str(self.allowed(self.requests, manifest_filename)),
                    "--profile", str(self.allowed(self.profiles, profile_filename)),
                    "--workspace", str(self.workspace), "--inputs", str(self.inputs),
                    "--job-token", token,
                ]
                try:
                    with log_path.open("ab") as log:
                        subprocess.Popen(
                            command, stdin=subprocess.DEVNULL,
                            stdout=log, stderr=subprocess.STDOUT,
                            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                            start_new_session=(os.name != "nt"),
                        )
                except OSError:
                    # A failed spawn cannot leave a phantom running job.
                    journal.job_finish(token, "failed", "Worker process could not start")
                    raise
                return {"job_id": job_id, "status": "launching"}
        finally:
            journal.close()

    def resume(self, job_id: str) -> dict:
        journal = self._existing(job_id)
        if journal is None:
            raise ValueError("Unknown MCP job")
        try:
            record = journal.job_record()
            if record is None:
                raise ValueError("No MCP job launch record")
            manifest_filename = record["manifest_filename"]
            profile_filename = record["profile_filename"]
        finally:
            journal.close()
        return self.submit(manifest_filename, profile_filename, resume=True)

    def status(self, job_id: str) -> dict:
        journal = self._existing(job_id)
        if journal is None:
            return {"job_id": job_id, "status": "unknown"}
        try:
            record = journal.job_record()
            active = journal.worker_active()
            if not record:
                status = "external_running" if active else "unknown"
                current = None
            else:
                status = record["status"]
                current = record["current_asset"]
                if status == "running" and not active:
                    status = "interrupted"
                if status == "launching" and not active and not self._fresh_launch(record):
                    status = "interrupted"
            results = journal.fact("results", {})
            manifest = journal.fact("manifest", {})
            required = len(manifest.get("assets", [])) or journal.fact(
                "requested_asset_count", 0)
            completed = sum(r.get("status") == "accepted"
                            for r in results.values() if isinstance(r, dict))
            return {
                "job_id": job_id, "status": status,
                "worker_active": active,
                "current_asset": current,
                "required_assets": required,
                "accepted_assets": completed,
                "processed_assets": len(results),
                "asset_status_counts": {
                    name: sum(isinstance(r, dict) and r.get("status") == name
                              for r in results.values())
                    for name in ("accepted", "rejected", "failed_cutouts", "error")
                },
                "reserved_usd": journal.reserved(),
                "operations": len(journal.tasks()),
                "resume_allowed": status in ("paused", "interrupted", "failed",
                                             "pause_requested", "needs_resume"),
                "in_flight_stage_may_finish": (status in ("pause_requested", "cancel_requested")
                                               and active),
            }
        finally:
            journal.close()

    def control(self, job_id: str, command: str) -> dict:
        journal = self._existing(job_id)
        if journal is None:
            raise ValueError("Unknown MCP job")
        try:
            with journal.launch_exclusive():
                result = journal.job_command(command, worker_active=journal.worker_active())
                return {"job_id": job_id, **result}
        finally:
            journal.close()

    def export(self, job_id: str, *, include_parquet: bool = False) -> dict:
        from .reporting import export_report, package
        journal = self._existing(job_id)
        if journal is None:
            raise ValueError("Unknown MCP job")
        try:
            with journal.launch_exclusive():
                if journal.worker_active():
                    raise RuntimeError("Worker active: export only after safe stop or completion")
                record = journal.job_record()
                if record and record["status"] == "launching" and self._fresh_launch(record):
                    raise RuntimeError("Worker still launching: cannot export yet")
                export_report(journal)
                return {"archive": str(package(journal))}
        finally:
            journal.close()
