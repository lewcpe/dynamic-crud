"""add_represent_and_system_rels

Revision ID: 3ded1d30dcae
Revises: 6a40ade4fe70
Create Date: 2026-04-28 10:15:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = '3ded1d30dcae'
down_revision: Union[str, Sequence[str], None] = '6a40ade4fe70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE dynamic_tables ADD COLUMN represent TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE dynamic_relationships ADD COLUMN to_system_table TEXT DEFAULT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE dynamic_relationships DROP COLUMN to_system_table")
    op.execute("ALTER TABLE dynamic_tables DROP COLUMN represent")
