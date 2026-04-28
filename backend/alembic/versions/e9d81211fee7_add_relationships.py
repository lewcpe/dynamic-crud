"""add_relationships

Revision ID: e9d81211fee7
Revises: b4323b89179f
Create Date: 2026-04-28 09:01:52.444703
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e9d81211fee7'
down_revision: Union[str, Sequence[str], None] = 'b4323b89179f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_table_id INTEGER NOT NULL
                REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            to_table_id INTEGER NOT NULL
                REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            rel_name TEXT NOT NULL,
            rel_label TEXT NOT NULL DEFAULT '',
            rel_type TEXT NOT NULL
                CHECK(rel_type IN ('1-1', '1-n', 'n-n')),
            from_label TEXT NOT NULL DEFAULT '',
            to_label TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(from_table_id, rel_name)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dynamic_relationships")
