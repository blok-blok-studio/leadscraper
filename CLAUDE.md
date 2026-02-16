# Lead Scraper — Bloblok Studio

## Project Overview
US-targeted local business lead scraper with full data enrichment pipeline. Python CLI tool that writes to PostgreSQL via Prisma.

## Tech Stack
- **Language:** Python 3.9+
- **Database:** PostgreSQL via Prisma Client Python (async)
- **HTTP:** httpx with retry (tenacity), rate limiting, rotating user agents
- **Parsing:** BeautifulSoup4 + lxml
- **CLI:** Click (wraps async with `asyncio.run()`)
- **Config:** YAML config files + .env for DATABASE_URL

## Architecture
- `main.py` — CLI entry point (Click commands, async bridge)
- `src/engine.py` — Core async orchestration: scrapers → DB → enrichment
- `src/scrapers/` — One scraper per source, all inherit `BaseScraper` (sync HTTP)
- `src/enrichment/` — Modular enrichment pipeline (tech stack, social, contacts, reviews)
- `src/database/` — Prisma client, field mapping (snake_case ↔ camelCase), repository pattern
- `prisma/schema.prisma` — Database schema (source of truth for tables)
- `src/utils/` — Cleaning, US locations, export, logging

## Key Patterns
- **Prisma schema** at `prisma/schema.prisma` — run `prisma db push` or `python main.py init-db` to sync
- **Field mapping** in `src/database/models.py` converts snake_case (scrapers) ↔ camelCase (Prisma)
- **Upsert logic** in `repository.py` deduplicates by phone → email → name+address
- **Quality score** (0-100) calculated from data completeness in `cleaning.py`
- All scrapers return raw dicts (snake_case) → cleaned by `clean_lead_data()` → converted to camelCase → upserted
- Enrichment runs after scraping on `isEnriched=False` leads
- Engine and repository are async; CLI wraps with `asyncio.run()`

## Commands
```bash
python main.py init-db                # Push Prisma schema to DB
python main.py run                    # Full pipeline
python main.py scrape -s yelp -cat "plumbers" -l "Miami, FL"
python main.py enrich --limit 200
python main.py export --format csv
python main.py stats
```

## Config
- `prisma/schema.prisma` — database schema
- `.env` — `DATABASE_URL` (Prisma connection string), scraper settings
- `config/default.yaml` — targeting, sources, enrichment modules, scheduling

## Adding a New Scraper
1. Create `src/scrapers/newsource.py` inheriting `BaseScraper`
2. Implement `search(category, location, max_pages) -> list[dict]` (return snake_case dicts)
3. Register in `src/scrapers/registry.py`
4. Add to `config/default.yaml` sources list
