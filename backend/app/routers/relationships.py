from fastapi import APIRouter, HTTPException
from ..database import get_db, get_items_table, get_relationships, get_relationships_from, ensure_table_exists, drop_column_from_table
from ..models import RelationshipCreate, RelationshipUpdate, RelLinkSet

router = APIRouter(prefix="/api/tables/{table_id}/relationships", tags=["relationships"])


def _create_relationship_storage(conn, rel: dict):
    rel_id = rel["id"]
    rel_type = rel["rel_type"]
    from_table = get_items_table(rel["from_table_id"])
    to_system = rel.get("to_system_table")

    if to_system:
        to_table_ref = to_system
    else:
        to_table_ref = get_items_table(rel["to_table_id"])

    if rel_type in ("1-1", "1-n"):
        col = f"rel_{rel_id}"
        try:
            conn.execute(
                f"ALTER TABLE {from_table} ADD COLUMN {col} INTEGER REFERENCES {to_table_ref}(id)"
            )
        except:
            pass
    elif rel_type == "n-n":
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS rel_{rel_id} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_item_id INTEGER NOT NULL REFERENCES {from_table}(id) ON DELETE CASCADE,
                to_item_id INTEGER NOT NULL REFERENCES {to_table_ref}(id) ON DELETE CASCADE,
                UNIQUE(from_item_id, to_item_id)
            )
        """)


def _drop_relationship_storage(conn, rel: dict):
    rel_id = rel["id"]
    rel_type = rel["rel_type"]

    if rel_type in ("1-1", "1-n"):
        col = f"rel_{rel_id}"
        drop_column_from_table(conn, rel["from_table_id"], col)
    elif rel_type == "n-n":
        conn.execute(f"DROP TABLE IF EXISTS rel_{rel_id}")


@router.get("")
def list_relationships(table_id: int):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    rels = get_relationships(conn, table_id)
    conn.close()
    return rels


@router.post("", status_code=201)
def create_relationship(table_id: int, payload: RelationshipCreate):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    if payload.to_table_id:
        ensure_table_exists(conn, payload.to_table_id)

    if not payload.rel_name or not payload.rel_name.strip():
        conn.close()
        raise HTTPException(400, "Relationship name is required")

    existing = conn.execute(
        "SELECT id FROM dynamic_relationships WHERE from_table_id = ? AND rel_name = ?",
        (table_id, payload.rel_name),
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, f"Relationship '{payload.rel_name}' already exists on this table")

    conn.execute(
        "INSERT INTO dynamic_relationships "
        "(from_table_id, to_table_id, to_system_table, rel_name, rel_label, rel_type, from_label, to_label) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (table_id, payload.to_table_id, payload.to_system_table, payload.rel_name,
         payload.rel_label or payload.rel_name, payload.rel_type, payload.from_label, payload.to_label),
    )
    rel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute("SELECT * FROM dynamic_relationships WHERE id = ?", (rel_id,)).fetchone()
    rel = dict(row)
    _create_relationship_storage(conn, rel)
    conn.commit()
    conn.close()
    return rel


@router.put("/{rel_id}")
def update_relationship(table_id: int, rel_id: int, payload: RelationshipUpdate):
    conn = get_db()
    ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_relationships WHERE id = ? AND (from_table_id = ? OR to_table_id = ?)",
        (rel_id, table_id, table_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Relationship not found")

    if payload.rel_label is not None:
        conn.execute("UPDATE dynamic_relationships SET rel_label = ? WHERE id = ?", (payload.rel_label, rel_id))
    if payload.from_label is not None:
        conn.execute("UPDATE dynamic_relationships SET from_label = ? WHERE id = ?", (payload.from_label, rel_id))
    if payload.to_label is not None:
        conn.execute("UPDATE dynamic_relationships SET to_label = ? WHERE id = ?", (payload.to_label, rel_id))
    conn.commit()
    row = conn.execute("SELECT * FROM dynamic_relationships WHERE id = ?", (rel_id,)).fetchone()
    conn.close()
    return dict(row)


@router.delete("/{rel_id}")
def delete_relationship(table_id: int, rel_id: int):
    conn = get_db()
    ensure_table_exists(conn, table_id)

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


@router.post("/{rel_id}/link")
def set_relationship_links(table_id: int, rel_id: int, payload: RelLinkSet):
    conn = get_db()
    ensure_table_exists(conn, table_id)

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
            conn.execute(f"UPDATE {items_table} SET {col} = ? WHERE id = ?", (val, payload.item_id))
        else:
            other_table = get_items_table(rel["from_table_id"])
            col = f"rel_{rel_id}"
            conn.execute(f"UPDATE {other_table} SET {col} = NULL WHERE {col} = ?", (payload.item_id,))
            for tid in payload.target_ids:
                conn.execute(f"UPDATE {other_table} SET {col} = ? WHERE id = ?", (payload.item_id, tid))
    elif rel["rel_type"] == "n-n":
        junction = f"rel_{rel_id}"
        if rel["from_table_id"] == table_id:
            conn.execute(f"DELETE FROM {junction} WHERE from_item_id = ?", (payload.item_id,))
            for tid in payload.target_ids:
                conn.execute(f"INSERT OR IGNORE INTO {junction} (from_item_id, to_item_id) VALUES (?, ?)", (payload.item_id, tid))
        else:
            conn.execute(f"DELETE FROM {junction} WHERE to_item_id = ?", (payload.item_id,))
            for tid in payload.target_ids:
                conn.execute(f"INSERT OR IGNORE INTO {junction} (from_item_id, to_item_id) VALUES (?, ?)", (tid, payload.item_id))

    conn.commit()
    conn.close()
    return {"ok": True}
