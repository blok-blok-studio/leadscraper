# Lead Scraper — Bloblok Studio

US-targeted local business lead scraper with full enrichment. Scrapes from YellowPages, BBB, and Yelp, then enriches leads with tech stack analysis, social media discovery, owner/decision maker info, and review data. All data stored in PostgreSQL.

## Quick Start

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Set up your environment
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# 3. Initialize the database
python main.py init-db

# 4. Run a targeted scrape
python main.py scrape --source yellowpages --category "plumbers" --location "Miami, FL"

# 5. Or run the full pipeline from config
python main.py run
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python main.py run` | Full pipeline (scrape all sources + enrich) |
| `python main.py scrape -s yelp -cat "dentists" -l "Austin, TX"` | Scrape single source |
| `python main.py enrich --limit 200` | Enrich unenriched leads |
| `python main.py export --format csv --state FL` | Export to CSV/JSON |
| `python main.py stats` | Show database stats |
| `python main.py init-db` | Create database tables |
| `python main.py schedule` | Run on a schedule |

## Configuration

Edit `config/default.yaml` to customize:
- **Target states/cities** — narrow or widen geography
- **Categories** — which business types to scrape
- **Sources** — yellowpages, bbb, yelp
- **Enrichment modules** — tech stack, social media, contacts, reviews
- **Scheduling** — automated runs

## Data Fields Captured

**Basic:** name, phone, email, website, full address
**Decision Maker:** owner name, title, email, phone, LinkedIn
**Business:** employee count, revenue estimate, year established, type
**Online Presence:** Facebook, Instagram, Twitter, LinkedIn, YouTube, TikTok
**Tech Stack:** CMS platform, analytics, ad tools, SSL, mobile-friendly
**Reviews:** Google rating/count, Yelp rating/count, BBB rating/accredited
**Ad Indicators:** Google Ads, Facebook Ads, Google Business Profile
**Quality:** 0-100 quality score based on data completeness

## Project Structure

```
leadscraper/
├── main.py                    # CLI entry point
├── config/
│   └── default.yaml           # Scraper configuration
├── src/
│   ├── config.py              # Config & env loader
│   ├── engine.py              # Core orchestration engine
│   ├── database/
│   │   ├── models.py          # SQLAlchemy models (Lead, ScrapeJob)
│   │   ├── connection.py      # DB engine & sessions
│   │   └── repository.py      # Data access layer
│   ├── scrapers/
│   │   ├── base.py            # Base scraper class
│   │   ├── http_client.py     # HTTP client with retry/rate limit
│   │   ├── registry.py        # Scraper factory
│   │   ├── yellowpages.py     # YellowPages scraper
│   │   ├── bbb.py             # BBB scraper
│   │   └── yelp.py            # Yelp scraper
│   ├── enrichment/
│   │   ├── base.py            # Base enricher class
│   │   ├── pipeline.py        # Enrichment orchestrator
│   │   ├── tech_stack.py      # Website tech analysis
│   │   ├── social_media.py    # Social link discovery
│   │   ├── contact_enrichment.py # Owner/contact finder
│   │   └── reviews.py         # Google/Yelp review data
│   └── utils/
│       ├── cleaning.py        # Data normalization & validation
│       ├── us_locations.py    # US city/state database
│       ├── export.py          # CSV/JSON export
│       └── logger.py          # Logging setup
├── requirements.txt
├── .env.example
└── .gitignore
```
