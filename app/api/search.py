from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.search_service import SearchService

router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    city: str | None = Field(default=None, max_length=128)
    company: str | None = Field(default=None, max_length=255)
    role_category: str | None = Field(default=None, max_length=64)
    limit: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    job_id: int
    score: float
    title: str
    company: str
    city: str | None
    employment_type: str | None
    role_category: str
    url: str
    published_at: str | None


class SearchResponse(BaseModel):
    query: str
    applied_filters: dict
    results: list[SearchResult]


@router.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    try:
        service = SearchService(db)
        result = service.search(
            query=payload.query,
            limit=payload.limit,
            city=payload.city,
            company=payload.company,
            role_category=payload.role_category,
        )
        return SearchResponse(**result)
    except Exception as exc:  # pragma: no cover - boundary-level protection
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Search failed: {exc}",
        ) from exc
