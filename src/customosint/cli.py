"""Command-line interface."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer

from .case import Case
from .config import load_settings
from .doctor import checks
from .engine import InvestigationEngine
from .exporters import export_all
from .providers import built_in_providers
from .providers.image import ImageProvider
from .report import generate_report

app = typer.Typer(no_args_is_help=True, help="Evidence-first OSINT correlation toolkit.")


@app.command()
def investigate(email: Annotated[list[str] | None, typer.Option()] = None, nickname: Annotated[list[str] | None, typer.Option()] = None, name: Annotated[list[str] | None, typer.Option()] = None, phone: Annotated[list[str] | None, typer.Option()] = None, image: Annotated[list[Path] | None, typer.Option()] = None, depth: Annotated[int, typer.Option(min=0, max=5)] = 2, providers: Annotated[str | None, typer.Option(help="Comma-separated provider names")] = None, case_name: Annotated[str | None, typer.Option()] = None, fixture: Annotated[Path | None, typer.Option(exists=True, file_okay=False)] = None, aggressive: Annotated[bool, typer.Option()] = False, no_cache: Annotated[bool, typer.Option()] = False, max_entities: Annotated[int | None, typer.Option(min=1)] = None, max_provider_runs: Annotated[int | None, typer.Option(min=1)] = None, timeout: Annotated[float | None, typer.Option(min=1)] = None, provider_timeout: Annotated[float | None, typer.Option(min=1)] = None, verbose: Annotated[int, typer.Option("-v", count=True)] = 0, debug: Annotated[bool, typer.Option()] = False, config: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None) -> None:
    """Create a case and run controlled enrichment."""
    seed_values: list[tuple[str, str]] = []
    for kind, values in (("email", email), ("nickname", nickname), ("name", name), ("phone", phone)):
        seed_values.extend((kind, value) for value in values or [])
    seed_values.extend(("image", str(value)) for value in image or [])
    if not seed_values: raise typer.BadParameter("Provide at least one seed")
    settings = load_settings(config); label = case_name or seed_values[0][1]
    if debug: verbose = max(verbose, 3)
    level = logging.DEBUG if verbose >= 2 else logging.INFO if verbose == 1 else logging.WARNING
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")
    if verbose: typer.echo(f"[+] Investigation: {label} (verbosity={verbose})")
    if max_entities is not None: settings.max_entities = max_entities
    if max_provider_runs is not None: settings.max_provider_runs = max_provider_runs
    if timeout is not None: settings.timeout = timeout
    if provider_timeout is not None: settings.provider_timeout = provider_timeout
    case = Case.create(settings.cases_dir, label, [{"type": k, "value": v} for k, v in seed_values])
    engine = InvestigationEngine(case, settings, fixture=fixture, no_cache=no_cache)
    try:
        for kind, value in seed_values: engine.add_seed(kind, value)
        asyncio.run(asyncio.wait_for(engine.run(depth, set(providers.split(",")) if providers else None, aggressive), timeout=settings.timeout))
        entities, relations = case.db.entities(), case.db.relationships(); export_all(case.path / "graph", entities, relations); generate_report(case)
        typer.echo(f"Investigation complete.\n\nSeeds: {len(seed_values)}\nEntities: {len(entities)}\nRelationships: {len(relations)}\n\nReport: {case.path / 'report/index.html'}\nInteractive graph: {case.path / 'graph/index.html'}\nGephi: {case.path / 'graph/case.gexf'}\nMaltego: {case.path / 'graph/maltego_import.csv'}\nNeo4j: {case.path / 'graph/neo4j.cypher'}")
    finally: case.db.close()


@app.command("providers")
def list_providers() -> None:
    """Show provider availability."""
    typer.echo(f"{'PROVIDER':<15} {'STATUS':<12} INPUT")
    for provider in [*built_in_providers(), ImageProvider()]:
        ready, reason = provider.available(); typer.echo(f"{provider.name:<15} {('READY' if ready else 'SKIPPED'):<12} {','.join(sorted(provider.supported_entities))} ({reason})")


@app.command()
def doctor() -> None:
    """Check runtime, tools, keys and permissions."""
    for label, status, detail in checks(): typer.echo(f"{label:<15} {status:<12} {detail}")


def _open_case(path: Path) -> Case: return Case.open(path.resolve())


@app.command()
def report(case_path: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    case = _open_case(case_path)
    try: typer.echo(generate_report(case))
    finally: case.db.close()


@app.command()
def graph(case_path: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    case = _open_case(case_path)
    try: export_all(case.path / "graph", case.db.entities(), case.db.relationships()); typer.echo(case.path / "graph")
    finally: case.db.close()


@app.command("cases")
def list_cases(root: Annotated[Path, typer.Option()] = Path("cases")) -> None:
    for path in sorted(root.glob("*/case.json"), reverse=True): typer.echo(path.parent)


@app.command()
def show(case_path: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    case = _open_case(case_path)
    try: typer.echo(f"{case.name}: {len(case.db.entities())} entities, {len(case.db.relationships())} relationships")
    finally: case.db.close()


if __name__ == "__main__": app()
