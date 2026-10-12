from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings


class QdrantIndex:
    def __init__(self) -> None:
        settings = get_settings()
        self.collection_name = settings.qdrant_collection_name
        self.client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    def ensure_collection(self, vector_size: int) -> None:
        if self.collection_exists():
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
        )

    def collection_exists(self) -> bool:
        try:
            exists = self.client.collection_exists(self.collection_name)
        except AttributeError:
            try:
                self.client.get_collection(self.collection_name)
                exists = True
            except Exception:
                exists = False
        return exists

    def upsert_points(self, points: list[qmodels.PointStruct]) -> None:
        if not points:
            return
        self.client.upsert(collection_name=self.collection_name, points=points)

    def search(
        self,
        vector: list[float],
        limit: int,
        query_filter: qmodels.Filter | None = None,
    ) -> list[qmodels.ScoredPoint]:
        try:
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        except AttributeError:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            return list(response.points)
