import json
import random
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.scraper.schemas import ScrapedJob


class WorkUaScraper:
    BASE_URL = "https://www.work.ua"
    BASE_HOST = "www.work.ua"

    def __init__(
        self,
        request_timeout: float = 20.0,
        min_delay_seconds: float = 0.6,
        max_delay_seconds: float = 1.5,
    ) -> None:
        self._client = httpx.Client(
            timeout=request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9,uk;q=0.8",
            },
        )
        self._min_delay = min_delay_seconds
        self._max_delay = max_delay_seconds

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "WorkUaScraper":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        wait=wait_exponential_jitter(initial=1, max=15),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response

    def _human_delay(self) -> None:
        delay = random.uniform(self._min_delay, self._max_delay)
        if delay > 0:
            import time

            time.sleep(delay)

    @staticmethod
    def _normalize_search_query(search_query: str) -> str:
        normalized = re.sub(r"\s+", " ", search_query or "").strip()
        if not 2 <= len(normalized) <= 100:
            raise ValueError("search_query must be between 2 and 100 characters")
        if not re.search(r"[\wА-Яа-яІіЇїЄєҐґ]", normalized, re.UNICODE):
            raise ValueError("search_query must contain letters or numbers")
        return normalized

    @classmethod
    def _ensure_workua_url(cls, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != cls.BASE_HOST:
            raise ValueError("WorkUaScraper only supports https://www.work.ua URLs")
        return url

    def build_search_url(self, search_query: str, page: int = 1) -> str:
        # Required search scope: exclude title-only matches via notitle=1.
        normalized_query = self._normalize_search_query(search_query)
        encoded_query = quote_plus(normalized_query)
        return self._ensure_workua_url(f"{self.BASE_URL}/jobs-{encoded_query}/")

    def fetch_job_links(self, search_query: str, page: int = 1) -> list[str]:
        response = self._get(
            self.build_search_url(search_query=search_query, page=page),
            params={"notitle": 1, "page": page},
        )
        soup = BeautifulSoup(response.text, "lxml")
        links: set[str] = set()

        for anchor in soup.select('a[href^="/jobs/"]'):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            if not re.match(r"^/jobs/\d+/?$", href):
                continue
            links.add(f"{self.BASE_URL}{href}")

        self._human_delay()
        return sorted(links)

    def scrape_pages(self, search_query: str, pages: int = 3) -> list[ScrapedJob]:
        normalized_query = self._normalize_search_query(search_query)
        results: list[ScrapedJob] = []
        seen_urls: set[str] = set()

        for page in range(1, pages + 1):
            job_urls = self.fetch_job_links(search_query=normalized_query, page=page)
            if not job_urls:
                continue

            for job_url in job_urls:
                if job_url in seen_urls:
                    continue
                seen_urls.add(job_url)

                job = self.scrape_job_detail(job_url)
                if job is not None:
                    results.append(job)

        return results

    def scrape_job_detail(self, url: str) -> ScrapedJob | None:
        self._ensure_workua_url(url)
        response = self._get(url)
        soup = BeautifulSoup(response.text, "lxml")

        source_job_id = self._extract_job_id(url)
        if not source_job_id:
            return None

        data = self._extract_jobposting_json_ld(soup)

        title = self._pick_title(soup, data)
        description_raw = self._pick_description(soup, data)
        company_name = self._pick_company(soup, data)
        city = self._pick_city(soup, data)
        employment_type = self._pick_employment_type(soup, data)
        published_at = self._pick_published_at(data)
        requirements_raw = self._extract_requirements_from_text(description_raw)

        self._human_delay()
        if not title or not description_raw or not company_name:
            return None

        return ScrapedJob(
            source_job_id=source_job_id,
            url=url,
            title=title,
            company_name=company_name,
            city=city,
            employment_type=employment_type,
            description_raw=description_raw,
            requirements_raw=requirements_raw,
            published_at=published_at,
        )

    @staticmethod
    def _extract_job_id(url: str) -> str | None:
        match = re.search(r"/jobs/(\d+)/?", url)
        return match.group(1) if match else None

    @staticmethod
    def _pick_title(soup: BeautifulSoup, data: dict[str, Any]) -> str:
        title = str(data.get("title") or "").strip()
        if title:
            return title
        header = soup.select_one("h1")
        return header.get_text(" ", strip=True) if header else ""

    @staticmethod
    def _pick_description(soup: BeautifulSoup, data: dict[str, Any]) -> str:
        description = str(data.get("description") or "").strip()
        if description:
            clean = BeautifulSoup(description, "lxml").get_text(" ", strip=True)
            return re.sub(r"\s+", " ", clean)

        main_description = soup.select_one("#job-description") or soup.select_one(".overflow.wordwrap")
        if main_description:
            text = main_description.get_text(" ", strip=True)
            return re.sub(r"\s+", " ", text)

        body_text = soup.get_text(" ", strip=True)
        return re.sub(r"\s+", " ", body_text)

    @staticmethod
    def _pick_company(soup: BeautifulSoup, data: dict[str, Any]) -> str:
        hiring = data.get("hiringOrganization")
        if isinstance(hiring, dict):
            company = str(hiring.get("name") or "").strip()
            if company:
                return company

        company_link = soup.select_one('a[href*="/company/"]')
        if company_link:
            company = company_link.get_text(" ", strip=True)
            if company:
                return company

        for by_company_link in soup.select('a[href*="/jobs/by-company/"]'):
            company = by_company_link.get_text(" ", strip=True)
            if company and "Більше про компанію" not in company:
                return company

        company_block = soup.select_one(".add-top-sm h2")
        if company_block:
            company = company_block.get_text(" ", strip=True)
            if company:
                return company

        meta_description = soup.find("meta", attrs={"name": "Description"})
        if meta_description:
            content = str(meta_description.get("content") or "")
            match = re.search(r"(?i)у\s+компанію\s+(.+?)\s+запрошується", content)
            if match:
                return match.group(1).strip(" «»\"")

        return ""

    @staticmethod
    def _pick_city(soup: BeautifulSoup, data: dict[str, Any]) -> str | None:
        location = data.get("jobLocation")
        if isinstance(location, dict):
            address = location.get("address")
            if isinstance(address, dict):
                locality = str(address.get("addressLocality") or "").strip()
                if locality:
                    return locality
        if isinstance(location, list):
            for item in location:
                if isinstance(item, dict):
                    address = item.get("address")
                    if isinstance(address, dict):
                        locality = str(address.get("addressLocality") or "").strip()
                        if locality:
                            return locality

        location_tag = soup.select_one('span[title*="Місце роботи"]')
        if location_tag:
            return location_tag.get_text(" ", strip=True)
        return None

    @staticmethod
    def _pick_employment_type(soup: BeautifulSoup, data: dict[str, Any]) -> str | None:
        employment_type = data.get("employmentType")
        if isinstance(employment_type, str) and employment_type.strip():
            return employment_type.strip()
        if isinstance(employment_type, list):
            values = [str(item).strip() for item in employment_type if str(item).strip()]
            if values:
                return ", ".join(values)

        possible = soup.select_one('span[title*="Вид зайнятості"]')
        if possible:
            return possible.get_text(" ", strip=True)
        return None

    @staticmethod
    def _pick_published_at(data: dict[str, Any]) -> datetime | None:
        date_value = str(data.get("datePosted") or "").strip()
        if not date_value:
            return None
        try:
            return datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _extract_requirements_from_text(text: str) -> str | None:
        segments = re.split(r"(?i)(requirements|вимоги|what we expect)", text)
        if len(segments) >= 3:
            candidate = segments[2].strip()
            return candidate[:2000] if candidate else None
        return None

    @staticmethod
    def _extract_jobposting_json_ld(soup: BeautifulSoup) -> dict[str, Any]:
        scripts = soup.select('script[type="application/ld+json"]')
        for script in scripts:
            raw = script.string or script.get_text(strip=True)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if not isinstance(item, dict):
                    continue
                value = str(item.get("@type") or "").lower()
                if "jobposting" in value:
                    return item
        return {}
