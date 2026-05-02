# muni.md
Crawler and scraper for archiving public records in markdown

muni.md/
├── muni/
│   ├── __init__.py
│   ├── cli.py            # typer or click entrypoint
│   ├── crawler.py        # finds Google Doc links on a site
│   ├── exporters/
│   │   ├── gdocs.py      # Google Doc → markdown
│   │   └── pdf.py        # for later
│   ├── pipeline.py       # orchestrates crawl → export → save
│   └── models.py         # Document dataclass (url, title, date, source)
├── output/               # gitignored, where markdown lands
├── tests/                # scripts for testing packages
├── pyproject.toml
└── README.md