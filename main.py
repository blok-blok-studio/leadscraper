"""
Lead Scraper CLI — US Local Business Lead Generation Tool

Usage:
    python main.py run                     # Run full pipeline from config
    python main.py scrape --source yelp    # Scrape specific source
    python main.py enrich                  # Enrich unenriched leads
    python main.py export --format csv     # Export leads
    python main.py stats                   # Show database stats
    python main.py init-db                 # Initialize database tables
"""

import click
import logging

from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)


@click.group()
@click.option("--config", "-c", default=None, help="Path to config YAML file")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx, config, verbose):
    """US Local Business Lead Scraper — Bloblok Studio"""
    setup_logging()
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


@cli.command()
@click.pass_context
def run(ctx):
    """Run the full scraping + enrichment pipeline."""
    from src.engine import ScraperEngine

    engine = ScraperEngine(ctx.obj["config"])
    click.echo("Starting full scraping pipeline...")
    results = engine.run()

    click.echo("\n--- Results ---")
    click.echo(f"  Leads found:    {results['total_found']}")
    click.echo(f"  New leads:      {results['total_new']}")
    click.echo(f"  Updated leads:  {results['total_updated']}")
    click.echo(f"  Skipped:        {results['total_skipped']}")
    click.echo(f"  Enriched:       {results['total_enriched']}")
    if results["errors"]:
        click.echo(f"  Errors:         {len(results['errors'])}")


@cli.command()
@click.option("--source", "-s", required=True, help="Source: yellowpages, bbb, yelp")
@click.option("--category", "-cat", required=True, help="Business category to search")
@click.option("--location", "-l", required=True, help="Location (e.g., 'Miami, FL')")
@click.option("--pages", "-p", default=5, help="Max pages to scrape")
@click.pass_context
def scrape(ctx, source, category, location, pages):
    """Scrape a single source/category/location."""
    from src.engine import ScraperEngine

    engine = ScraperEngine(ctx.obj["config"])
    click.echo(f"Scraping {source} for '{category}' in {location}...")
    stats = engine.scrape_single_source(source, category, location, pages)

    click.echo(f"\n  Found: {stats['found']} | New: {stats['new']} | Updated: {stats['updated']}")
    if stats.get("error"):
        click.echo(f"  Error: {stats['error']}")


@cli.command()
@click.option("--limit", "-l", default=100, help="Max leads to enrich")
@click.pass_context
def enrich(ctx, limit):
    """Enrich unenriched leads with additional data."""
    from src.engine import ScraperEngine

    engine = ScraperEngine(ctx.obj["config"])
    click.echo(f"Enriching up to {limit} leads...")
    results = engine.enrich_only(limit=limit)

    click.echo(f"\n  Total: {results['total']} | Success: {results['success']} | Failed: {results['failed']}")


@cli.command()
@click.option("--format", "-f", default="csv", type=click.Choice(["csv", "json"]))
@click.option("--output", "-o", default="exports", help="Output directory")
@click.option("--state", default=None, help="Filter by state (e.g., FL)")
@click.option("--category", default=None, help="Filter by category")
@click.option("--min-quality", default=0, help="Minimum quality score (0-100)")
@click.option("--enriched-only", is_flag=True, help="Only export enriched leads")
@click.pass_context
def export(ctx, format, output, state, category, min_quality, enriched_only):
    """Export leads to CSV or JSON."""
    from src.utils.export import export_leads

    filepath = export_leads(
        format=format,
        output_dir=output,
        state=state,
        category=category,
        min_quality=min_quality,
        enriched_only=enriched_only,
    )
    if filepath:
        click.echo(f"Exported to: {filepath}")
    else:
        click.echo("No leads matched export criteria.")


@cli.command()
@click.pass_context
def stats(ctx):
    """Show database statistics."""
    from src.database.connection import get_session, init_db
    from src.database.repository import LeadRepository

    init_db()
    session = get_session()
    repo = LeadRepository(session)
    data = repo.get_stats()
    session.close()

    click.echo("\n--- Lead Database Stats ---")
    click.echo(f"  Total leads:       {data['total_leads']}")
    click.echo(f"  Enriched:          {data['enriched_leads']}")
    click.echo(f"  Unenriched:        {data['unenriched_leads']}")
    click.echo(f"  Avg quality score: {data['avg_quality_score']}")

    if data["top_states"]:
        click.echo("\n  Top States:")
        for item in data["top_states"]:
            click.echo(f"    {item['state']}: {item['count']} leads")

    if data["top_categories"]:
        click.echo("\n  Top Categories:")
        for item in data["top_categories"]:
            click.echo(f"    {item['category']}: {item['count']} leads")


@cli.command("init-db")
@click.pass_context
def init_database(ctx):
    """Initialize database tables."""
    from src.database.connection import init_db

    click.echo("Initializing database...")
    init_db()
    click.echo("Database tables created successfully.")


@cli.command()
@click.pass_context
def schedule(ctx):
    """Run the scraper on a schedule (based on config)."""
    import schedule as sched
    import time
    from src.engine import ScraperEngine
    from src.config import load_config

    config = load_config(ctx.obj["config"])
    schedule_config = config.get("scheduling", {})

    if not schedule_config.get("enabled"):
        click.echo("Scheduling is disabled in config. Enable it first.")
        return

    interval = schedule_config.get("interval_hours", 24)
    start_time = schedule_config.get("start_time", "02:00")

    engine = ScraperEngine(ctx.obj["config"])

    def job():
        click.echo(f"Running scheduled scrape...")
        results = engine.run()
        click.echo(f"Scheduled run complete: {results['total_new']} new leads")

    sched.every(interval).hours.at(start_time).do(job)

    click.echo(f"Scheduler started. Running every {interval}h at {start_time}")
    click.echo("Press Ctrl+C to stop.")

    try:
        while True:
            sched.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        click.echo("\nScheduler stopped.")


if __name__ == "__main__":
    cli()
