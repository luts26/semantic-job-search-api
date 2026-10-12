from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, EmbeddingJobQueue, EmbeddingQueueStatus, Job
from app.models.job import JobRoleCategory
from app.scraper.classifier import classify_role
from app.scraper.schemas import ScrapedJob


@dataclass(slots=True)
class IngestionStats:
    total_scraped: int = 0
    jobs_created: int = 0
    jobs_updated: int = 0
    companies_created: int = 0


class JobIngestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_many(self, scraped_jobs: list[ScrapedJob]) -> IngestionStats:
        stats = IngestionStats(total_scraped=len(scraped_jobs))
        now = datetime.now(timezone.utc)

        for item in scraped_jobs:
            company, company_created = self._get_or_create_company(item.company_name)
            if company_created:
                stats.companies_created += 1

            created = self._upsert_job(item, company.id, now)
            if created:
                stats.jobs_created += 1
            else:
                stats.jobs_updated += 1

        self.db.commit()
        return stats

    def _get_or_create_company(self, company_name: str) -> tuple[Company, bool]:
        stmt = select(Company).where(Company.name == company_name)
        company = self.db.execute(stmt).scalar_one_or_none()
        if company is not None:
            return company, False

        company = Company(name=company_name)
        self.db.add(company)
        self.db.flush()
        return company, True

    def _upsert_job(self, item: ScrapedJob, company_id: int, seen_at: datetime) -> bool:
        stmt = select(Job).where(Job.source == "work.ua", Job.source_job_id == item.source_job_id)
        job = self.db.execute(stmt).scalar_one_or_none()

        role = classify_role(item.title, item.description_raw)

        if job is None:
            job = Job(
                source="work.ua",
                source_job_id=item.source_job_id,
                url=item.url,
                title=item.title,
                company_id=company_id,
                city=item.city,
                employment_type=item.employment_type,
                description_raw=item.description_raw,
                requirements_raw=item.requirements_raw,
                role_category=role,
                published_at=item.published_at,
                is_active=True,
                last_seen_at=seen_at,
            )
            self.db.add(job)
            self.db.flush()
            self._enqueue_for_embedding(job.id)
            return True

        job.url = item.url
        job.title = item.title
        job.company_id = company_id
        job.city = item.city
        job.employment_type = item.employment_type
        job.description_raw = item.description_raw
        job.requirements_raw = item.requirements_raw
        job.role_category = role if isinstance(role, JobRoleCategory) else JobRoleCategory.OTHER
        job.published_at = item.published_at
        job.is_active = True
        job.last_seen_at = seen_at
        self._enqueue_for_embedding(job.id)
        return False

    def _enqueue_for_embedding(self, job_id: int) -> None:
        stmt = select(EmbeddingJobQueue).where(EmbeddingJobQueue.job_id == job_id)
        queue_item = self.db.execute(stmt).scalar_one_or_none()
        if queue_item is None:
            queue_item = EmbeddingJobQueue(job_id=job_id, status=EmbeddingQueueStatus.PENDING, attempts=0)
            self.db.add(queue_item)
            return

        queue_item.status = EmbeddingQueueStatus.PENDING
        queue_item.last_error = None
