"""create companies and jobs tables

Revision ID: 20260417_01
Revises:
Create Date: 2026-04-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    role_enum = sa.Enum(
        "cpp_developer",
        "technical_artist",
        "animator",
        "level_designer",
        "game_designer",
        "other",
        name="job_role_category",
    )

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_companies_name", "companies", ["name"], unique=True)

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_job_id", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        sa.Column("description_raw", sa.Text(), nullable=False),
        sa.Column("requirements_raw", sa.Text(), nullable=True),
        sa.Column("role_category", role_enum, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("source", "source_job_id", name="uq_jobs_source_source_job_id"),
        sa.UniqueConstraint("url", name="uq_jobs_url"),
    )
    op.create_index("ix_jobs_title", "jobs", ["title"], unique=False)
    op.create_index("ix_jobs_city", "jobs", ["city"], unique=False)
    op.create_index("ix_jobs_employment_type", "jobs", ["employment_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_employment_type", table_name="jobs")
    op.drop_index("ix_jobs_city", table_name="jobs")
    op.drop_index("ix_jobs_title", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_table("companies")

    role_enum = sa.Enum(name="job_role_category")
    role_enum.drop(op.get_bind(), checkfirst=True)
