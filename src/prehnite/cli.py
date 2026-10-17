"""Prehnite command line."""
from pathlib import Path
import json
import typer
from .manifest import load_manifest, load_profile, validate_job
from .registry import list_models
from .store import Journal
from .reporting import export_report, package

app = typer.Typer(help="Batch-first, quality-gated visual asset production.")

@app.command()
def init(destination: Path = typer.Option(Path("."), "--destination",
                                      help="Directory for demo manifest and profile"),
         batch_id: str = typer.Option("starter-batch", "--batch-id",
                                      help="Identifier for this demo batch")):
    """Create a free, offline starter batch without replacing existing files."""
    from .onboarding import init_example
    try:
        manifest, profile = init_example(destination, batch_id)
    except (FileExistsError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Created {manifest} and {profile}")
    typer.echo(f'Next: prehnite validate "{manifest}" --profile "{profile}"')
    typer.echo(f'Then: prehnite run "{manifest}" --profile "{profile}" --workspace workspace')


@app.command()
def doctor(check_comfyui: bool = typer.Option(False, "--check-comfyui",
                                               help="Opt in to localhost-only health check"),
           comfyui_url: str = typer.Option("http://127.0.0.1:8188", "--comfyui-url",
                                          help="Loopback-only local ComfyUI address")):
    """Print key-presence-only environment diagnostics; never spend or upload."""
    from .onboarding import doctor_report
    try:
        report = doctor_report(check_comfyui=check_comfyui, comfyui_url=comfyui_url)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(report, indent=2))


@app.command("hardware")
def hardware():
    """Print read-only offline hardware observations; no model feasibility claims."""
    from .hardware import hardware_report
    typer.echo(json.dumps(hardware_report(), indent=2, sort_keys=True))


@app.command("recipe-resolve")
def recipe_resolve(
        recipe: Path = typer.Option(..., "--recipe"),
        bindings: Path = typer.Option(..., "--bindings"),
        workflows: Path = typer.Option(..., "--workflows"),
        checkpoints: Path = typer.Option(..., "--checkpoints")):
    """Verify operator-supplied micro recipe input bytes; never run models."""
    from .recipe_resolver import load_local_bindings, resolve_local_micro
    from .recipes import load_recipe
    try:
        result = resolve_local_micro(load_recipe(recipe), load_local_bindings(bindings),
                                     workflows, checkpoints)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result, indent=2, sort_keys=True))

@app.command()
def validate(manifest: Path, profile: Path = typer.Option(...),
             inputs: Path = typer.Option(Path("inputs"))):
    m, p = load_manifest(manifest), load_profile(profile)
    validate_job(m, p, inputs)
    typer.echo(f"Valid: {m.id}, {len(m.assets)} assets")

@app.command()
def models():
    typer.echo(json.dumps(list_models(), indent=2))

@app.command()
def estimate(manifest: Path, profile: Path = typer.Option(...),
             inputs: Path = typer.Option(Path("inputs"))):
    """Print estimated maximum-request cost before a batch starts."""
    from .costing import estimate_costs
    m, p = load_manifest(manifest), load_profile(profile)
    validate_job(m, p, inputs)
    typer.echo(json.dumps(estimate_costs(m, p), indent=2))

@app.command()
def crops(source: Path, output: Path = typer.Option(..., help="Local evidence folder"),
          edge: int = typer.Option(768, help="Native pixel size of each square crop"),
          anchor_x: float | None = typer.Option(None, help="Normalized subject X, 0–1"),
          anchor_y: float | None = typer.Option(None, help="Normalized subject Y, 0–1")):
    """Inspect image corners, center and optional manually selected subject at 1:1."""
    from .crops import make_detail_crops
    if (anchor_x is None) != (anchor_y is None):
        raise typer.BadParameter("Both --anchor-x and --anchor-y are required together")
    evidence = make_detail_crops(
        source, output, edge=edge,
        anchor=(anchor_x, anchor_y) if anchor_x is not None else None,
    )
    typer.echo(json.dumps({
        "source": str(source), "source_sha256": evidence["source_sha256"],
        "native_crops": len(evidence["crops"]), "manifest": str(output / "crops.json"),
        "overview": str(output / "overview.png"),
        "quality_judgment": "none; inspect crops with a human or configured judge",
    }, indent=2))


