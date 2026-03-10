"""CLI entry point for the Price Monitor Agent.

Usage:
    python -m agent.main run                    # One-off run (console output)
    python -m agent.main run --report slack     # One-off run, send to Slack
    python -m agent.main run --report both      # Send to Slack + Email
    python -m agent.main schedule               # Start the scheduled runner
    python -m agent.main stats                  # Show database statistics
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from agent.graph import agent
from agent.state import AgentState, CompetitorSource, ReportFormat
from agent.utils.config import get_settings
from agent.utils.database import PriceDatabase

app = typer.Typer(
    name="price-monitor",
    help="Multi-Step AI Process Automation Agent — Competitor Price Monitor",
)
console = Console()

DEFAULT_CONFIG = Path("data/competitors.json")


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _configure_langsmith(settings) -> None:
    """Configure LangSmith tracing if enabled.

    LangSmith provides observability for LangGraph runs — it captures
    each node's inputs/outputs, token usage, and latency so you can
    debug and optimise the agent pipeline from a web dashboard.

    Set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY in your .env
    to enable. The project name is set via LANGCHAIN_PROJECT.
    """
    if settings.langchain_tracing_v2 and settings.langchain_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        console.print(
            f"[dim]LangSmith tracing enabled — project: {settings.langchain_project}[/dim]"
        )


def _load_competitors(config_path: Path) -> list[CompetitorSource]:
    """Load competitor sources from a JSON config file."""
    if not config_path.exists():
        console.print(f"[red]Config not found: {config_path}[/red]")
        console.print("Create data/competitors.json — see data/sample_competitors.json for format")
        raise typer.Exit(1)

    with open(config_path) as f:
        data = json.load(f)

    sources = [CompetitorSource(**item) for item in data.get("competitors", data)]
    console.print(f"[green]Loaded {len(sources)} competitor sources[/green]")
    return sources


async def _run_agent(competitors: list[CompetitorSource], report_format: ReportFormat) -> None:
    """Execute the agent graph."""
    initial_state = AgentState(
        competitors=competitors,
        report_format=report_format,
        run_timestamp=datetime.now(),
    )

    console.print("[bold blue]Starting Price Monitor Agent...[/bold blue]")
    console.print(f"  Sources: {len(competitors)}")
    console.print(f"  Report:  {report_format.value}")
    console.print()

    result = await agent.ainvoke(initial_state)

    # Print summary
    console.print()
    console.print("[bold green]Agent run complete![/bold green]")
    console.print(f"  Products tracked: {result.get('total_products_tracked', 0)}")
    console.print(f"  Price changes:    {len(result.get('price_changes', []))}")
    console.print(f"  Notifications:    {', '.join(result.get('notifications_sent', []))}")

    if result.get("scrape_errors"):
        console.print(f"  [yellow]Warnings: {len(result['scrape_errors'])}[/yellow]")


@app.command()
def run(
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c", help="Competitors JSON config"),
    report: str = typer.Option(
        "console", "--report", "-r", help="Report format: console|slack|email|both"
    ),
) -> None:
    """Run the price monitoring agent once."""
    settings = get_settings()
    _setup_logging(settings.log_level)
    _configure_langsmith(settings)

    competitors = _load_competitors(config)
    report_format = ReportFormat(report)

    asyncio.run(_run_agent(competitors, report_format))


@app.command()
def schedule(
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c", help="Competitors JSON config"),
    report: str = typer.Option(
        "both", "--report", "-r", help="Report format: console|slack|email|both"
    ),
) -> None:
    """Start the scheduled runner (uses APScheduler with cron)."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    settings = get_settings()
    _setup_logging(settings.log_level)
    _configure_langsmith(settings)

    competitors = _load_competitors(config)
    report_format = ReportFormat(report)

    def job():
        console.print(f"\n[bold]Scheduled run at {datetime.now().isoformat()}[/bold]")
        asyncio.run(_run_agent(competitors, report_format))

    # Parse cron expression: "minute hour day_of_month month day_of_week"
    parts = settings.schedule_cron.split()
    trigger = CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
    )

    scheduler = BlockingScheduler()
    scheduler.add_job(job, trigger)

    console.print("[bold green]Scheduler started[/bold green]")
    console.print(f"  Cron: {settings.schedule_cron}")
    console.print(f"  Next run: {scheduler.get_jobs()[0].next_run_time}")
    console.print("  Press Ctrl+C to stop\n")

    try:
        # Run once immediately, then start scheduler
        job()
        scheduler.start()
    except KeyboardInterrupt:
        console.print("\n[yellow]Scheduler stopped[/yellow]")


@app.command()
def stats() -> None:
    """Show database statistics."""
    settings = get_settings()
    db = PriceDatabase(settings.db_path)
    s = db.get_stats()

    table = Table(title="Price Monitor Database")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Total Records", str(s["total_records"]))
    table.add_row("Unique Products", str(s["unique_products"]))
    table.add_row("Latest Scrape", s["latest_scrape"] or "Never")

    console.print(table)


def main():
    app()


if __name__ == "__main__":
    main()
