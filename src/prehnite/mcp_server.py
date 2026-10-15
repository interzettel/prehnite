"""Local stdio MCP; uses an independent, persistent batch worker."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

def server():
    from mcp.server.fastmcp import FastMCP
    from .manifest import load_manifest, load_profile, validate_job
    from .schema import Asset
    from .store import Journal
    from .reporting import export_report, package
    from .registry import list_models

    mcp = FastMCP("Prehnite")
    home = Path(os.environ.get("PREHNITE_HOME", "./prehnite-home")).resolve()
    requests, profiles = home/"requests", home/"profiles"
    workspace, inputs = home/"workspace", home/"inputs"
    for p in (requests, profiles, workspace, inputs):
        p.mkdir(parents=True, exist_ok=True)

    def allowed(root: Path, filename: str) -> Path:
        if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
            raise ValueError("Only files within allowlisted directories are accepted")
        path = (root/filename).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("File missing or outside approved directory")
        return path

    @mcp.tool()
    def list_capabilities() -> list[dict]:
        """List implemented inference model adapters."""
        return list_models()

    @mcp.tool()
    def validate_manifest(manifest_filename: str, profile_filename: str) -> dict:
        """Validate a staged batch without performing inference."""
        m = load_manifest(allowed(requests, manifest_filename))
        p = load_profile(allowed(profiles, profile_filename))
        validate_job(m, p, inputs)
        return {"valid": True, "id": m.id, "assets": len(m.assets),
                "paid_allowed": p.costs.allow_paid, "budget_usd": p.costs.max_usd}

    @mcp.tool()
    def estimate_cost(manifest_filename: str, profile_filename: str) -> dict:
        """Estimate billable calls and hypothetical spend without executing them."""
        from .costing import estimate_costs
        m = load_manifest(allowed(requests, manifest_filename))
        p = load_profile(allowed(profiles, profile_filename))
        validate_job(m, p, inputs)
        return estimate_costs(m, p)

    @mcp.tool()
    def submit_batch(manifest_filename: str, profile_filename: str) -> dict:
        """Start a batch subprocess, returning a durable job identifier."""
        info = validate_manifest(manifest_filename, profile_filename)
        Asset.check_id(info["id"])
        pidfile = workspace/("prehnite-" + info["id"] + ".pid")
        if pidfile.is_file():
            try:
                pid = int(pidfile.read_text())
                os.kill(pid, 0)
                return {"job_id": info["id"], "status": "already_running"}
            except (ValueError, OSError):
                pass
        with (workspace/("prehnite-" + info["id"] + ".log")).open("ab") as f:
            worker = subprocess.Popen(
                [sys.executable, "-m", "prehnite.cli", "run",
                 str(allowed(requests, manifest_filename)), "--profile",
                 str(allowed(profiles, profile_filename)), "--workspace",
                 str(workspace), "--inputs", str(inputs)],
                stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                start_new_session=(os.name != "nt"))
        pidfile.write_text(str(worker.pid))
        return {"job_id": info["id"], "status": "started", "pid": worker.pid}

    @mcp.tool()
    def get_job_status(job_id: str) -> dict:
        """Return durable per-asset statuses and cost reservation."""
        Asset.check_id(job_id)
        if not (workspace/"batches"/job_id/"state.sqlite3").is_file():
            return {"job_id": job_id, "status": "unknown"}
        j = Journal(workspace, job_id)
        try:
            return {"job_id": job_id, "results": j.fact("results", {}),
                    "reserved_usd": j.reserved(), "operations": len(j.tasks())}
        finally:
            j.close()

    @mcp.tool()
    def export_batch(job_id: str) -> dict:
        """Create an archive with accepted outputs only."""
        Asset.check_id(job_id)
        if not (workspace/"batches"/job_id/"state.sqlite3").is_file():
            raise ValueError("Unknown job")
        j = Journal(workspace, job_id)
        try:
            export_report(j)
            return {"archive": str(package(j))}
        finally:
            j.close()
    return mcp

def main():
    server().run(transport="stdio")

if __name__ == "__main__":
    main()