@app.command()
def run(manifest: Path, profile: Path = typer.Option(...),
        workspace: Path = typer.Option(Path("workspace")),
        inputs: Path = typer.Option(Path("inputs")),
        job_token: str | None = typer.Option(None, "--job-token", hidden=True),
        recipe: Path | None = typer.Option(None, "--recipe"),
        bindings: Path | None = typer.Option(None, "--bindings"),
        workflows: Path | None = typer.Option(None, "--workflows"),
        checkpoints: Path | None = typer.Option(None, "--checkpoints")):
    """Run a batch; optional all-or-nothing local recipe binding refuses drift."""
    from .engine import Engine
    from .recipe_execution import MicroExecution
    supplied = (recipe, bindings, workflows, checkpoints)
    if any(value is not None for value in supplied) and not all(
            value is not None for value in supplied):
        raise typer.BadParameter(
            "--recipe, --bindings, --workflows and --checkpoints must be supplied together"
        )
    execution = (MicroExecution(recipe, bindings, workflows, checkpoints)
                 if all(value is not None for value in supplied) else None)
    if execution is not None and job_token is not None:
        raise typer.BadParameter("Recipe-bound MCP worker launching is not implemented")
    try:
        engine = Engine(load_manifest(manifest), load_profile(profile), workspace, inputs,
                        job_token=job_token, recipe_execution=execution)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    try:
        report = engine.run()
        if "job_status" in report:
            typer.echo(f"Worker {report['job_status']}; accepted results remain journaled")
        else:
            typer.echo(f"Processed {len(report['asset_results'])} assets; "
                       f"reserved USD {report['cost_estimated_or_reserved_usd']}; "
                       f"output: {engine.journal.root}")
    finally:
        engine.journal.close()

@app.command()
def status(batch_id: str, workspace: Path = typer.Option(Path("workspace"))):
    from .schema import Asset
    Asset.check_id(batch_id)
    if not (workspace / "batches" / batch_id / "state.sqlite3").is_file():
        raise typer.BadParameter("No such batch")
    j = Journal(workspace, batch_id)
    try:
        typer.echo(json.dumps({"results": j.fact("results", {}),
                               "reserved_usd": j.reserved()}, indent=2))
    finally:
        j.close()


@app.command()
def inspect(batch_id: str,
            asset_id: str = typer.Option(..., "--asset",
                                         help="One accepted asset slot ID"),
            workspace: Path = typer.Option(Path("workspace")),
            inputs: Path | None = typer.Option(
                None, "--inputs",
                help="Explicit original-input root; requires saved source SHA256")):
    """Generate a private, offline 1:1 inspection page for one verified slot."""
    from .schema import Asset
    from .native_inspection import export_native_inspection
    Asset.check_id(batch_id)
    Asset.check_id(asset_id)
    if not (workspace / "batches" / batch_id / "state.sqlite3").is_file():
        raise typer.BadParameter("No such batch")
    journal = Journal(workspace, batch_id)
    try:
        with journal.launch_exclusive():
            if journal.worker_active():
                raise typer.BadParameter("Cannot inspect while a worker is active")
            record = journal.job_record()
            if record and record["status"] in (
                    "launching", "pause_requested", "cancel_requested"):
                raise typer.BadParameter(
                    "Worker launch/control state unresolved; inspect after safe stop")
            path = export_native_inspection(journal, asset_id, inputs=inputs)
        typer.echo(str(path))
    finally:
        journal.close()


@app.command()
def compare(batch_id: str,
            asset_id: str = typer.Option(..., "--asset",
                                         help="One accepted slot ID"),
            workspace: Path = typer.Option(Path("workspace")),
            inputs: Path | None = typer.Option(
                None, "--inputs", help="Explicit historical input root"),
            cutout: str | None = typer.Option(
                None, "--cutout", help="Named accepted cutout target"),
            assume_same_grid: bool = typer.Option(
                False, "--assume-same-grid",
                help="Required explicit attestation; no automatic alignment")):
    """Compare verified pixels without claiming visual quality or registration."""
    from .schema import Asset
    from .pixel_comparison import compare_slot
    Asset.check_id(batch_id)
    Asset.check_id(asset_id)
    if not (workspace / "batches" / batch_id / "state.sqlite3").is_file():
        raise typer.BadParameter("No such batch")
    j = Journal(workspace, batch_id)
    try:
        with j.launch_exclusive():
            if j.worker_active():
                raise typer.BadParameter("Cannot compare while a worker is active")
            record = j.job_record()
            if record and record["status"] in (
                    "launching", "pause_requested", "cancel_requested"):
                raise typer.BadParameter(
                    "Worker launch/control state unresolved; compare after safe stop")
            result = compare_slot(j, asset_id, inputs=inputs, cutout=cutout,
                                  same_grid_asserted=assume_same_grid)
        typer.echo(json.dumps(result, sort_keys=True, indent=2))
    finally:
        j.close()



