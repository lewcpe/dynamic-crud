"""update_field_type_check

Revision ID: 26e56fd2ccce
Revises: 7e59eded5a35
Create Date: 2026-04-28 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '26e56fd2ccce'
down_revision: Union[str, Sequence[str], None] = '7e59eded5a35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    count = conn.execute(sa.text("SELECT COUNT(*) FROM dynamic_fields")).scalar()

    op.execute("""
        CREATE TABLE dynamic_fields_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            field_name TEXT NOT NULL,
            field_type TEXT NOT NULL CHECK(field_type IN ('int','float','text','date','datetime','file','files','multiline','image')),
            field_label TEXT NOT NULL DEFAULT '',
            field_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(table_id, field_name)
        )
    """)

    if count > 0:
        op.execute("""
            INSERT INTO dynamic_fields_new
            (id, table_id, field_name, field_type, field_label, field_order, created_at)
            SELECT id, table_id, field_name, field_type, field_label, field_order, created_at
            FROM dynamic_fields
        """)

    op.execute("DROP TABLE dynamic_fields")
    op.execute("ALTER TABLE dynamic_fields_new RENAME TO dynamic_fields")


def downgrade() -> None:
    conn = op.get_bind()
    count = conn.execute(sa.text("SELECT COUNT(*) FROM dynamic_fields")).scalar()

    op.execute("""
        CREATE TABLE dynamic_fields_old (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            field_name TEXT NOT NULL,
            field_type TEXT NOT NULL CHECK(field_type IN ('int','float','text','date','datetime','file','files')),
            field_label TEXT NOT NULL DEFAULT '',
            field_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(table_id, field_name)
        )
    """)

    if count > 0:
        op.execute("""
            INSERT INTO dynamic_fields_old
            (id, table_id, field_name, field_type, field_label, field_order, created_at)
            SELECT id, table_id, field_name, field_type, field_label, field_order, created_at
            FROM dynamic_fields
            WHERE field_type IN ('int','float','text','date','datetime','file','files')
        """)

    op.execute("DROP TABLE dynamic_fields")
    op.execute("ALTER TABLE dynamic_fields_old RENAME TO dynamic_fields")
