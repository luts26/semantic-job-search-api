from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ScrapedJob:
    source_job_id: str
    url: str
    title: str
    company_name: str
    city: str | None
    employment_type: str | None
    description_raw: str
    requirements_raw: str | None
    published_at: datetime | None
