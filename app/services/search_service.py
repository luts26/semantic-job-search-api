import re
from dataclasses import dataclass
from datetime import datetime

from qdrant_client.http import models as qmodels
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Company, Job, JobRoleCategory
from app.scraper.classifier import classify_role
from app.vector.embedding_provider import build_embedding_provider
from app.vector.qdrant_index import QdrantIndex


KNOWN_CITIES = {
    "kyiv",
    "kiev",
    "lviv",
    "odesa",
    "odessa",
    "kharkiv",
    "dnipro",
    "zaporizhzhia",
    "mykolaiv",
    "vinnytsia",
    "ivano-frankivsk",
    "ternopil",
    "remote",
}


@dataclass(slots=True)
class SearchFilters:
    city: str | None
    company: str | None
    role_category: JobRoleCategory | None


class SearchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.provider = build_embedding_provider()
        self.qdrant = QdrantIndex()

    def search(
        self,
        query: str,
        limit: int = 10,
        city: str | None = None,
        company: str | None = None,
        role_category: str | None = None,
    ) -> dict:
        filters = self._resolve_filters(
            query=query,
            explicit_city=city,
            explicit_company=company,
            explicit_role=role_category,
        )

        if not self.qdrant.collection_exists():
            return {
                "query": query,
                "applied_filters": self._filters_to_dict(filters),
                "results": [],
            }

        embedding = self.provider.embed_texts([query])[0]
        query_filter = self._build_qdrant_filter(filters)
        points = self.qdrant.search(vector=embedding, limit=limit, query_filter=query_filter)
        if not points:
            return {
                "query": query,
                "applied_filters": self._filters_to_dict(filters),
                "results": [],
            }

        scores_by_id = {int(point.id): float(point.score) for point in points}
        ranked_ids = [int(point.id) for point in points]

        stmt = (
            select(Job, Company.name)
            .join(Company, Job.company_id == Company.id)
            .where(Job.id.in_(ranked_ids), Job.is_active.is_(True))
        )
        rows = list(self.db.execute(stmt).all())
        row_map = {job.id: (job, company_name) for job, company_name in rows}

        results: list[dict] = []
        for job_id in ranked_ids:
            row = row_map.get(job_id)
            if row is None:
                continue
            job, company_name = row
            results.append(
                {
                    "job_id": job.id,
                    "score": round(scores_by_id.get(job.id, 0.0), 6),
                    "title": job.title,
                    "company": company_name,
                    "city": job.city,
                    "employment_type": job.employment_type,
                    "role_category": job.role_category.value,
                    "url": job.url,
                    "published_at": self._to_iso(job.published_at),
                }
            )

        return {
            "query": query,
            "applied_filters": self._filters_to_dict(filters),
            "results": results,
        }

    def _resolve_filters(
        self,
        query: str,
        explicit_city: str | None,
        explicit_company: str | None,
        explicit_role: str | None,
    ) -> SearchFilters:
        inferred_city = self._extract_city(query)
        inferred_company = self._extract_company(query, inferred_city)
        inferred_role = classify_role(query, query)
        if inferred_role == JobRoleCategory.OTHER:
            inferred_role = None

        final_role = self._normalize_role(explicit_role) if explicit_role else inferred_role

        return SearchFilters(
            city=explicit_city or inferred_city,
            company=explicit_company or inferred_company,
            role_category=final_role,
        )

    @staticmethod
    def _normalize_role(role: str | None) -> JobRoleCategory | None:
        if not role:
            return None
        role = role.strip().lower()
        try:
            return JobRoleCategory(role)
        except ValueError:
            return None

    @staticmethod
    def _extract_city(query: str) -> str | None:
        lowered = query.lower()
        for city in KNOWN_CITIES:
            if re.search(rf"\b{re.escape(city)}\b", lowered):
                return city

        match = re.search(r"\bin\s+([A-Z][A-Za-z-]{1,40})\b", query)
        if match:
            candidate = match.group(1).strip()
            if candidate.lower() not in {"developer", "developers", "engineer", "engineers"}:
                return candidate
        return None

    @staticmethod
    def _extract_company(query: str, inferred_city: str | None) -> str | None:
        patterns = [
            r"\b(?:at|for|with)\s+([A-Z0-9][A-Za-z0-9&.' -]{1,60})",
            r"\bwork\s+in\s+([A-Z0-9][A-Za-z0-9&.' -]{1,60})",
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if not match:
                continue
            candidate = re.sub(r"\s+", " ", match.group(1)).strip(" ,.;")
            candidate = re.sub(r"\s+in\s+[A-Z][A-Za-z-]{1,40}$", "", candidate).strip(" ,.;")
            candidate = re.sub(r"\s+from\s+[A-Z][A-Za-z-]{1,40}$", "", candidate).strip(" ,.;")
            if inferred_city and candidate.lower() == inferred_city.lower():
                continue
            if candidate.lower() in KNOWN_CITIES:
                continue
            return candidate

        return None

    @staticmethod
    def _build_qdrant_filter(filters: SearchFilters) -> qmodels.Filter | None:
        conditions: list[qmodels.FieldCondition] = []

        if filters.city:
            conditions.append(
                qmodels.FieldCondition(
                    key="city_normalized",
                    match=qmodels.MatchValue(value=filters.city.lower()),
                )
            )

        if filters.company:
            conditions.append(
                qmodels.FieldCondition(
                    key="company_normalized",
                    match=qmodels.MatchValue(value=filters.company.lower()),
                )
            )

        if filters.role_category:
            conditions.append(
                qmodels.FieldCondition(
                    key="role_category",
                    match=qmodels.MatchValue(value=filters.role_category.value),
                )
            )

        if not conditions:
            return None
        return qmodels.Filter(must=conditions)

    @staticmethod
    def _filters_to_dict(filters: SearchFilters) -> dict:
        return {
            "city": filters.city,
            "company": filters.company,
            "role_category": filters.role_category.value if filters.role_category else None,
        }

    @staticmethod
    def _to_iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None
