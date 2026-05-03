"""
muni/cli.py

Command-line interface for muni.md.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from muni.pipeline import run
from muni.crawler import DiscoveredLink, LinkType

app = typer.Typer(
    name="muni",
    help="Crawl municipal websites and export public Google Docs to markdown.",
    no_args_is_help=True,
)
console = Console()


# ---------------------------------------------------------------------------
# muni crawl
# ---------------------------------------------------------------------------

@app.command()
def crawl_cmd(
    url: Annotated[str, typer.Argument(help="Seed URL to crawl")],
    output: Annotated[Path, typer.Option(
        "--output", "-o",
        help="Directory to write markdown files into",
    )] = Path("output"),
    all_content: Annotated[bool, typer.Option(
        "--all", "-a",
        help="Also collect PDFs and HTML page links",
    )] = False,
    dry_run: Annotated[bool, typer.Option(
        "--dry-run",
        help="Crawl and list links without exporting anything",
    )] = False,
    rate_limit: Annotated[float, typer.Option(
        "--rate-limit",
        help="Seconds between requests",
    )] = 1.0,
    no_manifest: Annotated[bool, typer.Option(
        "--no-manifest",
        help="Skip writing manifest.json",
    )] = False,
):
    """
    Crawl a URL, find Google Docs, and export them to markdown.
    """
    console.rule("[bold blue]muni.md[/bold blue]")
    console.print(f"[dim]Crawling:[/dim] {url}\n")

    with console.status("Running pipeline..."):
        result = run(
            seed_url=url,
            output_dir=output,
            collect_all=all_content,
            rate_limit=rate_limit,
            dry_run=dry_run,
            write_manifest=not no_manifest,
        )

    # --- Crawl errors ---
    if result.crawl.errors:
        for err in result.crawl.errors:
            rprint(f"[red]✗[/red] {err}")
        raise typer.Exit(1)

    # --- Discovered links table ---
    _print_discovered(result.crawl, all_content)

    if not result.crawl.gdocs:
        console.print("\n[yellow]No Google Docs found. Nothing to export.[/yellow]")
        raise typer.Exit(0)

    if dry_run:
        console.print("\n[dim]Dry run — skipping export.[/dim]")
        raise typer.Exit(0)

    # --- Export results ---
    console.print(f"\n[dim]Exported to[/dim] {output}/\n")
    _print_export_results(result.exports)

    # --- Summary ---
    summary = result.summary()
    console.print(
        f"\n[dim]Started:[/dim] {summary['started_at']}\n"
        f"[dim]Finished:[/dim] {summary['finished_at']}"
    )

    if not no_manifest:
        console.print(f"[dim]Manifest:[/dim] {output}/manifest.json")

    if result.failed:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# muni export (single doc)
# ---------------------------------------------------------------------------

@app.command()
def export_cmd(
    url: Annotated[str, typer.Argument(help="Google Doc URL to export")],
    output: Annotated[Path, typer.Option(
        "--output", "-o",
        help="Directory to write the markdown file into",
    )] = Path("output"),
    name: Annotated[str, typer.Option(
        "--name", "-n",
        help="Override the output filename (without .md extension)",
    )] = "",
):
    """
    Export a single Google Doc URL to markdown.
    """
    from muni.exporters.gdocs import export_doc

    link = DiscoveredLink(
        url=url,
        link_type=LinkType.GDOC,
        anchor_text=name,
        source_url=url,
    )

    with console.status("Exporting..."):
        result = export_doc(link, output_dir=output)

    if result.success:
        rprint(f"[green]✓[/green] {result.output_path}")
    else:
        rprint(f"[red]✗[/red] {result.error}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _print_discovered(result, all_content: bool):
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Type", width=8)
    table.add_column("Anchor text", max_width=40)
    table.add_column("URL")

    for link in result.gdocs:
        table.add_row("[green]gdoc[/green]", link.anchor_text or "[dim]—[/dim]", link.url)

    if all_content:
        for link in result.pdfs:
            table.add_row("[yellow]pdf[/yellow]", link.anchor_text or "[dim]—[/dim]", link.url)
        for link in result.html_pages:
            table.add_row("[blue]html[/blue]", link.anchor_text or "[dim]—[/dim]", link.url)

    console.print(table)
    console.print(
        f"[green]{len(result.gdocs)} Google Doc(s)[/green]"
        + (f", [yellow]{len(result.pdfs)} PDF(s)[/yellow]" if all_content else "")
        + (f", [blue]{len(result.html_pages)} HTML page(s)[/blue]" if all_content else "")
        + " found."
    )


def _print_export_results(results):
    success = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    for r in success:
        rprint(f"  [green]✓[/green] {r.output_path}")

    for r in failed:
        rprint(f"  [red]✗[/red] {r.error}")

    console.print(
        f"\n[bold]{len(success)} exported[/bold]"
        + (f", [red]{len(failed)} failed[/red]" if failed else "")
        + "."
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    app()


if __name__ == "__main__":
    main()
