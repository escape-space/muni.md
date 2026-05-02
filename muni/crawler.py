"""
muni/crawler.py

Crawls a seed URL and finds Google Doc links.
With --all flag, also collects PDFs and plain HTML page links.
"""

import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin, urlparse
import re
import time


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class LinkType(str, Enum):
    GDOC = "gdoc"
    PDF = "pdf"
    HTML = "html"


@dataclass
class DiscoveredLink:
    url: str
    link_type: LinkType
    anchor_text: str = ""
    source_url: str = ""


@dataclass
class CrawlResult:
    seed_url: str
    gdocs: list[DiscoveredLink] = field(default_factory=list)
    pdfs: list[DiscoveredLink] = field(default_factory=list)
    html_pages: list[DiscoveredLink] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def all_links(self) -> list[DiscoveredLink]:
        return self.gdocs + self.pdfs + self.html_pages


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GDOC_PATTERN = re.compile(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; muni.md/0.1; "
        "+https://github.com/muni-md/muni.md)"
    )
}


def _classify_link(href: str) -> LinkType | None:
    """Return the LinkType for a given href, or None if not interesting."""
    if GDOC_PATTERN.search(href):
        return LinkType.GDOC
    if href.lower().endswith(".pdf"):
        return LinkType.PDF
    parsed = urlparse(href)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return LinkType.HTML
    return None


def _normalize_gdoc_url(url: str) -> str:
    """Strip query params / fragments from a Google Doc URL for deduplication."""
    match = GDOC_PATTERN.search(url)
    if match:
        doc_id = match.group(1)
        return f"https://docs.google.com/document/d/{doc_id}"
    return url


def _fetch(url: str, timeout: int = 15) -> httpx.Response | None:
    """Fetch a URL, returning None on error."""
    try:
        resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=timeout)
        resp.raise_for_status()
        return resp
    except httpx.HTTPStatusError as e:
        return None
    except httpx.RequestError as e:
        return None


# ---------------------------------------------------------------------------
# Core crawler
# ---------------------------------------------------------------------------

def crawl(
    seed_url: str,
    collect_all: bool = False,
    same_domain_only: bool = True,
    rate_limit: float = 1.0,
) -> CrawlResult:
    """
    Crawl a seed URL and return discovered links.

    Args:
        seed_url:        The page to crawl.
        collect_all:     If True, also collect PDFs and HTML page links.
                         If False (default), only Google Doc links are returned.
        same_domain_only: When collect_all=True, restrict HTML links to the
                          same domain as the seed.
        rate_limit:      Seconds to wait between requests (polite default: 1.0).

    Returns:
        CrawlResult with categorized links.
    """
    result = CrawlResult(seed_url=seed_url)
    seed_domain = urlparse(seed_url).netloc

    seen_urls: set[str] = set()

    resp = _fetch(seed_url)
    if resp is None:
        result.errors.append(f"Failed to fetch seed URL: {seed_url}")
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.find_all("a", href=True):
        raw_href = a["href"].strip()
        if not raw_href or raw_href.startswith("#"):
            continue

        # Resolve relative URLs
        href = urljoin(seed_url, raw_href)
        link_type = _classify_link(href)

        if link_type is None:
            continue

        # Normalize Google Doc URLs for deduplication
        if link_type == LinkType.GDOC:
            href = _normalize_gdoc_url(href)

        # Skip already-seen
        if href in seen_urls:
            continue
        seen_urls.add(href)

        # Enforce same-domain for HTML links when collect_all is on
        if (
            link_type == LinkType.HTML
            and same_domain_only
            and urlparse(href).netloc != seed_domain
        ):
            continue

        link = DiscoveredLink(
            url=href,
            link_type=link_type,
            anchor_text=a.get_text(strip=True),
            source_url=seed_url,
        )

        if link_type == LinkType.GDOC:
            result.gdocs.append(link)
        elif collect_all and link_type == LinkType.PDF:
            result.pdfs.append(link)
        elif collect_all and link_type == LinkType.HTML:
            result.html_pages.append(link)

        time.sleep(rate_limit) if link_type != LinkType.GDOC else None

    return result


# ---------------------------------------------------------------------------
# Quick manual test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    collect_all = "--all" in sys.argv

    result = crawl(url, collect_all=collect_all)

    print(f"\n=== Crawl results for {result.seed_url} ===\n")
    print(f"Google Docs ({len(result.gdocs)}):")
    for link in result.gdocs:
        print(f"  [{link.anchor_text}] {link.url}")

    if collect_all:
        print(f"\nPDFs ({len(result.pdfs)}):")
        for link in result.pdfs:
            print(f"  [{link.anchor_text}] {link.url}")

        print(f"\nHTML pages ({len(result.html_pages)}):")
        for link in result.html_pages:
            print(f"  [{link.anchor_text}] {link.url}")

    if result.errors:
        print(f"\nErrors:")
        for e in result.errors:
            print(f"  {e}")