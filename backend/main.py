import sqlite3
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, model_validator

DB_PATH = Path(__file__).parent / "data.db"
STATIC_DIR = Path(__file__).parent / "static"
FIELD_TYPES = ["int", "float", "text", "date", "datetime"]
REL_TYPES = ["1-1", "1-n", "n-n"]
RESERVED_FIELD_NAMES = ("id", "owner", "created_at", "updated_at", "data")


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_items_table(table_id: int) -> str:
    return f"items_{table_id}"


def run_migrations():
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config()
    alembic_cfg.set_main_option(
        "script_location", str(Path(__file__).parent / "alembic")
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


def item_row_to_dict(row: sqlite3.Row, fields: list[dict]) -> dict:
    item = dict(row)
    item.pop("data", None)
    json_data = {}
    try:
        json_data = json.loads(row["data"] or "{}")
    except json.JSONDecodeError:
        pass
    for f in fields:
        name = f["field_name"]
        if name not in json_data:
            json_data[name] = row[name] if name in row.keys() else None
    item["fields"] = json_data
    return item


def get_item_label(conn: sqlite3.Connection, table_id: int, item_id: int) -> str:
    table = get_items_table(table_id)
    row = conn.execute(f"SELECT owner FROM {table} WHERE id = ?", (item_id,)).fetchone()
    if row:
        return row["owner"] or str(item_id)
    return str(item_id)


def enrich_item_with_relationships(
    conn: sqlite3.Connection, table_id: int, item: dict
) -> dict:
    rels = get_relationships(conn, table_id)
    relationships = {}
    for rel in rels:
        rel_id = rel["id"]
        rel_name = rel["rel_name"]
        rel_type = rel["rel_type"]
        is_from = rel["from_table_id"] == table_id

        if rel_type in ("1-1", "1-n"):
            if is_from:
                col = f"rel_{rel_id}"
                fk_val = item["fields"].get(col) or item.get(col)
                if fk_val is not None:
                    label = get_item_label(conn, rel["to_table_id"], fk_val)
                else:
                    fk_val = None
                    label = None
                relationships[rel_name] = {
                    "rel_id": rel_id,
                    "rel_type": rel_type,
                    "direction": "from",
                    "table_id": rel["to_table_id"],
                    "item_id": fk_val,
                    "label": label,
                }
            else:
                other_table = rel["from_table_id"]
                other_items = get_items_table(other_table)
                col = f"rel_{rel_id}"
                rows = conn.execute(
                    f"SELECT id, owner FROM {other_items} WHERE {col} = ?",
                    (item["id"],),
                ).fetchall()
                relationships[rel_name] = {
                    "rel_id": rel_id,
                    "rel_type": rel_type,
                    "direction": "to",
                    "table_id": other_table,
                    "items": [
                        {"item_id": r["id"], "label": r["owner"] or str(r["id"])}
                        for r in rows
                    ],
                }
        elif rel_type == "n-n":
            junction = f"rel_{rel_id}"
            if is_from:
                other_table = rel["to_table_id"]
                rows = conn.execute(
                    f"SELECT to_item_id FROM {junction} WHERE from_item_id = ?",
                    (item["id"],),
                ).fetchall()
                items_list = []
                for r in rows:
                    tid = r["to_item_id"]
                    label = get_item_label(conn, other_table, tid)
                    items_list.append({"item_id": tid, "label": label})
                relationships[rel_name] = {
                    "rel_id": rel_id,
                    "rel_type": rel_type,
                    "direction": "from",
                    "table_id": other_table,
                    "items": items_list,
                }
            else:
                other_table = rel["from_table_id"]
                rows = conn.execute(
                    f"SELECT from_item_id FROM {junction} WHERE to_item_id = ?",
                    (item["id"],),
                ).fetchall()
                items_list = []
                for r in rows:
                    fid = r["from_item_id"]
                    label = get_item_label(conn, other_table, fid)
                    items_list.append({"item_id": fid, "label": label})
                relationships[rel_name] = {
                    "rel_id": rel_id,
                    "rel_type": rel_type,
                    "direction": "to",
                    "table_id": other_table,
                    "items": items_list,
                }
    item["relationships"] = relationships
    return item


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="Dynamic CRUD", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Table management ──────────────────────────────────────────────────────────

class TableCreate(BaseModel):
    name: str
    label: str = ""


class TableUpdate(BaseModel):
    name: str | None = None
    label: str | None = None


@app.get("/api/tables")
def list_tables():
    conn = get_db()
    rows = conn.execute("SELECT * FROM dynamic_tables ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/tables", status_code=201)
def create_table(payload: TableCreate):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM dynamic_tables WHERE name = ?", (payload.name,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, f"Table '{payload.name}' already exists")

    conn.execute(
        "INSERT INTO dynamic_tables (name, label) VALUES (?, ?)",
        (payload.name, payload.label or payload.name),
    )
    table_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(f"""
        CREATE TABLE {get_items_table(table_id)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL DEFAULT 'default',
            data TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    row = conn.execute(
        "SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    conn.close()
    return dict(row)


@app.put("/api/tables/{table_id}")
def update_table(table_id: int, payload: TableUpdate):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Table not found")
    if payload.name is not None:
        conn.execute(
            "UPDATE dynamic_tables SET name = ? WHERE id = ?",
            (payload.name, table_id),
        )
    if payload.label is not None:
        conn.execute(
            "UPDATE dynamic_tables SET label = ? WHERE id = ?",
            (payload.label, table_id),
        )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/api/tables/{table_id}")
def delete_table(table_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Table not found")

    rels = get_relationships(conn, table_id)
    for rel in rels:
        _drop_relationship_storage(conn, rel)

    conn.execute("DELETE FROM dynamic_relationships WHERE from_table_id = ? OR to_table_id = ?",
                 (table_id, table_id))
    conn.execute("DELETE FROM dynamic_fields WHERE table_id = ?", (table_id,))
    conn.execute(f"DROP TABLE IF EXISTS {get_items_table(table_id)}")
    conn.execute("DELETE FROM dynamic_tables WHERE id = ?", (table_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Field management ──────────────────────────────────────────────────────────

class FieldCreate(BaseModel):
    field_name: str
    field_type: str
    field_label: str = ""

    @model_validator(mode="after")
    def check_type(self):
        if self.field_type not in FIELD_TYPES:
            raise ValueError(f"field_type must be one of {FIELD_TYPES}")
        return self


class FieldUpdate(BaseModel):
    field_label: str | None = None
    field_type: str | None = None

    @model_validator(mode="after")
    def check_type(self):
        if self.field_type is not None and self.field_type not in FIELD_TYPES:
            raise ValueError(f"field_type must be one of {FIELD_TYPES}")
        return self


def _ensure_table_exists(conn: sqlite3.Connection, table_id: int):
    row = conn.execute(
        "SELECT id FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Table not found")
    return row


@app.get("/api/tables/{table_id}/fields")
def list_fields(table_id: int):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    fields = get_fields(conn, table_id)
    conn.close()
    return fields


@app.post("/api/tables/{table_id}/fields", status_code=201)
def create_field(table_id: int, payload: FieldCreate):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    existing = conn.execute(
        "SELECT id FROM dynamic_fields WHERE table_id = ? AND field_name = ?",
        (table_id, payload.field_name),
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(
            400, f"Field '{payload.field_name}' already exists in this table"
        )
    if payload.field_name in RESERVED_FIELD_NAMES:
        conn.close()
        raise HTTPException(400, f"Field name '{payload.field_name}' is reserved")

    max_order = conn.execute(
        "SELECT COALESCE(MAX(field_order), -1) FROM dynamic_fields WHERE table_id = ?",
        (table_id,),
    ).fetchone()[0]

    conn.execute(
        "INSERT INTO dynamic_fields (table_id, field_name, field_type, field_label, field_order) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            table_id,
            payload.field_name,
            payload.field_type,
            payload.field_label or payload.field_name,
            max_order + 1,
        ),
    )
    alter_table_for_new_field(conn, table_id, payload.field_name, payload.field_type)
    conn.commit()

    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE table_id = ? AND field_name = ?",
        (table_id, payload.field_name),
    ).fetchone()
    conn.close()
    return dict(row)


@app.put("/api/tables/{table_id}/fields/{field_id}")
def update_field(table_id: int, field_id: int, payload: FieldUpdate):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE id = ? AND table_id = ?",
        (field_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Field not found")

    if payload.field_label is not None:
        conn.execute(
            "UPDATE dynamic_fields SET field_label = ? WHERE id = ?",
            (payload.field_label, field_id),
        )
    if payload.field_type is not None:
        conn.execute(
            "UPDATE dynamic_fields SET field_type = ? WHERE id = ?",
            (payload.field_type, field_id),
        )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE id = ?", (field_id,)
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/api/tables/{table_id}/fields/{field_id}")
def delete_field(table_id: int, field_id: int):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE id = ? AND table_id = ?",
        (field_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Field not found")

    field_name = row["field_name"]
    conn.execute("DELETE FROM dynamic_fields WHERE id = ?", (field_id,))
    drop_column_from_table(conn, table_id, field_name)
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/tables/{table_id}/fields/reorder")
def reorder_fields(table_id: int, order: list[int]):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    for idx, fid in enumerate(order):
        conn.execute(
            "UPDATE dynamic_fields SET field_order = ? WHERE id = ? AND table_id = ?",
            (idx, fid, table_id),
        )
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Relationship management ───────────────────────────────────────────────────

class RelationshipCreate(BaseModel):
    to_table_id: int
    rel_name: str
    rel_label: str = ""
    rel_type: str
    from_label: str = ""
    to_label: str = ""

    @model_validator(mode="after")
    def check_rel_type(self):
        if self.rel_type not in REL_TYPES:
            raise ValueError(f"rel_type must be one of {REL_TYPES}")
        return self


class RelationshipUpdate(BaseModel):
    rel_label: str | None = None
    from_label: str | None = None
    to_label: str | None = None


def _create_relationship_storage(conn: sqlite3.Connection, rel: dict):
    rel_id = rel["id"]
    rel_type = rel["rel_type"]
    from_table = get_items_table(rel["from_table_id"])
    to_table = get_items_table(rel["to_table_id"])

    if rel_type in ("1-1", "1-n"):
        col = f"rel_{rel_id}"
        try:
            conn.execute(
                f"ALTER TABLE {from_table} ADD COLUMN {col} INTEGER REFERENCES {to_table}(id)"
            )
        except sqlite3.OperationalError:
            pass
    elif rel_type == "n-n":
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS rel_{rel_id} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_item_id INTEGER NOT NULL REFERENCES {from_table}(id) ON DELETE CASCADE,
                to_item_id INTEGER NOT NULL REFERENCES {to_table}(id) ON DELETE CASCADE,
                UNIQUE(from_item_id, to_item_id)
            )
        """)


def _drop_relationship_storage(conn: sqlite3.Connection, rel: dict):
    rel_id = rel["id"]
    rel_type = rel["rel_type"]

    if rel_type in ("1-1", "1-n"):
        col = f"rel_{rel_id}"
        drop_column_from_table(conn, rel["from_table_id"], col)
    elif rel_type == "n-n":
        conn.execute(f"DROP TABLE IF EXISTS rel_{rel_id}")


@app.get("/api/tables/{table_id}/relationships")
def list_relationships(table_id: int):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    rels = get_relationships(conn, table_id)
    conn.close()
    return rels


@app.post("/api/tables/{table_id}/relationships", status_code=201)
def create_relationship(table_id: int, payload: RelationshipCreate):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    _ensure_table_exists(conn, payload.to_table_id)

    if not payload.rel_name or not payload.rel_name.strip():
        conn.close()
        raise HTTPException(400, "Relationship name is required")

    existing = conn.execute(
        "SELECT id FROM dynamic_relationships WHERE from_table_id = ? AND rel_name = ?",
        (table_id, payload.rel_name),
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(
            400, f"Relationship '{payload.rel_name}' already exists on this table"
        )

    conn.execute(
        "INSERT INTO dynamic_relationships "
        "(from_table_id, to_table_id, rel_name, rel_label, rel_type, from_label, to_label) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            table_id,
            payload.to_table_id,
            payload.rel_name,
            payload.rel_label or payload.rel_name,
            payload.rel_type,
            payload.from_label,
            payload.to_label,
        ),
    )
    rel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ?", (rel_id,)
    ).fetchone()
    rel = dict(row)
    _create_relationship_storage(conn, rel)
    conn.commit()
    conn.close()
    return rel


