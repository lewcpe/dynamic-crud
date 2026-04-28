from fastapi import APIRouter, HTTPException
from ..database import get_db, get_items_table, get_fields
from ..models import TableCreate, TableUpdate
from ..helpers import get_default_represent, format_represent

router = APIRouter(prefix="/api/tables", tags=["tables"])


@router.get("")
def list_tables():
    conn = get_db()
    rows = conn.execute("SELECT * FROM dynamic_tables ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def create_table(payload: TableCreate):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM dynamic_tables WHERE name = ?", (payload.name,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, f"Table '{payload.name}' already exists")

    conn.execute(
        "INSERT INTO dynamic_tables (name, label, represent) VALUES (?, ?, ?)",
        (payload.name, payload.label or payload.name, payload.represent),
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


@router.put("/{table_id}")
def update_table(table_id: int, payload: TableUpdate):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Table not found")
    if payload.name is not None:
        conn.execute("UPDATE dynamic_tables SET name = ? WHERE id = ?", (payload.name, table_id))
    if payload.label is not None:
        conn.execute("UPDATE dynamic_tables SET label = ? WHERE id = ?", (payload.label, table_id))
    if payload.represent is not None:
        conn.execute("UPDATE dynamic_tables SET represent = ? WHERE id = ?", (payload.represent, table_id))
    conn.commit()
    row = conn.execute("SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)).fetchone()
    conn.close()
    return dict(row)


@router.delete("/{table_id}")
def delete_table(table_id: int):
    from ..helpers import enrich_item_with_relationships
    from ..database import get_relationships

    conn = get_db()
    row = conn.execute("SELECT * FROM dynamic_tables WHERE id = ?", (table_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Table not found")

    rels = get_relationships(conn, table_id)
    for rel in rels:
        _drop_relationship_storage(conn, rel)

    conn.execute("DELETE FROM dynamic_relationships WHERE from_table_id = ? OR to_table_id = ?", (table_id, table_id))
    conn.execute("DELETE FROM dynamic_fields WHERE table_id = ?", (table_id,))
    conn.execute(f"DROP TABLE IF EXISTS {get_items_table(table_id)}")
    conn.execute("DELETE FROM dynamic_tables WHERE id = ?", (table_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


def _drop_relationship_storage(conn, rel: dict):
    from ..database import drop_column_from_table
    rel_id = rel["id"]
    rel_type = rel["rel_type"]

    if rel_type in ("1-1", "1-n"):
        col = f"rel_{rel_id}"
        drop_column_from_table(conn, rel["from_table_id"], col)
    elif rel_type == "n-n":
        conn.execute(f"DROP TABLE IF EXISTS rel_{rel_id}")
