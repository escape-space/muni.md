"""
muni/pipeline.py

Orchestrates crawl → export into a single reusable function.
Designed to be called from the CLI, a scheduler, or directly in Python.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from muni.crawler import CrawlResult, crawl
from muni.exporters.gdocs import ExportResult, export_all


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    seed_url: str
    started_at: str
    finished_at: str
    crawl: CrawlResult
    exports: list[ExportResult] = field(default_factory=list)

    @property
    def succeeded(self) -> list[ExportResult]:
        return [r for r in self.exports if r.success]

    @property
    def failed(self) -> list[ExportResult]:
        return [r for r in self.exports if not r.success]

    def summary(self) -> dict:
        return {
            "seed_url": self.seed_url,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "gdocs_found": len(self.crawl.gdocs),
            "pdfs_found": len(self.crawl.pdfs),
            "html_pages_found": len(self.crawl.html_pages),
            "exports_succeeded": len(self.succeeded),
            "exports_failed": len(self.failed),
            "crawl_errors": self.crawl.errors,
            "export_errors": [r.error for r in self.failed],
        }


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run(
    seed_url: str,
    output_dir: Path,
    collect_all: bool = False,
    rate_limit: float = 1.0,
    dry_run: bool = False,
    write_manifest: bool = True,
) -> PipelineResult:
    """
    Run the full crawl → export pipeline for a seed URL.

    Args:
        seed_url:        Page to crawl for Google Doc links.
        output_dir:      Root directory for output files.
        collect_all:     Also collect PDFs and HTML links during crawl.
        rate_limit:      Seconds between HTTP requests.
        dry_run:         Crawl only, skip exporting.
        write_manifest:  Write a manifest.json summarizing the run.

    Returns:
        PipelineResult with crawl and export details.
    """
    started_at = _now()

    # --- Crawl ---
    crawl_result = crawl(
        seed_url,
        collect_all=collect_all,
        rate_limit=rate_limit,
    )

    # --- Export ---
    export_results = []
    if not dry_run and crawl_result.gdocs:
        export_results = export_all(
            crawl_result.gdocs,
            output_dir=output_dir,
            rate_limit=rate_limit,
        )

    finished_at = _now()

    result = PipelineResult(
        seed_url=seed_url,
        started_at=started_at,
        finished_at=finished_at,
        crawl=crawl_result,
        exports=export_results,
    )

    # --- Manifest ---
    if write_manifest and not dry_run:
        _write_manifest(result, output_dir)

    return result


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def _write_manifest(result: PipelineResult, output_dir: Path):
    """
    Write a manifest.json to output_dir summarizing the pipeline run.
    Appends to existing manifest if one exists, so runs accumulate.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"

    # Load existing runs if present
    runs = []
    if manifest_path.exists():
        try:
            runs = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    # Build this run's entry
    run_entry = result.summary()
    run_entry["documents"] = [
        {
            "doc_id": r.doc_id,
            "source_url": r.link.url,
            "anchor_text": r.link.anchor_text,
            "output_path": str(r.output_path) if r.output_path else None,
            "success": r.success,
            "error": r.error,
        }
        for r in result.exports
    ]

    runs.append(run_entry)
    manifest_path.write_text(json.dumps(runs, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()