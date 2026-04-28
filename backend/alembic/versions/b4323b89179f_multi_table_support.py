"""multi_table_support

Revision ID: b4323b89179f
Revises: 5c2f33b63ec1
Create Date: 2026-04-28 08:40:01.234567
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b4323b89179f'
down_revision: Union[str, Sequence[str], None] = '5c2f33b63ec1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    op.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    op.execute("""
        INSERT OR IGNORE INTO dynamic_tables (name, label)
        VALUES ('default', 'Default')
    """)

    row = conn.execute(
        sa.text("SELECT id FROM dynamic_tables WHERE name = 'default'")
    ).fetchone()
    default_table_id = row[0]

    op.execute(sa.text(f"""
        CREATE TABLE dynamic_fields_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL DEFAULT {default_table_id}
                REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            field_name TEXT NOT NULL,
            field_type TEXT NOT NULL
                CHECK(field_type IN ('int','float','text','date','datetime')),
            field_label TEXT NOT NULL DEFAULT '',
            field_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(table_id, field_name)
        )
    """))
    op.execute(sa.text(f"""
        INSERT INTO dynamic_fields_new
            (id, table_id, field_name, field_type, field_label, field_order, created_at)
        SELECT id, {default_table_id}, field_name, field_type, field_label, field_order, created_at
        FROM dynamic_fields
    """))
    op.execute("DROP TABLE dynamic_fields")
    op.execute("ALTER TABLE dynamic_fields_new RENAME TO dynamic_fields")

    op.execute(sa.text(f"ALTER TABLE dynamic_items RENAME TO items_{default_table_id}"))


def downgrade() -> None:
    conn = op.get_bind()

    row = conn.execute(
        sa.text("SELECT id FROM dynamic_tables WHERE name = 'default'")
    ).fetchone()
    default_table_id = row[0] if row else 1

    try:
        op.execute(sa.text(f"ALTER TABLE items_{default_table_id} RENAME TO dynamic_items"))
    except Exception:
        pass

    op.execute("""
        CREATE TABLE dynamic_fields_single (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_name TEXT NOT NULL UNIQUE,
            field_type TEXT NOT NULL
                CHECK(field_type IN ('int','float','text','date','datetime')),
            field_label TEXT NOT NULL DEFAULT '',
            field_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    op.execute("""
        INSERT INTO dynamic_fields_single
            (id, field_name, field_type, field_label, field_order, created_at)
        SELECT id, field_name, field_type, field_label, field_order, created_at
        FROM dynamic_fields
    """)
    op.execute("DROP TABLE dynamic_fields")
    op.execute("ALTER TABLE dynamic_fields_single RENAME TO dynamic_fields")

    op.execute("DROP TABLE IF EXISTS dynamic_tables")
