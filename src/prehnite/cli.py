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
        inputs: Path = typer.Option(Path("inputs"))):
    from .engine import Engine
    engine = Engine(load_manifest(manifest), load_profile(profile), workspace, inputs)
    try:
        report = engine.run()
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
def export(batch_id: str, workspace: Path = typer.Option(Path("workspace"))):
    from .schema import Asset
    Asset.check_id(batch_id)
    if not (workspace / "batches" / batch_id / "state.sqlite3").is_file():
        raise typer.BadParameter("No such batch")
    j = Journal(workspace, batch_id)
    try:
        export_report(j)
        typer.echo(str(package(j)))
    finally:
        j.close()

if __name__ == "__main__":
    app()
