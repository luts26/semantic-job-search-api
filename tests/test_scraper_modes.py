from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import admin
from app.api import search as search_api
from app.api import security
from app.db.session import get_db
from app.main import app
from app.models import Company, EmbeddingJobQueue, Job
from app.scraper.errors import SourceAccessDeniedError
from app.scraper.workua_scraper import WorkUaScraper
from app.services import index_service, scrape_service
from app.services.index_service import IndexService
from app.services.scrape_service import ScrapeService


@dataclass(slots=True)
class FakeSettings:
    admin_api_key: str = "test_admin_key"
    scraper_mode: str = "fixture"
    workua_request_timeout: float = 20.0
    workua_min_delay_seconds: float = 0.0
    workua_max_delay_seconds: float = 0.0
    embedding_provider: str = "hash"
    embedding_vector_size: int = 8
    embedding_max_attempts: int = 5


class FakeQdrantIndex:
    points = []

    def collection_exists(self):
        return True

    def ensure_collection(self, vector_size):
        self.vector_size = vector_size

    def upsert_points(self, points):
        self.points.extend(points)


def test_successful_fixture_import_and_indexing(db_session, monkeypatch):
    FakeQdrantIndex.points = []
    monkeypatch.setattr(scrape_service, "get_settings", lambda: FakeSettings(scraper_mode="fixture"))
    monkeypatch.setattr(index_service, "get_settings", lambda: FakeSettings(scraper_mode="fixture"))
    monkeypatch.setattr(index_service, "QdrantIndex", FakeQdrantIndex)

    scrape_result = ScrapeService(db_session).run_workua_scrape(search_query="Java Developer", max_pages=3)
    assert scrape_result == {
        "total_scraped": 3,
        "jobs_created": 3,
        "jobs_updated": 0,
        "companies_created": 3,
    }
    assert db_session.query(Job).count() == 3
    assert db_session.query(Company).count() == 3
    assert db_session.query(EmbeddingJobQueue).count() == 3

    index_result = IndexService(db_session).run(batch_size=10)
    assert index_result["indexed"] == 3
    assert len(FakeQdrantIndex.points) == 3


def test_duplicate_fixture_import_updates_existing_jobs(db_session, monkeypatch):
    monkeypatch.setattr(scrape_service, "get_settings", lambda: FakeSettings(scraper_mode="fixture"))

    first = ScrapeService(db_session).run_workua_scrape(search_query="Java Developer", max_pages=3)
    second = ScrapeService(db_session).run_workua_scrape(search_query="Java Developer", max_pages=3)

    assert first["jobs_created"] == 3
    assert second["jobs_created"] == 0
    assert second["jobs_updated"] == 3
    assert db_session.query(Job).count() == 3
    assert db_session.query(EmbeddingJobQueue).count() == 3


def test_invalid_scraper_mode(db_session, monkeypatch):
    monkeypatch.setattr(scrape_service, "get_settings", lambda: FakeSettings(scraper_mode="invalid"))

    with pytest.raises(ValueError, match="SCRAPER_MODE"):
        ScrapeService(db_session).run_workua_scrape(search_query="Java Developer", max_pages=1)


def test_live_source_cloudflare_403(monkeypatch):
    scraper = WorkUaScraper(min_delay_seconds=0, max_delay_seconds=0)

    def fake_get(url, params=None):
        del url, params
        return httpx.Response(
            status_code=403,
            headers={"cf-mitigated": "challenge"},
            request=httpx.Request("GET", "https://www.work.ua/jobs-Python+Developer/"),
            text="<html>challenge</html>",
        )

    monkeypatch.setattr(scraper._client, "get", fake_get)

    with pytest.raises(SourceAccessDeniedError) as exc_info:
        scraper.fetch_job_links(search_query="Java Developer", page=1)

    assert exc_info.value.source == "work.ua"
    assert exc_info.value.status_code == 403
    scraper.close()


def test_safe_api_error_response(db_session, monkeypatch):
    class DeniedScrapeService:
        def __init__(self, db):
            del db

        def run_workua_scrape(self, search_query, max_pages):
            del search_query, max_pages
            raise SourceAccessDeniedError("work.ua", 403, "raw technical details")

    def override_get_db():
        yield db_session

    monkeypatch.setattr(security, "get_settings", lambda: FakeSettings(admin_api_key="test_admin_key"))
    monkeypatch.setattr(admin, "ScrapeService", DeniedScrapeService)
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(
            "/admin/scrape/run",
            headers={"X-API-Key": "test_admin_key"},
            json={"search_query": "Java Developer", "max_pages": 1},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "source_access_denied"
    assert "raw technical details" not in response.text


def test_parse_sanitized_workua_search_fixture_without_network():
    html = Path("tests/fixtures/workua_search_page.html").read_text(encoding="utf-8")
    jobs = WorkUaScraper(min_delay_seconds=0, max_delay_seconds=0).parse_search_page_jobs(html)

    assert [job.source_job_id for job in jobs] == ["910001", "910002"]
    assert jobs[0].title == "Java Backend Developer"
    assert jobs[0].company_name == "Northstar Systems"
    assert jobs[0].city == "Kyiv"
    assert "Fictional backend role" in jobs[0].description_raw


def test_admin_endpoint_without_api_key_returns_401(monkeypatch):
    monkeypatch.setattr(security, "get_settings", lambda: FakeSettings(admin_api_key="expected_test_key"))

    response = TestClient(app).post(
        "/admin/scrape/run",
        json={"search_query": "Java Developer", "max_pages": 1},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "error": "unauthorized",
            "message": "Valid API key required.",
        }
    }
    assert "expected_test_key" not in response.text


def test_admin_endpoint_wrong_api_key_returns_401(monkeypatch):
    monkeypatch.setattr(security, "get_settings", lambda: FakeSettings(admin_api_key="expected_test_key"))

    response = TestClient(app).post(
        "/admin/scrape/run",
        headers={"X-API-Key": "wrong_test_key"},
        json={"search_query": "Java Developer", "max_pages": 1},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "unauthorized"
    assert "expected_test_key" not in response.text
    assert "wrong_test_key" not in response.text


def test_admin_endpoint_with_valid_api_key_passes_auth(db_session, monkeypatch):
    class SuccessfulScrapeService:
        def __init__(self, db):
            del db

        def run_workua_scrape(self, search_query, max_pages):
            assert search_query == "Java Developer"
            assert max_pages == 1
            return {
                "total_scraped": 3,
                "jobs_created": 3,
                "jobs_updated": 0,
                "companies_created": 3,
            }

    def override_get_db():
        yield db_session

    monkeypatch.setattr(security, "get_settings", lambda: FakeSettings(admin_api_key="test_admin_key"))
    monkeypatch.setattr(admin, "ScrapeService", SuccessfulScrapeService)
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(
            "/admin/scrape/run",
            headers={"X-API-Key": "test_admin_key"},
            json={"search_query": "Java Developer", "max_pages": 1},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total_scraped"] == 3
    assert "test_admin_key" not in response.text


def test_health_is_public_without_api_key():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_search_is_public_without_admin_dependency(db_session, monkeypatch):
    class FakeSearchService:
        def __init__(self, db):
            del db

        def search(self, query, limit, city=None, company=None, role_category=None):
            return {
                "query": query,
                "applied_filters": {
                    "city": city,
                    "company": company,
                    "role_category": role_category,
                },
                "results": [],
            }

    def override_get_db():
        yield db_session

    monkeypatch.setattr(search_api, "SearchService", FakeSearchService)
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(
            "/search",
            json={"query": "Java backend developer", "limit": 10},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["query"] == "Java backend developer"
