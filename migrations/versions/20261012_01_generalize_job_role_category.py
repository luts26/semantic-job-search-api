"""generalize job role category enum

Revision ID: 20261012_01
Revises: 20260417_02
Create Date: 2026-10-12

"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261012_01"
down_revision: Union[str, Sequence[str], None] = "20260417_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_VALUES = (
    "backend",
    "frontend",
    "fullstack",
    "mobile",
    "devops",
    "qa",
    "data",
    "machine_learning",
    "game_development",
    "design",
    "management",
    "other",
)

OLD_VALUES = (
    "cpp_developer",
    "technical_artist",
    "animator",
    "level_designer",
    "game_designer",
    "other",
)


def upgrade() -> None:
    values = ", ".join(f"'{value}'" for value in NEW_VALUES)
    op.execute(f"CREATE TYPE job_role_category_new AS ENUM ({values})")
    op.execute(
        """
        ALTER TABLE jobs
        ALTER COLUMN role_category TYPE job_role_category_new
        USING (
            CASE role_category::text
                WHEN 'cpp_developer' THEN 'backend'
                WHEN 'technical_artist' THEN 'game_development'
                WHEN 'animator' THEN 'design'
                WHEN 'level_designer' THEN 'game_development'
                WHEN 'game_designer' THEN 'game_development'
                ELSE 'other'
            END
        )::job_role_category_new
        """
    )
    op.execute("DROP TYPE job_role_category")
    op.execute("ALTER TYPE job_role_category_new RENAME TO job_role_category")


def downgrade() -> None:
    values = ", ".join(f"'{value}'" for value in OLD_VALUES)
    op.execute(f"CREATE TYPE job_role_category_old AS ENUM ({values})")
    op.execute(
        """
        ALTER TABLE jobs
        ALTER COLUMN role_category TYPE job_role_category_old
        USING (
            CASE role_category::text
                WHEN 'backend' THEN 'cpp_developer'
                WHEN 'game_development' THEN 'game_designer'
                WHEN 'design' THEN 'game_designer'
                ELSE 'other'
            END
        )::job_role_category_old
        """
    )
    op.execute("DROP TYPE job_role_category")
    op.execute("ALTER TYPE job_role_category_old RENAME TO job_role_category")
