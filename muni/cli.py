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

from muni.crawler import crawl
from muni.exporters.gdocs import export_all

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
    export: Annotated[bool, typer.Option(
        "--export", "-e",
        help="Export discovered Google Docs to markdown immediately",
    )] = True,
    dry_run: Annotated[bool, typer.Option(
        "--dry-run",
        help="Crawl and list links without exporting anything",
    )] = False,
    rate_limit: Annotated[float, typer.Option(
        "--rate-limit",
        help="Seconds between requests",
    )] = 1.0,
):
    """
    Crawl a URL, find Google Docs, and export them to markdown.
    """
    console.rule("[bold blue]muni.md[/bold blue]")
    console.print(f"[dim]Crawling:[/dim] {url}\n")

    # --- Crawl ---
    with console.status("Crawling page..."):
        result = crawl(url, collect_all=all_content, rate_limit=0)  # no delay on crawl itself

    if result.errors:
        for err in result.errors:
            rprint(f"[red]✗[/red] {err}")
        raise typer.Exit(1)

    # --- Report discovered links ---
    _print_discovered(result, all_content)

    if not result.gdocs:
        console.print("\n[yellow]No Google Docs found. Nothing to export.[/yellow]")
        raise typer.Exit(0)

    if dry_run:
        console.print("\n[dim]Dry run — skipping export.[/dim]")
        raise typer.Exit(0)

    if not export:
        raise typer.Exit(0)

    # --- Export ---
    console.print(f"\n[dim]Exporting {len(result.gdocs)} doc(s) to[/dim] {output}/\n")

    with console.status("Exporting..."):
        export_results = export_all(result.gdocs, output_dir=output, rate_limit=rate_limit)

    _print_export_results(export_results)


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
    from muni.crawler import DiscoveredLink, LinkType
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