@app.put("/api/tables/{table_id}/relationships/{rel_id}")
def update_relationship(table_id: int, rel_id: int, payload: RelationshipUpdate):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ? AND (from_table_id = ? OR to_table_id = ?)",
        (rel_id, table_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Relationship not found")

    if payload.rel_label is not None:
        conn.execute(
            "UPDATE dynamic_relationships SET rel_label = ? WHERE id = ?",
            (payload.rel_label, rel_id),
        )
    if payload.from_label is not None:
        conn.execute(
            "UPDATE dynamic_relationships SET from_label = ? WHERE id = ?",
            (payload.from_label, rel_id),
        )
    if payload.to_label is not None:
        conn.execute(
            "UPDATE dynamic_relationships SET to_label = ? WHERE id = ?",
            (payload.to_label, rel_id),
        )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ?", (rel_id,)
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/api/tables/{table_id}/relationships/{rel_id}")
def delete_relationship(table_id: int, rel_id: int):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ? AND (from_table_id = ? OR to_table_id = ?)",
        (rel_id, table_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Relationship not found")

    _drop_relationship_storage(conn, dict(row))
    conn.execute("DELETE FROM dynamic_relationships WHERE id = ?", (rel_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Relationship link management ──────────────────────────────────────────────

class RelLinkSet(BaseModel):
    item_id: int
    target_ids: list[int]


@app.post("/api/tables/{table_id}/relationships/{rel_id}/link")
def set_relationship_links(table_id: int, rel_id: int, payload: RelLinkSet):
    conn = get_db()
    _ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ? AND (from_table_id = ? OR to_table_id = ?)",
        (rel_id, table_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Relationship not found")
    rel = dict(row)

    if rel["rel_type"] in ("1-1", "1-n"):
        if rel["from_table_id"] == table_id:
            items_table = get_items_table(table_id)
            col = f"rel_{rel_id}"
            val = payload.target_ids[0] if payload.target_ids else None
            conn.execute(
                f"UPDATE {items_table} SET {col} = ? WHERE id = ?",
                (val, payload.item_id),
            )
        else:
            other_table = get_items_table(rel["from_table_id"])
            col = f"rel_{rel_id}"
            conn.execute(
                f"UPDATE {other_table} SET {col} = NULL WHERE {col} = ?",
                (payload.item_id,),
            )
            for tid in payload.target_ids:
                conn.execute(
                    f"UPDATE {other_table} SET {col} = ? WHERE id = ?",
                    (payload.item_id, tid),
                )
    elif rel["rel_type"] == "n-n":
        junction = f"rel_{rel_id}"
        if rel["from_table_id"] == table_id:
            conn.execute(
                f"DELETE FROM {junction} WHERE from_item_id = ?",
                (payload.item_id,),
            )
            for tid in payload.target_ids:
                conn.execute(
                    f"INSERT OR IGNORE INTO {junction} (from_item_id, to_item_id) VALUES (?, ?)",
                    (payload.item_id, tid),
                )
        else:
            conn.execute(
                f"DELETE FROM {junction} WHERE to_item_id = ?",
                (payload.item_id,),
            )
            for tid in payload.target_ids:
                conn.execute(
                    f"INSERT OR IGNORE INTO {junction} (from_item_id, to_item_id) VALUES (?, ?)",
                    (tid, payload.item_id),
                )

    conn.commit()
    conn.close()
    return {"ok": True}


# ── CRUD items ────────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    owner: str = "default"
    data: dict[str, Any] = {}


class ItemUpdate(BaseModel):
    owner: str | None = None
    data: dict[str, Any] | None = None


@app.get("/api/tables/{table_id}/items")
def list_items(
    table_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    fields = get_fields(conn, table_id)
    field_names = [f["field_name"] for f in fields]
    items_table = get_items_table(table_id)

    rels = get_relationships_from(conn, table_id)
    rel_cols = [f"rel_{r['id']}" for r in rels if r["rel_type"] in ("1-1", "1-n")]

    where_clause = ""
    params: list = []
    if search:
        search_cols = ["owner"] + field_names + rel_cols
        like_parts = " OR ".join(f"{c} LIKE ?" for c in search_cols)
        where_clause = f"WHERE {like_parts}"
        params = [f"%{search}%"] * len(search_cols)

    allowed_sort = ["id", "owner", "created_at", "updated_at"] + field_names + rel_cols
    if sort_by and sort_by in allowed_sort:
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        order_clause = f"ORDER BY {sort_by} {direction}"
    else:
        order_clause = "ORDER BY id DESC"

    count_sql = f"SELECT COUNT(*) FROM {items_table} {where_clause}"
    total = conn.execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * page_size
    items_sql = (
        f"SELECT * FROM {items_table} {where_clause} {order_clause} LIMIT ? OFFSET ?"
    )
    rows = conn.execute(items_sql, params + [page_size, offset]).fetchall()

    items = [item_row_to_dict(r, fields) for r in rows]
    items = [enrich_item_with_relationships(conn, table_id, item) for item in items]
    conn.close()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@app.get("/api/tables/{table_id}/items/{item_id}")
def get_item(table_id: int, item_id: int):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    fields = get_fields(conn, table_id)
    items_table = get_items_table(table_id)

    row = conn.execute(
        f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")
    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    conn.close()
    return item


@app.post("/api/tables/{table_id}/items", status_code=201)
def create_item(table_id: int, payload: ItemCreate):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    fields = get_fields(conn, table_id)
    validated = validate_item_data(fields, payload.data)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    json_data = json.dumps(validated, ensure_ascii=False)
    items_table = get_items_table(table_id)

    conn.execute(
        f"INSERT INTO {items_table} (owner, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (payload.owner, json_data, now, now),
    )
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    set_cols = ", ".join(f"{k} = ?" for k in validated if validated[k] is not None)
    set_vals = [v for v in validated.values() if v is not None]
    if set_cols:
        conn.execute(
            f"UPDATE {items_table} SET {set_cols} WHERE id = ?",
            set_vals + [item_id],
        )
    conn.commit()

    row = conn.execute(
        f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)
    ).fetchone()
    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    conn.close()
    return item


@app.put("/api/tables/{table_id}/items/{item_id}")
def update_item(table_id: int, item_id: int, payload: ItemUpdate):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    fields = get_fields(conn, table_id)
    items_table = get_items_table(table_id)

    row = conn.execute(
        f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if payload.owner is not None:
        conn.execute(
            f"UPDATE {items_table} SET owner = ?, updated_at = ? WHERE id = ?",
            (payload.owner, now, item_id),
        )
    else:
        conn.execute(
            f"UPDATE {items_table} SET updated_at = ? WHERE id = ?",
            (now, item_id),
        )

    if payload.data is not None:
        validated = validate_item_data(fields, payload.data)
        json_data = json.dumps(validated, ensure_ascii=False)
        conn.execute(
            f"UPDATE {items_table} SET data = ? WHERE id = ?",
            (json_data, item_id),
        )
        set_cols = ", ".join(f"{k} = ?" for k in validated if validated[k] is not None)
        set_vals = [v for v in validated.values() if v is not None]
        if set_cols:
            conn.execute(
                f"UPDATE {items_table} SET {set_cols} WHERE id = ?",
                set_vals + [item_id],
            )

    conn.commit()
    row = conn.execute(
        f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)
    ).fetchone()
    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    conn.close()
    return item


@app.delete("/api/tables/{table_id}/items/{item_id}")
def delete_item(table_id: int, item_id: int):
    conn = get_db()
    _ensure_table_exists(conn, table_id)
    items_table = get_items_table(table_id)

    conn.execute(f"DELETE FROM {items_table} WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Serve frontend ────────────────────────────────────────────────────────────
STATIC_DIR.mkdir(exist_ok=True)
assets_dir = STATIC_DIR / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static_assets")


@app.get("/{path:path}")
async def serve_frontend(path: str):
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(404, "Not found")
