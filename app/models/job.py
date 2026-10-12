from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobRoleCategory(str, Enum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    FULLSTACK = "fullstack"
    MOBILE = "mobile"
    DEVOPS = "devops"
    QA = "qa"
    DATA = "data"
    MACHINE_LEARNING = "machine_learning"
    GAME_DEVELOPMENT = "game_development"
    DESIGN = "design"
    MANAGEMENT = "management"
    OTHER = "other"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "source_job_id", name="uq_jobs_source_source_job_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="work.ua")
    source_job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    employment_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    requirements_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_category: Mapped[JobRoleCategory] = mapped_column(
        SqlEnum(
            JobRoleCategory,
            name="job_role_category",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=JobRoleCategory.OTHER,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    company = relationship("Company", back_populates="jobs")
