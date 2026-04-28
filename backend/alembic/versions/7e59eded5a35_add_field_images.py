"""add_field_images

Revision ID: 7e59eded5a35
Revises: 20d0f2171dd8
Create Date: 2026-04-28 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = '7e59eded5a35'
down_revision: Union[str, Sequence[str], None] = '20d0f2171dd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS field_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            item_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            filename TEXT NOT NULL,
            mime_type TEXT NOT NULL DEFAULT 'image/jpeg',
            thumbnail BLOB NOT NULL,
            file_path TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_field_images_lookup ON field_images (table_id, item_id, field_name)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS field_images")
