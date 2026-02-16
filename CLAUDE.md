# Lead Scraper — Bloblok Studio

## Project Overview
US-targeted local business lead scraper with full data enrichment pipeline. Python CLI tool that writes to PostgreSQL.

## Tech Stack
- **Language:** Python 3.11+
- **Database:** PostgreSQL via SQLAlchemy ORM
- **HTTP:** httpx with retry (tenacity), rate limiting, rotating user agents
- **Parsing:** BeautifulSoup4 + lxml
- **CLI:** Click
- **Config:** YAML config files + .env for secrets

## Architecture
- `main.py` — CLI entry point (Click commands)
- `src/engine.py` — Core orchestration: ties scrapers → DB → enrichment
- `src/scrapers/` — One scraper per source, all inherit `BaseScraper`
- `src/enrichment/` — Modular enrichment pipeline (tech stack, social, contacts, reviews)
- `src/database/` — SQLAlchemy models, connection pool, repository pattern
- `src/utils/` — Cleaning, US locations, export, logging

## Key Patterns
- **Upsert logic** in `repository.py` deduplicates by phone → email → name+address
- **Quality score** (0-100) calculated from data completeness in `cleaning.py`
- All scrapers return raw dicts → cleaned by `clean_lead_data()` → upserted via repository
- Enrichment runs after scraping on `is_enriched=False` leads

## Commands
```bash
python main.py run                    # Full pipeline
python main.py scrape -s yelp -cat "plumbers" -l "Miami, FL"
python main.py enrich --limit 200
python main.py export --format csv
python main.py stats
python main.py init-db
```

## Config
- `config/default.yaml` — targeting, sources, enrichment modules, scheduling
- `.env` — DB credentials, scraper settings, proxy config

## Adding a New Scraper
1. Create `src/scrapers/newsource.py` inheriting `BaseScraper`
2. Implement `search(category, location, max_pages) -> list[dict]`
3. Register in `src/scrapers/registry.py`
4. Add to `config/default.yaml` sources list
