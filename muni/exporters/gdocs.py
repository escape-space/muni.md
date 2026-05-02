"""
muni/exporters/gdocs.py

Exports public Google Docs to markdown files.
"""

import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from muni.crawler import DiscoveredLink


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class ExportResult:
    link: DiscoveredLink
    doc_id: str
    output_path: Path | None = None
    success: bool = False
    error: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GDOC_ID_PATTERN = re.compile(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; muni.md/0.1; "
        "+https://github.com/muni-md/muni.md)"
    )
}


def _extract_doc_id(url: str) -> str | None:
    match = GDOC_ID_PATTERN.search(url)
    return match.group(1) if match else None


def _export_url(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/export?format=md"


def _safe_filename(anchor_text: str, doc_id: str) -> str:
    """
    Turn anchor text into a safe filename, falling back to doc_id.
    e.g. "Board Meeting Agenda – Oct 2024" → "board-meeting-agenda-oct-2024.md"
    """
    if anchor_text:
        name = anchor_text.lower()
        name = re.sub(r"[^\w\s-]", "", name)       # strip special chars
        name = re.sub(r"[\s_]+", "-", name).strip("-")  # spaces → hyphens
        name = name[:80]                             # cap length
        if name:
            return f"{name}.md"
    return f"{doc_id}.md"


# ---------------------------------------------------------------------------
# Core exporter
# ---------------------------------------------------------------------------

def export_doc(
    link: DiscoveredLink,
    output_dir: Path,
    rate_limit: float = 1.0,
) -> ExportResult:
    """
    Export a single Google Doc to a markdown file.

    Args:
        link:        A DiscoveredLink with a Google Doc URL.
        output_dir:  Directory to write the .md file into.
        rate_limit:  Seconds to wait after the request.

    Returns:
        ExportResult indicating success or failure.
    """
    doc_id = _extract_doc_id(link.url)
    if not doc_id:
        return ExportResult(
            link=link,
            doc_id="",
            success=False,
            error=f"Could not extract doc ID from URL: {link.url}",
        )

    result = ExportResult(link=link, doc_id=doc_id)
    url = _export_url(doc_id)

    try:
        resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=20)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        result.error = f"HTTP {e.response.status_code} for {url}"
        return result
    except httpx.RequestError as e:
        result.error = f"Request error for {url}: {e}"
        return result
    finally:
        time.sleep(rate_limit)

    # Write to file
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(link.anchor_text, doc_id)
    output_path = output_dir / filename

    # Handle filename collisions by appending doc_id suffix
    if output_path.exists():
        stem = output_path.stem
        output_path = output_dir / f"{stem}-{doc_id[:8]}.md"

    output_path.write_text(resp.text, encoding="utf-8")

    result.output_path = output_path
    result.success = True
    return result


def export_all(
    links: list[DiscoveredLink],
    output_dir: Path,
    rate_limit: float = 1.0,
) -> list[ExportResult]:
    """
    Export a list of Google Doc links to markdown files.

    Args:
        links:       List of DiscoveredLinks (typically from CrawlResult.gdocs).
        output_dir:  Directory to write files into.
        rate_limit:  Seconds between requests.

    Returns:
        List of ExportResults, one per link.
    """
    results = []
    for link in links:
        result = export_doc(link, output_dir=output_dir, rate_limit=rate_limit)
        results.append(result)
    return results