from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.index_service import IndexService
from app.services.scrape_service import ScrapeService

router = APIRouter(prefix="/admin", tags=["admin"])


class ScrapeRunRequest(BaseModel):
    search_query: str = Field(min_length=2, max_length=100)
    max_pages: int = Field(default=3, ge=1, le=30)

    @field_validator("search_query")
    @classmethod
    def validate_search_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not 2 <= len(normalized) <= 100:
            raise ValueError("search_query must be between 2 and 100 characters")
        if not any(char.isalnum() for char in normalized):
            raise ValueError("search_query must contain letters or numbers")
        return normalized


class ScrapeRunResponse(BaseModel):
    total_scraped: int
    jobs_created: int
    jobs_updated: int
    companies_created: int


class IndexRunRequest(BaseModel):
    batch_size: int = Field(default=50, ge=1, le=500)


class IndexRunResponse(BaseModel):
    total_candidates: int
    processed: int
    indexed: int
    failed: int


@router.post("/scrape/run", response_model=ScrapeRunResponse)
def run_scrape(payload: ScrapeRunRequest, db: Session = Depends(get_db)) -> ScrapeRunResponse:
    try:
        service = ScrapeService(db)
        result = service.run_workua_scrape(
            search_query=payload.search_query,
            max_pages=payload.max_pages,
        )
        return ScrapeRunResponse(**result)
    except Exception as exc:  # pragma: no cover - boundary-level protection
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Scraper failed: {exc}",
        ) from exc


@router.post("/index/run", response_model=IndexRunResponse)
def run_index(payload: IndexRunRequest, db: Session = Depends(get_db)) -> IndexRunResponse:
    try:
        service = IndexService(db)
        result = service.run(batch_size=payload.batch_size)
        return IndexRunResponse(**result)
    except Exception as exc:  # pragma: no cover - boundary-level protection
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Indexing failed: {exc}",
        ) from exc
