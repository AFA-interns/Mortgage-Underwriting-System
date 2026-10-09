# Multi-Source Property Scraper

## Overview

This package scrapes property listings from multiple real estate websites,
merges the data, fills missing fields, and computes quality scores.

## Architecture

```
SquareYards ──┐
              ├──→ Merger ──→ Enricher ──→ PostgreSQL
Housing.com ──┤
              │
MagicBricks ──┘
```

## Files

| File | Purpose |
|---|---|
| `playwright_base.py` | Base scraper with Playwright (JS rendering, auto-scroll, retries) |
| `squareyards_v2.py` | SquareYards scraper (Playwright + JSON-LD extraction) |
| `jsonld_extractor.py` | Extract structured data from `<script>` tags |
| `matcher.py` | Fuzzy property matching across sources |
| `merger.py` | Multi-source data merger with NULL filling |
| `quality.py` | Data quality scoring (0-100) |
| `runner.py` | CLI entry point |

## Setup

```bash
# Install dependencies
pip install playwright beautifulsoup4 lxml
python -m playwright install chromium

# Or use the setup script
python setup_playwright.py
```

## Usage

### Command Line

```bash
# Scrape Bangalore 2 BHK listings
python -m property_data.scrapers.runner --city Bangalore --bhk 2

# Scrape specific locality
python -m property_data.scrapers.runner --city Mumbai --locality "Andheri West" --bhk 3

# Scrape without saving to database
python -m property_data.scrapers.runner --city Hyderabad --bhk 2 --no-save

# Limit results
python -m property_data.scrapers.runner --city Pune --bhk 2 --limit 10
```

### Python API

```python
import asyncio
from property_data.scrapers.squareyards_v2 import SquareYardsScraperV2
from property_data.scrapers.merger import merge_sources

async def main():
    scraper = SquareYardsScraperV2(headless=True)
    listings = await scraper.fetch_listings(
        city="Bangalore",
        locality="Whitefield",
        bhk=2,
        limit=20,
    )
    print(f"Found {len(listings)} listings")

asyncio.run(main())
```

## Data Quality Scoring

Each listing gets a quality score (0-100) based on:

| Factor | Weight | Description |
|---|---|---|
| Completeness | 50% | How many critical fields are filled |
| Freshness | 20% | How recent the listing is |
| Source diversity | 30% | How many sources agree (max 20 points) |

Quality labels:
- **80-100**: Excellent — ready for comps analysis
- **60-79**: Good — usable with minor gaps
- **40-59**: Fair — usable with caution
- **20-39**: Poor — needs enrichment
- **0-19**: Unusable — discard

## Database Schema

The `property_listings` table includes:

| Column | Type | Description |
|---|---|---|
| `data_quality_score` | FLOAT | Overall quality (0-100) |
| `quality_completeness` | FLOAT | Field completeness (0-100) |
| `quality_freshness` | FLOAT | Listing recency (0-100) |
| `source_count` | INTEGER | Number of sources |
| `imputed_fields` | JSON | List of fields filled from other sources |
| `sources` | JSON | List of source names |

## Adding a New Scraper

1. Create a new file in `property_data/scrapers/`
2. Extend `PlaywrightBaseScraper`
3. Implement `fetch_listings()` method
4. Add to `runner.py` sources list

Example:

```python
from property_data.scrapers.playwright_base import PlaywrightBaseScraper

class NewScraper(PlaywrightBaseScraper):
    SOURCE = "new_source"
    BASE_URL = "https://www.newsource.com"

    async def fetch_listings(self, city, locality=None, bhk=2, **kwargs):
        # Implement scraping logic
        pass
```

## Testing

```bash
pytest tests/test_jsonld_extractor.py -v
pytest tests/test_matcher.py -v
pytest tests/test_merger.py -v
```

## Roadmap

- [ ] Housing.com scraper
- [ ] MagicBricks scraper
- [ ] Proxy rotation support
- [ ] Scheduled scraping (cron)
- [ ] RERA data integration
- [ ] Geocoding enrichment
