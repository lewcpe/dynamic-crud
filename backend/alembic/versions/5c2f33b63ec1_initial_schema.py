"""initial_schema

Revision ID: 5c2f33b63ec1
Revises:
Create Date: 2026-04-28 08:39:49.869791
"""
from typing import Sequence, Union

from alembic import op

revision: str = '5c2f33b63ec1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_name TEXT NOT NULL UNIQUE,
            field_type TEXT NOT NULL CHECK(field_type IN ('int','float','text','date','datetime')),
            field_label TEXT NOT NULL DEFAULT '',
            field_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL DEFAULT 'default',
            data TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dynamic_items")
    op.execute("DROP TABLE IF EXISTS dynamic_fields")
