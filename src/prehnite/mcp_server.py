"""Local stdio MCP: durable detached jobs, cooperative stop and reconnect."""
from __future__ import annotations

import os
from pathlib import Path

from .mcp_jobs import JobManager


def server():
    from mcp.server.fastmcp import FastMCP

    from .costing import estimate_costs
    from .registry import list_models

    mcp = FastMCP("Prehnite")
    jobs = JobManager(Path(os.environ.get("PREHNITE_HOME", "./prehnite-home")))

    @mcp.tool()
    def list_capabilities() -> list[dict]:
        """List implemented inference model adapters."""
        return list_models()

    @mcp.tool()
    def validate_manifest(manifest_filename: str, profile_filename: str) -> dict:
        """Validate pre-staged files without inference or cloud uploads."""
        manifest, profile = jobs.validate(manifest_filename, profile_filename)
        return {"valid": True, "id": manifest.id, "assets": len(manifest.assets),
                "paid_allowed": profile.costs.allow_paid,
                "budget_usd": profile.costs.max_usd}

    @mcp.tool()
    def estimate_cost(manifest_filename: str, profile_filename: str) -> dict:
        """Estimate potential calls without running a batch."""
        manifest, profile = jobs.validate(manifest_filename, profile_filename)
        return estimate_costs(manifest, profile)

    @mcp.tool()
    def submit_batch(manifest_filename: str, profile_filename: str) -> dict:
        """Launch an allowlisted batch once; repeated submissions are idempotent."""
        return jobs.submit(manifest_filename, profile_filename)

    @mcp.tool()
    def get_job_status(job_id: str) -> dict:
        """Read persisted state; missing locks never imply a live worker."""
        return jobs.status(job_id)

    @mcp.tool()
    def pause_batch(job_id: str) -> dict:
        """Ask the worker to stop at its next safe stage boundary."""
        return jobs.control(job_id, "pause")

    @mcp.tool()
    def cancel_batch(job_id: str) -> dict:
        """Revoke continuation at the next safe boundary; do not kill a PID."""
        return jobs.control(job_id, "cancel")

    @mcp.tool()
    def resume_batch(job_id: str) -> dict:
        """Explicitly restart a paused/interrupted batch using staged files."""
        return jobs.resume(job_id)

    @mcp.tool()
    def export_batch(job_id: str, include_parquet: bool = False) -> dict:
        """Export accepted outputs when no worker is writing them."""
        return jobs.export(job_id, include_parquet=include_parquet)

    return mcp


def main():
    server().run(transport="stdio")


if __name__ == "__main__":
    main()
