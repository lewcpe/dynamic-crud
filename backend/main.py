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


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_name TEXT NOT NULL UNIQUE,
            field_type TEXT NOT NULL CHECK(field_type IN ('int','float','text','date','datetime')),
            field_label TEXT NOT NULL DEFAULT '',
            field_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL DEFAULT 'default',
            data TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def get_fields(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM dynamic_fields ORDER BY field_order, id").fetchall()
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


def alter_table_for_new_field(conn: sqlite3.Connection, field_name: str, field_type: str):
    sqlite_type = "TEXT"
    if field_type == "int":
        sqlite_type = "INTEGER"
    elif field_type == "float":
        sqlite_type = "REAL"
    try:
        conn.execute(f"ALTER TABLE dynamic_items ADD COLUMN {field_name} {sqlite_type}")
    except sqlite3.OperationalError:
        pass


def drop_column_from_table(conn: sqlite3.Connection, field_name: str):
    """SQLite 3.35+ supports DROP COLUMN. Recreate table as fallback."""
    try:
        conn.execute(f"ALTER TABLE dynamic_items DROP COLUMN {field_name}")
    except sqlite3.OperationalError:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(dynamic_items)").fetchall()]
        if field_name not in cols:
            return
        cols = [c for c in cols if c != field_name]
        quoted = ", ".join(cols)
        conn.execute("CREATE TABLE dynamic_items_new AS SELECT " + quoted + " FROM dynamic_items")
        conn.execute("DROP TABLE dynamic_items")
        conn.execute("ALTER TABLE dynamic_items_new RENAME TO dynamic_items")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Dynamic CRUD", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Field management ────────────────────────────────────────────────────────

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




@app.get("/api/fields")
def list_fields():
    conn = get_db()
    fields = get_fields(conn)
    conn.close()
    return fields


@app.post("/api/fields", status_code=201)
def create_field(payload: FieldCreate):
    conn = get_db()
    existing = conn.execute("SELECT id FROM dynamic_fields WHERE field_name=?", (payload.field_name,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, f"Field '{payload.field_name}' already exists")
    if payload.field_name in ("id", "owner", "created_at", "updated_at", "data"):
        conn.close()
        raise HTTPException(400, f"Field name '{payload.field_name}' is reserved")

    max_order = conn.execute("SELECT COALESCE(MAX(field_order),-1) FROM dynamic_fields").fetchone()[0]
    conn.execute(
        "INSERT INTO dynamic_fields (field_name, field_type, field_label, field_order) VALUES (?,?,?,?)",
        (payload.field_name, payload.field_type, payload.field_label or payload.field_name, max_order + 1),
    )
    alter_table_for_new_field(conn, payload.field_name, payload.field_type)
    conn.commit()
    row = conn.execute("SELECT * FROM dynamic_fields WHERE field_name=?", (payload.field_name,)).fetchone()
    conn.close()
    return dict(row)


@app.put("/api/fields/{field_id}")
def update_field(field_id: int, payload: FieldUpdate):
    conn = get_db()
    row = conn.execute("SELECT * FROM dynamic_fields WHERE id=?", (field_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Field not found")
    if payload.field_label is not None:
        conn.execute("UPDATE dynamic_fields SET field_label=? WHERE id=?", (payload.field_label, field_id))
    if payload.field_type is not None:
        conn.execute("UPDATE dynamic_fields SET field_type=? WHERE id=?", (payload.field_type, field_id))
    conn.commit()
    row = conn.execute("SELECT * FROM dynamic_fields WHERE id=?", (field_id,)).fetchone()
    conn.close()
    return dict(row)


@app.delete("/api/fields/{field_id}")
def delete_field(field_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM dynamic_fields WHERE id=?", (field_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Field not found")
    field_name = row["field_name"]
    conn.execute("DELETE FROM dynamic_fields WHERE id=?", (field_id,))
    drop_column_from_table(conn, field_name)
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/fields/reorder")
def reorder_fields(order: list[int]):
    conn = get_db()
    for idx, fid in enumerate(order):
        conn.execute("UPDATE dynamic_fields SET field_order=? WHERE id=?", (idx, fid))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── CRUD items ───────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    owner: str = "default"
    data: dict[str, Any] = {}


class ItemUpdate(BaseModel):
    owner: str | None = None
    data: dict[str, Any] | None = None


def item_row_to_dict(row: sqlite3.Row, fields: list[dict]) -> dict:
    item = dict(row)
    item.pop("data")
    json_data = {}
    try:
        json_data = json.loads(row["data"] or "{}")
    except json.JSONDecodeError:
        pass
    for f in fields:
        name = f["field_name"]
        if name not in json_data:
            json_data[name] = row[name] if name in row.keys() else None
        # prefer json value
    item["fields"] = json_data
    return item


@app.get("/api/items")
def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
):
    conn = get_db()
    fields = get_fields(conn)
    field_names = [f["field_name"] for f in fields]

    where_clause = ""
    params: list = []
    if search:
        search_cols = ["owner"] + field_names
        like_parts = " OR ".join(f"{c} LIKE ?" for c in search_cols)
        where_clause = f"WHERE {like_parts}"
        params = [f"%{search}%"] * len(search_cols)

    if sort_by and (sort_by in field_names or sort_by in ("id", "owner", "created_at", "updated_at")):
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        order_clause = f"ORDER BY {sort_by} {direction}"
    else:
        order_clause = "ORDER BY id DESC"

    count_sql = f"SELECT COUNT(*) FROM dynamic_items {where_clause}"
    total = conn.execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * page_size
    items_sql = f"SELECT * FROM dynamic_items {where_clause} {order_clause} LIMIT ? OFFSET ?"
    rows = conn.execute(items_sql, params + [page_size, offset]).fetchall()

    items = [item_row_to_dict(r, fields) for r in rows]
    conn.close()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@app.get("/api/items/{item_id}")
def get_item(item_id: int):
    conn = get_db()
    fields = get_fields(conn)
    row = conn.execute("SELECT * FROM dynamic_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Item not found")
    return item_row_to_dict(row, fields)


@app.post("/api/items", status_code=201)
def create_item(payload: ItemCreate):
    conn = get_db()
    fields = get_fields(conn)
    validated = validate_item_data(fields, payload.data)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    json_data = json.dumps(validated, ensure_ascii=False)
    conn.execute(
        "INSERT INTO dynamic_items (owner, data, created_at, updated_at) VALUES (?,?,?,?)",
        (payload.owner, json_data, now, now),
    )
    # Also set per-column values for direct SQL querying
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    set_cols = ", ".join(f"{k} = ?" for k in validated if validated[k] is not None)
    set_vals = [v for v in validated.values() if v is not None]
    if set_cols:
        conn.execute(f"UPDATE dynamic_items SET {set_cols} WHERE id=?", set_vals + [item_id])
    conn.commit()
    row = conn.execute("SELECT * FROM dynamic_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return item_row_to_dict(row, fields)


@app.put("/api/items/{item_id}")
def update_item(item_id: int, payload: ItemUpdate):
    conn = get_db()
    fields = get_fields(conn)
    row = conn.execute("SELECT * FROM dynamic_items WHERE id=?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if payload.owner is not None:
        conn.execute("UPDATE dynamic_items SET owner=?, updated_at=? WHERE id=?", (payload.owner, now, item_id))
    else:
        conn.execute("UPDATE dynamic_items SET updated_at=? WHERE id=?", (now, item_id))

    if payload.data is not None:
        validated = validate_item_data(fields, payload.data)
        json_data = json.dumps(validated, ensure_ascii=False)
        conn.execute("UPDATE dynamic_items SET data=? WHERE id=?", (json_data, item_id))
        set_cols = ", ".join(f"{k} = ?" for k in validated if validated[k] is not None)
        set_vals = [v for v in validated.values() if v is not None]
        if set_cols:
            conn.execute(f"UPDATE dynamic_items SET {set_cols} WHERE id=?", set_vals + [item_id])

    conn.commit()
    row = conn.execute("SELECT * FROM dynamic_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return item_row_to_dict(row, fields)


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int):
    conn = get_db()
    conn.execute("DELETE FROM dynamic_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Serve frontend ───────────────────────────────────────────────────────────
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
