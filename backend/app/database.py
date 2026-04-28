import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data.db"
FIELD_TYPES = ["int", "float", "text", "date", "datetime", "file", "files"]
REL_TYPES = ["1-1", "1-n", "n-n"]
RESERVED_FIELD_NAMES = ("id", "owner", "created_at", "updated_at", "data")
SYSTEM_TABLES = {"users", "groups"}


def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_items_table(table_id: int) -> str:
    return f"items_{table_id}"


def run_migrations():
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config()
    alembic_cfg.set_main_option(
        "script_location", str(Path(__file__).parent.parent / "alembic")
    )
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")
    command.upgrade(alembic_cfg, "head")


def get_fields(conn: sqlite3.Connection, table_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM dynamic_fields WHERE table_id = ? ORDER BY field_order, id",
        (table_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_relationships(conn: sqlite3.Connection, table_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE from_table_id = ? OR to_table_id = ?",
        (table_id, table_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_relationships_from(conn: sqlite3.Connection, table_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE from_table_id = ?",
        (table_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def validate_item_data(fields: list[dict], data: dict) -> dict:
    from fastapi import HTTPException

    validated = {}
    for f in fields:
        name = f["field_name"]
        ftype = f["field_type"]
        raw = data.get(name)
        if raw is None or raw == "":
            validated[name] = None
            continue
        if ftype == "int":
            try:
                validated[name] = int(raw)
            except (ValueError, TypeError):
                raise HTTPException(400, f"Field '{name}' must be an integer")
        elif ftype == "float":
            try:
                validated[name] = float(raw)
            except (ValueError, TypeError):
                raise HTTPException(400, f"Field '{name}' must be a float")
        elif ftype in ("text", "date", "datetime"):
            validated[name] = str(raw)
        else:
            validated[name] = str(raw)
    return validated


def alter_table_for_new_field(
    conn: sqlite3.Connection, table_id: int, field_name: str, field_type: str
):
    table = get_items_table(table_id)
    sqlite_type = "TEXT"
    if field_type == "int":
        sqlite_type = "INTEGER"
    elif field_type == "float":
        sqlite_type = "REAL"
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {field_name} {sqlite_type}")
    except sqlite3.OperationalError:
        pass


def drop_column_from_table(
    conn: sqlite3.Connection, table_id: int, field_name: str
):
    table = get_items_table(table_id)
    try:
        conn.execute(f"ALTER TABLE {table} DROP COLUMN {field_name}")
    except sqlite3.OperationalError:
        cols = [
            r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        ]
        if field_name not in cols:
            return
        cols.remove(field_name)
        quoted = ", ".join(cols)
        conn.execute(
            f"CREATE TABLE {table}_new AS SELECT {quoted} FROM {table}"
        )
        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")


def ensure_table_exists(conn, table_id: int):
    from fastapi import HTTPException

    row = conn.execute(
        "SELECT id FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Table not found")
    return row
