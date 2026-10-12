from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from qdrant_client.http import models as qmodels
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Company, EmbeddingJobQueue, EmbeddingQueueStatus, Job
from app.vector.embedding_provider import build_embedding_provider
from app.vector.qdrant_index import QdrantIndex


@dataclass(slots=True)
class IndexingStats:
    total_candidates: int = 0
    processed: int = 0
    indexed: int = 0
    failed: int = 0


class IndexService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.provider = build_embedding_provider()
        self.qdrant = QdrantIndex()

    def run(self, batch_size: int = 50) -> dict[str, int]:
        stats = IndexingStats()
        queue_rows = self._select_queue_rows(batch_size=batch_size)
        stats.total_candidates = len(queue_rows)

        if not queue_rows:
            return asdict(stats)

        jobs_for_index: list[tuple[EmbeddingJobQueue, Job, str]] = []
        for queue_item, job, company_name in queue_rows:
            try:
                queue_item.status = EmbeddingQueueStatus.PROCESSING
                queue_item.attempts += 1
                queue_item.updated_at = datetime.now(timezone.utc)
                jobs_for_index.append((queue_item, job, company_name))
            except Exception:
                queue_item.status = EmbeddingQueueStatus.FAILED
                queue_item.last_error = "Failed to prepare queue item"
                stats.failed += 1

        self.db.commit()

        if not jobs_for_index:
            return asdict(stats)

        try:
            texts = [self._build_embedding_text(job, company_name) for _, job, company_name in jobs_for_index]
            embeddings = self.provider.embed_texts(texts)
            if len(embeddings) != len(jobs_for_index):
                raise RuntimeError("Embedding provider returned invalid number of vectors")

            vector_size = len(embeddings[0]) if embeddings else self.settings.embedding_vector_size
            self.qdrant.ensure_collection(vector_size=vector_size)

            points: list[qmodels.PointStruct] = []
            for (queue_item, job, company_name), vector in zip(jobs_for_index, embeddings):
                payload = {
                    "job_id": job.id,
                    "title": job.title,
                    "company": company_name,
                    "company_normalized": company_name.lower(),
                    "city": job.city,
                    "city_normalized": (job.city or "").lower(),
                    "employment_type": job.employment_type,
                    "role_category": job.role_category.value,
                    "url": job.url,
                    "source": job.source,
                }
                points.append(qmodels.PointStruct(id=job.id, vector=vector, payload=payload))
                stats.processed += 1

            self.qdrant.upsert_points(points)
            for queue_item, _, _ in jobs_for_index:
                queue_item.status = EmbeddingQueueStatus.DONE
                queue_item.last_error = None
                queue_item.updated_at = datetime.now(timezone.utc)
                stats.indexed += 1
        except Exception as exc:
            error_message = str(exc)[:500]
            for queue_item, _, _ in jobs_for_index:
                queue_item.status = EmbeddingQueueStatus.FAILED
                queue_item.last_error = error_message
                queue_item.updated_at = datetime.now(timezone.utc)
                stats.failed += 1

        self.db.commit()
        return asdict(stats)

    def _select_queue_rows(self, batch_size: int) -> list[tuple[EmbeddingJobQueue, Job, str]]:
        stmt = (
            select(EmbeddingJobQueue, Job, Company.name)
            .join(Job, EmbeddingJobQueue.job_id == Job.id)
            .join(Company, Job.company_id == Company.id)
            .where(
                Job.is_active.is_(True),
                or_(
                    EmbeddingJobQueue.status == EmbeddingQueueStatus.PENDING,
                    EmbeddingJobQueue.status == EmbeddingQueueStatus.FAILED,
                ),
                EmbeddingJobQueue.attempts < self.settings.embedding_max_attempts,
            )
            .order_by(EmbeddingJobQueue.updated_at.asc())
            .limit(batch_size)
        )
        return list(self.db.execute(stmt).all())

    @staticmethod
    def _build_embedding_text(job: Job, company_name: str) -> str:
        pieces = [
            f"title: {job.title}",
            f"company: {company_name}",
            f"city: {job.city or ''}",
            f"employment_type: {job.employment_type or ''}",
            f"role_category: {job.role_category.value}",
            f"requirements: {job.requirements_raw or ''}",
            f"description: {job.description_raw}",
        ]
        return "\n".join(pieces)
