# Semantic Job Search API - Project Plan

## 1) Goal
Build a backend service that:
1. Accepts a job search phrase such as `Java Developer`, `Python Developer`, `React Developer`, or `Unreal Engine`.
2. Scrapes matching vacancies from Work.ua.
3. Stores normalized entities in PostgreSQL.
4. Prepares embeddings for semantic retrieval in Qdrant.
5. Exposes a FastAPI search API that combines semantic search with metadata filters.

---

## 2) Functional Scope (Current MVP)
- Source: `work.ua` search pages generated from a validated `search_query`.
- Entities:
  - Job
  - Company
  - Embedding queue item
- Search examples to support:
  - `Python backend developer in Kyiv`
  - `React developer`
  - `DevOps engineer with Kubernetes`
  - `Unreal Engine`

---

## 3) Architecture
- **Scraper service**
  - Builds Work.ua search URLs from a validated search phrase.
  - Fetches list pages and job pages.
  - Keeps pagination, retry/backoff, and polite random delay.
  - Parses normalized fields.
  - Upserts companies and jobs into PostgreSQL.

- **Embedding/indexing service**
  - Reads jobs waiting for embedding.
  - Builds text representation from title, company, city, employment type, category, requirements, and description.
  - Generates embeddings through a configurable provider.
  - Upserts vectors to Qdrant with payload (`job_id`, `company`, `city`, `employment_type`, `role_category`, `url`).

- **Search API (FastAPI)**
  - Accepts a natural-language query and optional metadata filters.
  - Produces a query embedding.
  - Runs Qdrant vector search with payload filters.
  - Enriches ranked results from PostgreSQL.

- **Infrastructure**
  - Docker Compose services: `api`, `postgres`, `qdrant`, `adminer`.
  - PostgreSQL database: `semantic_jobs`.
  - PostgreSQL user: `semantic_jobs_app`.
  - Qdrant collection: `job_vacancies`.

---

## 4) Data Model (PostgreSQL)

### `companies`
- `id` (PK)
- `name` (unique)
- `website` (nullable)
- `created_at`, `updated_at`

### `jobs`
- `id` (PK)
- `source` (`work.ua`)
- `source_job_id` (unique with source)
- `url` (unique)
- `title`
- `company_id` (FK -> companies.id)
- `city` (nullable)
- `employment_type` (nullable)
- `description_raw`
- `requirements_raw` (nullable)
- `role_category`
- `published_at` (nullable)
- `is_active` (bool)
- `last_seen_at`
- `created_at`, `updated_at`

Supported role categories:
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

### `embedding_jobs_queue`
- `job_id` (FK)
- `status` (`pending`, `processing`, `done`, `failed`)
- `attempts`
- `last_error`
- `updated_at`

---

## 5) Qdrant Collection Design
- Collection: `job_vacancies`
- Vector size: depends on embedding settings (`EMBEDDING_VECTOR_SIZE` for hash provider)
- Distance: `Cosine`
- Point ID: `job_id`
- Payload:
  - `job_id`
  - `title`
  - `company`
  - `company_normalized`
  - `city`
  - `city_normalized`
  - `employment_type`
  - `role_category`
  - `url`
  - `source`

---

## 6) API Endpoints (Current MVP)
- `GET /health`
- `POST /admin/scrape/run`
  - Request:
    - `search_query: str` (2-100 chars)
    - `max_pages: int = 3` (1-30)
- `POST /admin/index/run`
  - Request:
    - `batch_size: int = 50`
- `POST /search`
  - Request:
    - `query: str`
    - `city: Optional[str]`
    - `company: Optional[str]`
    - `role_category: Optional[str]`
    - `limit: int = 10`
  - Response:
    - ranked list with score and job metadata

---

## 7) Role Classification Strategy
- Current implementation: rule-based regex/keyword mapping into universal software job categories.
- Examples:
  - backend: Java, Python, FastAPI, Spring
  - frontend: React, Vue, Angular, TypeScript
  - devops: Kubernetes, Docker, Terraform, cloud keywords
  - qa: QA, test automation, manual testing
  - game_development: game developer, gameplay programmer, Unity, Unreal
- LLM classification is intentionally out of scope for this stage.

---

## 8) Reliability & Clean Code Requirements
- Parsing logic isolated from FastAPI endpoints.
- Retry with exponential backoff for HTTP requests.
- Random delay between source requests.
- Idempotent upsert by source identifiers.
- Safe re-indexing through an embedding queue.

---

## 9) Delivery Plan

### Phase 1 - Portfolio Preparation
- Rename project concept to Semantic Job Search API.
- Generalize Work.ua scraper through `search_query`.
- Replace domain-specific job role categories with universal categories.
- Clean repository-local generated files and ignore local configuration.
- Keep admin authentication, CI, full test suite, production deployment, and major refactors out of scope.

### Later Phases
- Add admin authentication.
- Add focused unit/integration tests.
- Add CI checks.
- Prepare production deployment guidance.

---

## 10) Known Risks and Mitigations
- **Rate limiting / anti-bot from source**
  - Backoff, request delay, and conservative pagination limits.
- **HTML layout changes on Work.ua**
  - Keep parser logic isolated for targeted updates.
- **Embedding model switch cost**
  - Keep provider and vector size configurable.

---

## 11) Current Definition of Done
- Scraper accepts a validated `search_query`.
- Jobs are stored in PostgreSQL with universal role categories.
- Qdrant payload supports metadata filtering.
- README examples match current implementation.
- Configuration uses the Semantic Job Search naming scheme.