@app.command("compare-tiles")
def compare_tiles(
        batch_id: str,
        asset_id: str = typer.Option(..., "--asset"),
        alignment: Path = typer.Option(..., "--alignment",
                                      help="Operator-authored hash-bound translation JSON"),
        workspace: Path = typer.Option(Path("workspace")),
        inputs: Path | None = typer.Option(
            None, "--inputs", help="Approved original-image root"),
        cutout: str | None = typer.Option(
            None, "--cutout", help="Named accepted cutout")):
    """Overlap-only registered pixel diagnostics up to 24 MP (translation only)."""
    from .schema import Asset
    from .tiled_alignment import compare_registered_tiles
    Asset.check_id(batch_id)
    Asset.check_id(asset_id)
    if not (workspace / "batches" / batch_id / "state.sqlite3").is_file():
        raise typer.BadParameter("No such batch")
    j = Journal(workspace, batch_id)
    try:
        with j.launch_exclusive():
            if j.worker_active():
                raise typer.BadParameter("Cannot compare while worker is active")
            control = j.job_record()
            if control and control["status"] in (
                    "launching", "pause_requested", "cancel_requested"):
                raise typer.BadParameter(
                    "Worker control state unresolved; compare after safe stop")
            output = compare_registered_tiles(
                j, asset_id, alignment=alignment, inputs=inputs, cutout=cutout)
        typer.echo(json.dumps(output, sort_keys=True, indent=2))
    finally:
        j.close()



@app.command("validate-affine")
def validate_affine(
        batch_id: str,
        asset_id: str = typer.Option(..., "--asset"),
        alignment: Path = typer.Option(..., "--alignment",
                                      help="Operator-authored v2 affine contract JSON"),
        workspace: Path = typer.Option(Path("workspace")),
        inputs: Path | None = typer.Option(
            None, "--inputs", help="Approved historical input root"),
        cutout: str | None = typer.Option(
            None, "--cutout", help="Named accepted cutout")):
    """Verify versioned affine provenance, invertibility and geometric overlap.

    This command never warps image pixels or writes comparison evidence.
    """
    from .affine_contract import validate_affine_for_slot
    from .schema import Asset
    Asset.check_id(batch_id)
    Asset.check_id(asset_id)
    if not (workspace / "batches" / batch_id / "state.sqlite3").is_file():
        raise typer.BadParameter("No such batch")
    j = Journal(workspace, batch_id)
    try:
        with j.launch_exclusive():
            if j.worker_active():
                raise typer.BadParameter("Cannot validate while worker is active")
            control = j.job_record()
            if control and control["status"] in (
                    "launching", "pause_requested", "cancel_requested"):
                raise typer.BadParameter(
                    "Worker state unresolved; validate after safe stop")
            result = validate_affine_for_slot(
                j, asset_id, alignment=alignment, inputs=inputs, cutout=cutout)
        typer.echo(json.dumps(result, sort_keys=True, indent=2))
    finally:
        j.close()



@app.command("evaluate-visual-gold")
def evaluate_visual_gold(
        source: Path = typer.Option(..., "--input",
                                   help="Private local labeled Noul observation JSON"),
        destination: Path = typer.Option(..., "--output",
                                        help="Write aggregate-only JSON locally"),
        reject_at: float = typer.Option(0.2, "--reject-at"),
        accept_at: float = typer.Option(0.8, "--accept-at")):
    """Offline-only binary visual-judge calibration; no providers or imagery."""
    from .visual_calibration import (
        evaluate_binary_visual_gold, write_aggregate_gold_report)
    if not source.is_file() or source.stat().st_size > 16 * 1024 * 1024:
        raise typer.BadParameter("Local gold input absent or exceeds 16 MiB")
    data = json.loads(source.read_text(encoding="utf-8"))
    if (not isinstance(data, dict)
            or set(data) != {"schema_version", "declared_source", "observations"}
            or type(data["schema_version"]) is not int
            or data["schema_version"] != 1):
        raise typer.BadParameter("Unsupported or privacy-unsafe gold JSON schema")
    result = evaluate_binary_visual_gold(
        data["observations"], declared_source=data["declared_source"],
        lower=reject_at, upper=accept_at)
    write_aggregate_gold_report(destination, result)
    typer.echo(str(destination))


@app.command()
def export(batch_id: str, workspace: Path = typer.Option(Path("workspace")),
           parquet: bool = typer.Option(False, "--parquet",
                                         help="Opt-in local Parquet; needs prehnite[parquet]")):
    from .schema import Asset
    Asset.check_id(batch_id)
    if not (workspace / "batches" / batch_id / "state.sqlite3").is_file():
        raise typer.BadParameter("No such batch")
    j = Journal(workspace, batch_id)
    try:
        with j.launch_exclusive():
            if j.worker_active():
                raise typer.BadParameter("Cannot export while a worker is active")
            record = j.job_record()
            if record and record["status"] in (
                    "launching", "pause_requested", "cancel_requested"):
                raise typer.BadParameter(
                    "Worker launch/control state unresolved; export after safe stop")
            report = export_report(j)
            if parquet:
                from .parquet_export import write_parquet_exports
                write_parquet_exports(j.root, report["analytics"],
                                      j.fact("manifest", {}), j.fact("results", {}))
            typer.echo(str(package(j, include_parquet=parquet)))
    finally:
        j.close()

if __name__ == "__main__":
    app()
