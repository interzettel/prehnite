"""Optional Arrow/Parquet regression contracts; no provider calls or uploads."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from unittest import mock

import pytest
from typer.testing import CliRunner

from prehnite.analytics import build_analytics, write_analytics
from prehnite.cli import app
from prehnite.engine import Engine
from prehnite.mcp_jobs import JobManager
from prehnite.parquet_export import (
    MANIFEST_FILE, DATASETS, _metric_rows, verified_parquet_entries,
    write_parquet_exports,
)
from prehnite.reporting import export_report, package
from prehnite.schema import Manifest, Profile


def small_engine(tmp_path):
    manifest = Manifest.model_validate({
        "id": "private-batch", "assets": [
            {"id": "private-slot", "prompt": "PRIVATE PROMPT MUST STAY LOCAL",
             "target_size": [192, 256], "aspect_ratio": "3:4",
             "output": {"image": "image.png"}},
        ],
    })
    profile = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "judge": {"provider": "demo", "model": "technical"},
        "policy": {"uncertain": "accept_unverified"},
    })
    return Engine(manifest, profile, tmp_path)


def _arrow():
    pa = pytest.importorskip("pyarrow")
    return pa, pytest.importorskip("pyarrow.parquet")


def test_default_export_without_optional_dependency_keeps_original_zip(tmp_path):
    engine = small_engine(tmp_path)
    try:
        engine.run()
        original = package(engine.journal).read_bytes()
        with mock.patch.dict(sys.modules, {"pyarrow": None, "pyarrow.parquet": None}):
            result = export_report(engine.journal)
            assert "analytics" in result
            assert package(engine.journal).read_bytes() == original
            with pytest.raises(RuntimeError, match="prehnite\\[parquet\\]"):
                write_parquet_exports(
                    engine.journal.root, result["analytics"],
                    engine.journal.fact("manifest", {}),
                    engine.journal.fact("results", {}))
        assert not (engine.journal.root / DATASETS[0]).exists()
        with zipfile.ZipFile(package(engine.journal)) as z:
            assert not any(name.endswith(".parquet") for name in z.namelist())
    finally:
        engine.journal.close()


def test_opt_in_cli_parquet_roundtrip_digest_and_no_raw_private_values(tmp_path):
    pa, pq = _arrow()
    engine = small_engine(tmp_path)
    try:
        engine.run()
    finally:
        engine.journal.close()
    runner = CliRunner()
    response = runner.invoke(app, [
        "export", "private-batch", "--workspace", str(tmp_path), "--parquet"
    ])
    assert response.exit_code == 0, response.output
    root = tmp_path / "batches" / "private-batch"
    archive = root / "prehnite-private-batch.zip"
    with zipfile.ZipFile(archive) as z:
        entries = set(z.namelist())
        for name in (*DATASETS, MANIFEST_FILE):
            assert "_prehnite/" + name in entries
        receipt = json.loads(z.read("_prehnite/archive-manifest.json"))
        for name in (*DATASETS, MANIFEST_FILE):
            dest = "_prehnite/" + name
            assert hashlib.sha256(z.read(dest)).hexdigest() == receipt["sha256"][dest]
        assert z.testzip() is None
    metrics = pq.read_table(root / DATASETS[0])
    observations = pq.read_table(root / DATASETS[1])
    assert observations.num_rows == 1
    assert observations.column("slot_ordinal").to_pylist() == [1]
    assert observations.column("status").to_pylist() == ["accepted"]
    assert observations.schema.metadata[b"prehnite.schema_version"] == b"1"
    assert str(metrics.schema.field("value_usd").type) == "decimal128(20, 6)"
    assert str(metrics.schema.field("value_integer").type) == "int64"
    assert metrics.num_rows > 5
    assert all("private" not in key.lower() for key in metrics.column_names)
    row = observations.to_pylist()[0]
    assert "private-slot" not in json.dumps(row)
    assert "PRIVATE PROMPT" not in json.dumps(row)
    first_bytes = archive.read_bytes()
    repeat = runner.invoke(app, [
        "export", "private-batch", "--workspace", str(tmp_path), "--parquet"
    ])
    assert repeat.exit_code == 0, repeat.output
    assert archive.read_bytes() == first_bytes
    # Disabling opt-in excludes Parquet even though those files still exist.
    ordinary = runner.invoke(app, [
        "export", "private-batch", "--workspace", str(tmp_path)
    ])
    assert ordinary.exit_code == 0, ordinary.output
    with zipfile.ZipFile(archive) as z:
        assert all(not name.endswith(".parquet") for name in z.namelist())


def test_90_anonymous_slot_rows_with_18_cutouts_and_null_metric_values(tmp_path):
    pa, pq = _arrow()
    assets, results = [], {}
    for n in range(1, 91):
        identifier = f"private-token-{n:03d}"
        ratio = ("3:4" if n % 2 else "1:1")
        asset = {"id": identifier, "aspect_ratio": ratio,
                 "source": "SECRET/INPUT/PATH" if n <= 60 else None,
                 "prompt": "SECRET PROMPT" if n > 60 else None,
                 "targets": ["subject"] if n % 5 == 0 else []}
        assets.append(asset)
        paths = [f"photos/secret-{n}.png"]
        if n % 5 == 0:
            paths.append(f"cutouts/private-{n}.png")
        results[identifier] = {"status": "accepted", "outputs": paths}
    manifest = {"assets": assets}
    snapshot = build_analytics(manifest, results, [], [])
    assert snapshot["accepted_assets"] == 90
    pub = write_parquet_exports(tmp_path, snapshot, manifest, results)
    assert pub["datasets"][DATASETS[1]]["rows"] == 90
    slots = pq.read_table(tmp_path / DATASETS[1]).to_pylist()
    assert len(slots) == 90
    assert sum(r["requested_cutouts"] for r in slots) == 18
    assert sum(r["selected_outputs"] for r in slots) == 108
    assert sum(r["source_mode"] == "local_source" for r in slots) == 60
    assert sum(r["source_mode"] == "demo_or_model_generated" for r in slots) == 30
    assert slots[0]["slot_ordinal"] == 1
    assert slots[-1]["slot_ordinal"] == 90
    assert "id" not in pq.read_table(tmp_path / DATASETS[1]).column_names
    assert "prompt" not in pq.read_table(tmp_path / DATASETS[1]).column_names
    metrics = pq.read_table(tmp_path / DATASETS[0]).to_pylist()
    # No task journal: unknown stage/provider p95 must not be fabricated.
    assert snapshot["actual_invoiced_usd"] is None
    assert all(row["value_usd"] is None or row["value_usd"] >= 0 for row in metrics)
    all_strings = json.dumps(slots) + json.dumps([
        {k: str(v) for k, v in row.items()} for row in metrics])
    assert "SECRET" not in all_strings
    assert "private-token-" not in all_strings
    assert "photos/secret" not in all_strings


def test_nullable_integer_usd_ms_and_nonzero_cost_are_distinct(tmp_path):
    pa, pq = _arrow()
    csv_text = ("schema_version,section,group,measure,value,unit\n"
                "1,stage,generation,operations,0,operations\n"
                "1,stage,generation,reserved_usd,1.235678,USD\n"
                "1,stage,generation,observed_elapsed_ms_p95,,ms\n"
                "1,stage,generation,attempts_without_finished_timing,2,operations\n")
    rows = _metric_rows(csv_text)
    assert rows[0]["value_integer"] == 2
    assert any(row["value_integer"] == 0 for row in rows)
    assert any(str(row["value_usd"]) == "1.235678" for row in rows)
    assert any(row["unit"] == "ms" and row["value_ms"] is None for row in rows)
    from prehnite.economics import batch_economics
    snapshot = build_analytics({"assets": [{"id": "x", "aspect_ratio": "1:1"}]},
                               {"x": {"status": "rejected"}}, [], [])
    write_parquet_exports(tmp_path, snapshot, {"assets": [{"id": "x"}]},
                          {"x": {"status": "rejected"}})
    data = pq.read_table(tmp_path / DATASETS[0]).to_pylist()
    per_accepted = [r for r in data
                    if r["measure"] == "reserved_usd_per_accepted_asset"]
    assert len(per_accepted) == 1 and per_accepted[0]["value_usd"] is None
    assert any(r["measure"] == "accepted_assets" and r["value_integer"] == 0
               for r in data)


def test_stale_and_tampered_parquet_refused_before_zip_inclusion(tmp_path):
    pa, pq = _arrow()
    engine = small_engine(tmp_path)
    try:
        report = engine.run()
        root = engine.journal.root
        write_parquet_exports(root, report["analytics"],
                              engine.journal.fact("manifest", {}),
                              engine.journal.fact("results", {}))
        assert len(verified_parquet_entries(root)) == 3
        source = root / DATASETS[0]
        original = source.read_bytes()
        source.write_bytes(original[:-8] + b"TAMPERED")
        with pytest.raises(Exception, match="Parquet|digest"):
            package(engine.journal, include_parquet=True)
        source.write_bytes(original)
        (root / "analytics.json").write_text("{}")
        with pytest.raises(Exception, match="Parquet|stale"):
            package(engine.journal, include_parquet=True)
        # Default archive is not tainted by stale optional files.
        assert package(engine.journal).is_file()
    finally:
        engine.journal.close()


def test_mcp_export_can_opt_in_without_changing_default(tmp_path):
    pa, pq = _arrow()
    manager = JobManager(tmp_path / "home")
    manifest = Manifest.model_validate({
        "id": "mcp-parquet", "assets": [{
            "id": "a", "prompt": "PRIVATE", "aspect_ratio": "3:4",
            "target_size": [192, 256], "output": {"image": "a.png"},
        }]
    })
    profile = Profile.model_validate({
        "variants": ["native_4k"],
        "generation": {"provider": "demo", "model": "synthetic"},
        "upscale": {"provider": "disabled"},
        "policy": {"uncertain": "accept_unverified"},
    })
    engine = Engine(manifest, profile, manager.workspace, manager.inputs)
    try:
        engine.run()
    finally:
        engine.journal.close()
    normal = manager.export("mcp-parquet")
    assert normal["parquet_included"] is False
    with zipfile.ZipFile(normal["archive"]) as z:
        assert all(not n.endswith(".parquet") for n in z.namelist())
    opted = manager.export("mcp-parquet", include_parquet=True)
    assert opted["parquet_included"] is True
    with zipfile.ZipFile(opted["archive"]) as z:
        assert "_prehnite/analytics.parquet" in z.namelist()
        assert "_prehnite/asset-observations.parquet" in z.namelist()


@pytest.mark.parametrize("csv_value,unit", [
    ("nan", "USD"), ("inf", "ms"), ("-1", "operations"),
    ("1e10", "operations"), ("1.23456789e19", "USD"),
])
def test_invalid_numeric_csv_refused(csv_value, unit):
    from prehnite.parquet_export import _metric_rows
    csv_text = ("schema_version,section,group,measure,value,unit\n"
                + f"1,stage,generation,value,{csv_value},{unit}\n")
    with pytest.raises((ValueError, ArithmeticError)):
        _metric_rows(csv_text)


def test_cli_export_refuses_fresh_launch_before_worker_acquires_lock(tmp_path):
    engine = small_engine(tmp_path)
    try:
        engine.run()
        engine.journal.job_launch(
            "test-launch-token", "fixture.yaml", "demo.yaml",
            engine.journal.fact("configuration_sha256"))
    finally:
        engine.journal.close()
    response = CliRunner().invoke(
        app, ["export", "private-batch", "--workspace", str(tmp_path)])
    assert response.exit_code != 0
    assert "unresolved" in response.output.lower()


def test_symlinked_parquet_file_outside_batch_is_rejected_even_if_digest_matches(tmp_path):
    pa, pq = _arrow()
    engine = small_engine(tmp_path)
    try:
        result = engine.run()
        root = engine.journal.root
        write_parquet_exports(
            root, result["analytics"],
            engine.journal.fact("manifest", {}),
            engine.journal.fact("results", {}))
        source = root / DATASETS[0]
        outside = tmp_path / "outside.parquet"
        outside.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not allowed on this Windows account")
        with pytest.raises(Exception, match="batch root"):
            verified_parquet_entries(root)
        # Default export does not include optional datasets regardless.
        assert package(engine.journal).is_file()
    finally:
        engine.journal.close()
