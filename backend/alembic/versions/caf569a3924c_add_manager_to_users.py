"""add_manager_to_users

Revision ID: caf569a3924c
Revises: b55a6a897de8
Create Date: 2026-04-28 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'caf569a3924c'
down_revision: Union[str, Sequence[str], None] = 'b55a6a897de8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN manager_id INTEGER REFERENCES users(id) ON DELETE SET NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN manager_id")
