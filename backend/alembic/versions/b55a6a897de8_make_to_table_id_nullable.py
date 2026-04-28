"""make_to_table_id_nullable

Revision ID: b55a6a897de8
Revises: 3ded1d30dcae
Create Date: 2026-04-28 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b55a6a897de8'
down_revision: Union[str, Sequence[str], None] = '3ded1d30dcae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if there are any existing relationships
    count = conn.execute(sa.text("SELECT COUNT(*) FROM dynamic_relationships")).scalar()

    # Recreate the table with to_table_id nullable
    op.execute("""
        CREATE TABLE dynamic_relationships_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_table_id INTEGER NOT NULL REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            to_table_id INTEGER REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            to_system_table TEXT DEFAULT NULL,
            rel_name TEXT NOT NULL,
            rel_label TEXT NOT NULL DEFAULT '',
            rel_type TEXT NOT NULL CHECK(rel_type IN ('1-1', '1-n', 'n-n')),
            from_label TEXT NOT NULL DEFAULT '',
            to_label TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(from_table_id, rel_name)
        )
    """)

    if count > 0:
        op.execute("""
            INSERT INTO dynamic_relationships_new
            (id, from_table_id, to_table_id, to_system_table, rel_name, rel_label, rel_type, from_label, to_label, created_at)
            SELECT id, from_table_id, to_table_id, to_system_table, rel_name, rel_label, rel_type, from_label, to_label, created_at
            FROM dynamic_relationships
        """)

    op.execute("DROP TABLE dynamic_relationships")
    op.execute("ALTER TABLE dynamic_relationships_new RENAME TO dynamic_relationships")


def downgrade() -> None:
    conn = op.get_bind()
    count = conn.execute(sa.text("SELECT COUNT(*) FROM dynamic_relationships")).scalar()

    op.execute("""
        CREATE TABLE dynamic_relationships_old (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_table_id INTEGER NOT NULL REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            to_table_id INTEGER NOT NULL REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            to_system_table TEXT DEFAULT NULL,
            rel_name TEXT NOT NULL,
            rel_label TEXT NOT NULL DEFAULT '',
            rel_type TEXT NOT NULL CHECK(rel_type IN ('1-1', '1-n', 'n-n')),
            from_label TEXT NOT NULL DEFAULT '',
            to_label TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(from_table_id, rel_name)
        )
    """)

    if count > 0:
        op.execute("""
            INSERT INTO dynamic_relationships_old
            (id, from_table_id, to_table_id, to_system_table, rel_name, rel_label, rel_type, from_label, to_label, created_at)
            SELECT id, from_table_id, to_table_id, to_system_table, rel_name, rel_label, rel_type, from_label, to_label, created_at
            FROM dynamic_relationships
            WHERE to_table_id IS NOT NULL
        """)

    op.execute("DROP TABLE dynamic_relationships")
    op.execute("ALTER TABLE dynamic_relationships_old RENAME TO dynamic_relationships")
