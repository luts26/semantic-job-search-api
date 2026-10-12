# Semantic Job Search API

Backend service for collecting job vacancies from Work.ua by a user-provided search phrase, storing normalized data in PostgreSQL, preparing vectors in Qdrant, and exposing semantic search with metadata filters through FastAPI.

## Current status
- [x] FastAPI application skeleton
- [x] PostgreSQL schema and Alembic migrations
- [x] Work.ua scraper with retry/backoff, delay, pagination, and upsert
- [x] Embedding pipeline with hash embeddings for local development
- [x] Qdrant indexing
- [x] Semantic search API with metadata filters

## Project names
- Application title: `Semantic Job Search API`
- Project slug: `semantic_job_search`
- PostgreSQL database: `semantic_jobs`
- PostgreSQL user: `semantic_jobs_app`
- Qdrant collection: `job_vacancies`

## Quick start

1. Prepare environment:
```bash
cp .env.example .env
```

2. Start services:
```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
```

3. Apply migrations:
```bash
docker compose exec api alembic upgrade head
```

4. Healthcheck:
```bash
curl http://localhost:8000/health
```

## Data collection

The scraper has two modes:
- `SCRAPER_MODE=fixture` (default in `.env.example`): imports fictional local demo vacancies. Use this for demos, smoke checks, and portfolio review without depending on external access.
- `SCRAPER_MODE=live`: fetches matching vacancies from Work.ua. External sources may restrict automated access, and the API returns a structured `source_access_denied` error if access is blocked.

Run scraper for any supported search phrase:
```bash
curl -X POST http://localhost:8000/admin/scrape/run \
  -H "Content-Type: application/json" \
  -d '{"search_query":"Java Developer","max_pages":3}'
```

`search_query` must be 2-100 characters. `max_pages` must be 1-30. In fixture mode, `search_query` is still validated but the local fictional dataset is imported.

To use live mode, set:
```env
SCRAPER_MODE=live
```

This project does not implement CAPTCHA bypassing, Cloudflare circumvention, proxy rotation, or stealth-browser techniques.

Run indexing into Qdrant:
```bash
curl -X POST http://localhost:8000/admin/index/run \
  -H "Content-Type: application/json" \
  -d '{"batch_size":50}'
```

## Semantic search

Endpoint:
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Python backend developer in Kyiv","limit":10}'
```

Optional explicit filters:
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"React developer","city":"Kyiv","role_category":"frontend","limit":10}'
```

Supported `role_category` values:
```text
backend
frontend
fullstack
mobile
devops
qa
data
machine_learning
game_development
design
management
other
```

## Embedding provider modes
- `EMBEDDING_PROVIDER=hash`: local deterministic embeddings for development and smoke checks.
- `EMBEDDING_PROVIDER=openai`: OpenAI embeddings (`OPENAI_API_KEY` required).

## Notes
- Search combines vector retrieval from Qdrant with metadata filtering by payload (`city`, `company`, `role_category`) and PostgreSQL enrichment.
- After each new scrape, run indexing to refresh vectors.
- Admin endpoints are currently internal utility endpoints and do not yet include authentication.
- The scraper is scoped to `https://www.work.ua` and does not accept arbitrary external domains.
