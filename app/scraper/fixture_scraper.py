import json
from datetime import datetime
from pathlib import Path

from app.scraper.schemas import ScrapedJob


class FixtureJobScraper:
    def __init__(self, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path or Path(__file__).parent / "fixtures" / "workua_jobs.json"

    def scrape_pages(self, search_query: str, pages: int = 3) -> list[ScrapedJob]:
        del search_query, pages
        with self.fixture_path.open(encoding="utf-8") as fixture_file:
            payload = json.load(fixture_file)

        return [self._to_scraped_job(item) for item in payload["jobs"]]

    @staticmethod
    def _to_scraped_job(item: dict) -> ScrapedJob:
        published_at = item.get("published_at")
        return ScrapedJob(
            source_job_id=str(item["source_job_id"]),
            url=str(item["url"]),
            title=str(item["title"]),
            company_name=str(item["company_name"]),
            city=item.get("city"),
            employment_type=item.get("employment_type"),
            description_raw=str(item["description_raw"]),
            requirements_raw=item.get("requirements_raw"),
            published_at=datetime.fromisoformat(published_at) if published_at else None,
        )
