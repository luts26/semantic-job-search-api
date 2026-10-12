from dataclasses import asdict

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.scraper.workua_scraper import WorkUaScraper
from app.services.job_ingestion_service import JobIngestionService


class ScrapeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run_workua_scrape(self, search_query: str, max_pages: int = 3) -> dict[str, int]:
        settings = get_settings()
        with WorkUaScraper(
            request_timeout=settings.workua_request_timeout,
            min_delay_seconds=settings.workua_min_delay_seconds,
            max_delay_seconds=settings.workua_max_delay_seconds,
        ) as scraper:
            scraped_jobs = scraper.scrape_pages(search_query=search_query, pages=max_pages)

        ingestion = JobIngestionService(self.db)
        stats = ingestion.upsert_many(scraped_jobs)
        return asdict(stats)
