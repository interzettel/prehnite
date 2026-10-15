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
def validate(manifest: Path, profile: Path = typer.Option(...),
             inputs: Path = typer.Option(Path("inputs"))):
    m, p = load_manifest(manifest), load_profile(profile)
    validate_job(m, p, inputs)
    typer.echo(f"Valid: {m.id}, {len(m.assets)} assets")

@app.command()
def models():
    typer.echo(json.dumps(list_models(), indent=2))

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
