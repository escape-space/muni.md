# test_export.py
from pathlib import Path
from muni.crawler import DiscoveredLink, LinkType
from muni.exporters.gdocs import export_all

links = [
    DiscoveredLink(
        url="https://docs.google.com/document/d/1mEgf4lp4G7LbXkp2SmYHwcs5oyJGA1jEECgUtD3Tm3c",
        link_type=LinkType.GDOC,
        anchor_text="Board Meeting Agenda 3.Mar.2026",
    ),
]

results = export_all(links, output_dir=Path("output"))

for r in results:
    if r.success:
        print(f"✓ {r.output_path}")
    else:
        print(f"✗ {r.error}")