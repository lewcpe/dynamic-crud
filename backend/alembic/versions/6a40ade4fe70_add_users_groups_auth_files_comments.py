"""add_users_groups_auth_files_comments

Revision ID: 6a40ade4fe70
Revises: e9d81211fee7
Create Date: 2026-04-28 09:19:50.511121
"""
from typing import Sequence, Union

from alembic import op

revision: str = '6a40ade4fe70'
down_revision: Union[str, Sequence[str], None] = 'e9d81211fee7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_groups (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, group_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            target_type TEXT NOT NULL CHECK(target_type IN ('user', 'group', 'role')),
            target_id INTEGER,
            target_role TEXT,
            list_rule TEXT,
            view_rule TEXT,
            create_rule TEXT,
            update_rule TEXT,
            delete_rule TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            item_id INTEGER NOT NULL,
            field_name TEXT NOT NULL DEFAULT '',
            filename TEXT NOT NULL,
            mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
            size INTEGER NOT NULL DEFAULT 0,
            data BLOB NOT NULL,
            uploader_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL REFERENCES dynamic_tables(id) ON DELETE CASCADE,
            item_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS comments")
    op.execute("DROP TABLE IF EXISTS files")
    op.execute("DROP TABLE IF EXISTS permissions")
    op.execute("DROP TABLE IF EXISTS user_groups")
    op.execute("DROP TABLE IF EXISTS groups")
    op.execute("DROP TABLE IF EXISTS users")
