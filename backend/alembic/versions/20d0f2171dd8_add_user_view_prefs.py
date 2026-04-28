"""add_user_view_prefs

Revision ID: 20d0f2171dd8
Revises: caf569a3924c
Create Date: 2026-04-28 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20d0f2171dd8'
down_revision: Union[str, Sequence[str], None] = 'caf569a3924c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_view_prefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            table_id INTEGER NOT NULL REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            hidden_columns TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, table_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_view_prefs")
