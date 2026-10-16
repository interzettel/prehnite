"""Reproducible, $0 offline 90-slot batch exercise for Prehnite issue #41.

Uses PIL synthetic source images and the existing demo provider; NO network,
API tokens, model downloads, GPU or provider invoices. Worker crash is a real
subprocess os._exit() to test durable SQLite and OS-lock recovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import yaml
from PIL import Image

from prehnite.engine import Engine
from prehnite.manifest import load_manifest, load_profile
from prehnite.mcp_jobs import JobManager
from prehnite.reporting import package
from prehnite.store import Journal

COUNT = 90
GENERATED = 30
CUTOUTS = 18
RATIOS = (
    ("1:1", (128, 128)),
    ("3:4", (144, 192)),
    ("9:16", (108, 192)),
    ("16:9", (192, 108)),
    ("4:3", (192, 144)),
)
BATCH_ID = "offline-90-v1"


def prepare(home: Path) -> JobManager:
    manager = JobManager(home)
    manifest = {"id": BATCH_ID, "assets": []}
    for n in range(1, COUNT + 1):
        ratio, size = RATIOS[(n - 1) % len(RATIOS)]
        asset = {
            "id": f"asset-{n:03d}",
            "aspect_ratio": ratio,
            "target_size": list(size),
            "seed": n,
            "targets": ["subject"] if n % 5 == 0 else [],
            "output": {
                "image": f"photos/{n:03d}.png",
                "cutouts": {"subject": f"cutouts/{n:03d}-subject.png"}
                if n % 5 == 0 else {},
            },
        }
        if n <= COUNT - GENERATED:
            filename = f"source-{n:03d}.png"
            source = manager.inputs / filename
            Image.new("RGB", size, (n % 200 + 20, n % 110 + 50, 145)).save(source)
            asset["source"] = filename
        else:
            asset["prompt"] = f"Offline synthetic fixture for slot {n:03d}; not AI art"
        manifest["assets"].append(asset)
    profile = {
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "segmentation": {"provider": "demo", "model": "simple-mask"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified", "maximum_attempts": 2},
        "costs": {"allow_paid": False, "allow_cloud_uploads": False,
                  "max_usd": 0.0, "estimates_usd": {}},
    }
    (manager.requests / "offline90.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=True), encoding="utf-8"
    )
    (manager.profiles / "offline90.yaml").write_text(
        yaml.safe_dump(profile, sort_keys=True), encoding="utf-8"
    )
    return manager


def engine_for(manager: JobManager, token: str | None = None) -> Engine:
    manifest = load_manifest(manager.requests / "offline90.yaml")
    profile = load_profile(manager.profiles / "offline90.yaml")
    return Engine(manifest, profile, manager.workspace, manager.inputs, job_token=token)


def launch_token(manager: JobManager) -> str:
    j = Journal(manager.workspace, BATCH_ID)
    try:
        return j.job_record()["token"]
    finally:
        j.close()


def crash_worker(manager: JobManager, token: str) -> None:
    """Only invoked in a subprocess; os._exit simulates actual process death."""
    engine = engine_for(manager, token)
    process = engine.process

    def injected(asset):
        if asset.id == "asset-066":
            os._exit(73)
        return process(asset)

    engine.process = injected
    try:
        engine.run()
    finally:
        engine.journal.close()


def _fake_spawn(*args, **kwargs):
    """Persist launch controls without allowing an uncontrolled worker race."""
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.STDOUT
    return None


def expected_projection() -> list[dict]:
    """Explicitly hypothetical API quotes, never a provider price or invoice."""
    projected_calls = GENERATED + 3  # Assume 10% generated-image retries.
    bands = (
        ("low", Decimal("0.02"), Decimal("0.003")),
        ("mid", Decimal("0.05"), Decimal("0.01")),
        ("high", Decimal("0.10"), Decimal("0.025")),
    )
    return [
        {
            "scenario": name,
            "basis": "hypothetical_unit_prices_not_provider_quotes",
            "assumed_generation_calls": projected_calls,
            "assumed_segmentation_calls": CUTOUTS,
            "usd_per_generation": str(gen),
            "usd_per_segment": str(seg),
            "hypothetical_usd_total": str(projected_calls * gen + CUTOUTS * seg),
            "excludes": ["judging", "upscaling", "hardware", "labor", "tax",
                         "provider_overhead", "real_invoices"],
        }
        for name, gen, seg in bands
    ]


def run_benchmark(home: Path, preview_file: Path | None = None,
                  *, parquet: bool = False,
                  parquet_output: Path | None = None) -> dict:
    manager = prepare(home)
    # Fake *only launch*, actual Engine workers execute independently below.
    # This eliminates timing races without weakening real OS run-lock tests.
    with patch("prehnite.mcp_jobs.subprocess.Popen", _fake_spawn):
        assert manager.submit("offline90.yaml", "offline90.yaml")["status"] == "launching"
    initial_token = launch_token(manager)
    engine = engine_for(manager, initial_token)
    original_process = engine.process

    def first_phase(asset):
        if asset.id == "asset-010":
            # Controlled failure, then retry on explicit resume.
            raise RuntimeError("INJECTED_OFFLINE_TEST_FAILURE")
        result = original_process(asset)
        if asset.id == "asset-030":
            assert manager.control(BATCH_ID, "pause")["status"] == "pause_requested"
        return result

    engine.process = first_phase
    try:
        partial = engine.run()
        assert partial["job_status"] == "paused"
        first_results = engine.journal.fact("results", {})
        assert len(first_results) == 30
        assert first_results["asset-010"]["status"] == "error"
        assert sum(r["status"] == "accepted" for r in first_results.values()) == 29
        before = {r["task_key"]: r for r in engine.journal.tasks()}
    finally:
        engine.journal.close()
    assert JobManager(home).status(BATCH_ID)["status"] == "paused"

    with patch("prehnite.mcp_jobs.subprocess.Popen", _fake_spawn):
        assert manager.resume(BATCH_ID)["status"] == "launching"
    second_token = launch_token(manager)

    # A genuine process crash midway through the 90-slot workload. The parent
    # must discover interrupted state via the released kernel run lock.
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()),
         "--crash-worker", "--home", str(home), "--token", second_token],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=180, check=False,
    )
    assert proc.returncode == 73, (
        f"Expected injected process crash (73); got {proc.returncode}: "
        f"{proc.stderr.decode(errors='replace')[-700:]}"
    )
    interrupted = JobManager(home).status(BATCH_ID)
    assert interrupted["status"] == "interrupted", interrupted
    assert interrupted["processed_assets"] == 65, interrupted
    assert interrupted["accepted_assets"] == 65, interrupted

    with patch("prehnite.mcp_jobs.subprocess.Popen", _fake_spawn):
        assert manager.resume(BATCH_ID)["status"] == "launching"
    engine = engine_for(manager, launch_token(manager))
    try:
        final = engine.run()
        assert manager.status(BATCH_ID)["status"] == "completed"
        result_rows = final["asset_results"]
        assert len(result_rows) == COUNT
        assert all(r["status"] == "accepted" for r in result_rows.values())
        assert sum(len(r["outputs"]) - 1 for r in result_rows.values()) == CUTOUTS
        tasks = engine.journal.tasks()
        assert len({r["task_key"] for r in tasks}) == len(tasks)
        for key, item in before.items():
            final_row = engine.journal.get(key)
            assert final_row["status"] == item["status"]
            assert final_row["reserved_usd"] == item["reserved_usd"]
        assert final["cost_estimated_or_reserved_usd"] == 0.0
        e = final["economics"]
        assert e["accepted_assets"] == COUNT
        analytics = final["analytics"]
        assert analytics["schema_version"] == 1
        assert analytics["required_assets"] == COUNT
        assert analytics["accepted_assets"] == COUNT
        assert analytics["asset_status_counts"]["pending"] == 0
        assert analytics["asset_status_counts"]["error"] == 0
        assert analytics["accepted_percent_of_required"] == 100.0
        assert sum(x["requested"] for x in analytics["input_mode"]) == COUNT
        assert sum(x["accepted"] for x in analytics["aspect_ratio"]) == COUNT
        assert analytics["actual_invoiced_usd"] is None
        assert analytics["retry_distribution"]["one_invocation"] == 48
        assert analytics["retry_distribution"]["no_invocation_recorded"] == 0
        assert e["reserved_usd_total"] == 0.0
        assert e["actual_invoiced_usd_total"] is None
        assert e["attempts_without_finished_timing"] == 0
        assert e["retry_attempts"] == 0
        assert e["attempts_started"] == len(tasks)
        archive = engine.journal.root / f"prehnite-{BATCH_ID}.zip"
        first_bytes = archive.read_bytes()
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            expected_images = {
                f"photos/{n:03d}.png" for n in range(1, COUNT + 1)
            } | {
                f"cutouts/{n:03d}-subject.png"
                for n in range(1, COUNT + 1) if n % 5 == 0
            }
            assert expected_images <= set(names)
            assert {"_prehnite/analytics.json", "_prehnite/analytics.csv"} <= set(names)
            assert json.loads(z.read("_prehnite/analytics.json")) == analytics
            assert b"schema_version,section,group,measure,value,unit" in z.read(
                "_prehnite/analytics.csv")
            gallery = z.read("_prehnite/gallery.html")
            assert b"BATCH INTELLIGENCE / V1" in gallery
            assert b"Production snapshot" in gallery
            assert b"connect-src 'none'" in gallery
            assert len(expected_images) == COUNT + CUTOUTS
            assert names == sorted(names)
            assert z.testzip() is None
            receipt = json.loads(z.read("_prehnite/archive-manifest.json"))
            assert set(receipt["sha256"]) == set(names) - {
                "_prehnite/archive-manifest.json"
            }
            for name, digest in receipt["sha256"].items():
                assert hashlib.sha256(z.read(name)).hexdigest() == digest
            provenance = json.loads(z.read("_prehnite/provenance.json"))
            assert len(provenance["inputs_and_outputs"]) == COUNT
            assert provenance["quality_certification"].startswith("none")
        # Running a completed batch must reuse all stages and be byte-stable.
        attempts_before = len(engine.journal.attempts())
        # Direct CLI-mode replay validates idempotence after a completed
        # MCP job without trying to re-enter a terminal launch token.
        replay = engine_for(manager)
        try:
            resumed_report = replay.run()
            assert len(replay.journal.attempts()) == attempts_before
            assert resumed_report["economics"]["accepted_assets"] == COUNT
            assert package(replay.journal).read_bytes() == first_bytes
        finally:
            replay.journal.close()
        assert not any("INJECTED_OFFLINE_TEST_FAILURE" in str(row)
                       for row in resumed_report["asset_results"].values())
        if preview_file is not None:
            # Safe for *this fixed synthetic fixture only*. Never upload an
            # arbitrary user's gallery; it embeds thumbnail pixels.
            preview_file.parent.mkdir(parents=True, exist_ok=True)
            gallery_html = (engine.journal.root / "gallery.html").read_text(
                encoding="utf-8")
            assert "<script" not in gallery_html
            gallery_html = gallery_html.replace(
                "Prehnite / offline production dashboard</h1>",
                "Prehnite / offline production dashboard · SYNTHETIC DEMO</h1>",
                1)
            preview_file.write_text(gallery_html, encoding="utf-8")
        parquet_verified = False
        if parquet:
            import pyarrow.parquet as pq
            from prehnite.parquet_export import DATASETS, write_parquet_exports
            manifest = engine.journal.fact("manifest", {})
            results = engine.journal.fact("results", {})
            record = write_parquet_exports(
                engine.journal.root, final["analytics"], manifest, results)
            assert record["datasets"][DATASETS[1]]["rows"] == COUNT
            slot_table = pq.read_table(engine.journal.root / DATASETS[1])
            assert slot_table.num_rows == COUNT
            assert sum(slot_table.column("requested_cutouts").to_pylist()) == CUTOUTS
            assert sum(slot_table.column("selected_outputs").to_pylist()) == COUNT + CUTOUTS
            parquet_zip = package(engine.journal, include_parquet=True)
            with zipfile.ZipFile(parquet_zip) as z:
                for name in DATASETS:
                    assert "_prehnite/" + name in z.namelist()
                assert "_prehnite/parquet-manifest.json" in z.namelist()
                assert z.testzip() is None
                receipt = json.loads(z.read("_prehnite/archive-manifest.json"))
                for name in DATASETS:
                    item = "_prehnite/" + name
                    assert hashlib.sha256(z.read(item)).hexdigest() == receipt["sha256"][item]
            if parquet_output is not None:
                # Never export real user data through this test script: prepare()
                # creates only fresh synthetic fixtures inside temporary home.
                parquet_output.mkdir(parents=True, exist_ok=True)
                for name in (*DATASETS, "parquet-manifest.json",
                             "analytics.json", "analytics.csv"):
                    shutil.copyfile(engine.journal.root / name, parquet_output / name)
            parquet_verified = True
        return {
            "schema_version": 1,
            "scenario": "synthetic_offline_no_paid_inference",
            "status": "passed",
            "required_slots": COUNT,
            "source_slots": COUNT - GENERATED,
            "demo_generated_slots": GENERATED,
            "requested_cutouts": CUTOUTS,
            "injected_failure_slots": 1,
            "paused_after_processed_slots": 30,
            "crashed_after_processed_slots": 65,
            "final_accepted_slots": e["accepted_assets"],
            "final_asset_status_counts": e["asset_status_counts"],
            "stage_operations": len(tasks),
            "observed_stage_attempts": e["attempts_started"],
            "provider_invoice_verified": False,
            "reserved_spend_usd": e["reserved_usd_total"],
            "zip_image_entries": len(expected_images),
            "archive_sha256": hashlib.sha256(first_bytes).hexdigest(),
            "replay_byte_identical": True,
            "parquet_opt_in_verified": parquet_verified,
            "quote_scenarios": expected_projection(),
            "limitations": [
                "synthetic_inputs_not_human_verified_visual_quality",
                "no_actual_remote_provider_or_gpu_inference",
                "local_process_recovery_not_remote_billing_reconciliation",
            ],
        }
    finally:
        engine.journal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path)
    parser.add_argument("--token", type=str)
    parser.add_argument("--crash-worker", action="store_true")
    parser.add_argument("--result-file", type=Path)
    parser.add_argument("--parquet", action="store_true",
                        help="Also verify opt-in Parquet datasets; requires prehnite[parquet]")
    parser.add_argument("--parquet-output", type=Path,
                        help="Copy only synthetic aggregate Parquet evidence to this folder")
    parser.add_argument("--preview-file", type=Path,
                        help="Write a safe embedded HTML preview (synthetic demo only)")
    args = parser.parse_args()
    if args.parquet_output is not None and not args.parquet:
        parser.error("--parquet-output requires --parquet")
    if args.crash_worker:
        if args.home is None or args.token is None:
            parser.error("Crash worker needs --home and --token")
        crash_worker(JobManager(args.home), args.token)
        raise AssertionError("Injected worker should have exited with status 73")
    with tempfile.TemporaryDirectory(prefix="prehnite-benchmark-90-") as directory:
        report = run_benchmark(Path(directory), args.preview_file,
                               parquet=args.parquet,
                               parquet_output=args.parquet_output)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.result_file:
        args.result_file.parent.mkdir(parents=True, exist_ok=True)
        args.result_file.write_text(serialized, encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
