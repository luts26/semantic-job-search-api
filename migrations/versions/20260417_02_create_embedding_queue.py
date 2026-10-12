"""create embedding queue table

Revision ID: 20260417_02
Revises: 20260417_01
Create Date: 2026-04-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_02"
down_revision: Union[str, Sequence[str], None] = "20260417_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status_enum = sa.Enum("pending", "processing", "done", "failed", name="embedding_queue_status")

    op.create_table(
        "embedding_jobs_queue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_embedding_jobs_queue_job_id", "embedding_jobs_queue", ["job_id"], unique=True)
    op.create_index("ix_embedding_jobs_queue_status", "embedding_jobs_queue", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_embedding_jobs_queue_status", table_name="embedding_jobs_queue")
    op.drop_index("ix_embedding_jobs_queue_job_id", table_name="embedding_jobs_queue")
    op.drop_table("embedding_jobs_queue")

    status_enum = sa.Enum(name="embedding_queue_status")
    status_enum.drop(op.get_bind(), checkfirst=True)
