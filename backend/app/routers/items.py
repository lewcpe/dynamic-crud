import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Depends
from ..database import get_db, get_fields, get_relationships_from, get_items_table, ensure_table_exists
from ..models import ItemCreate, ItemUpdate
from ..auth import get_current_user_optional
from ..permissions import check_table_permission, get_row_level_filter
from ..helpers import item_row_to_dict, enrich_item_with_relationships

router = APIRouter(prefix="/api/tables/{table_id}/items", tags=["items"])


@router.get("")
def list_items(
    table_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    user: dict | None = Depends(get_current_user_optional),
):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    if not check_table_permission(conn, table_id, "list", user):
        conn.close()
        raise HTTPException(403, "Not authorized to list items")
    fields = get_fields(conn, table_id)
    field_names = [f["field_name"] for f in fields]
    items_table = get_items_table(table_id)

    rels = get_relationships_from(conn, table_id)
    rel_cols = [f"rel_{r['id']}" for r in rels if r["rel_type"] in ("1-1", "1-n")]

    where_parts = []
    params: list = []

    row_filter = get_row_level_filter(conn, table_id, "list", user, params)
    if row_filter is not None:
        where_parts.append(row_filter)

    if search:
        search_cols = ["owner"] + field_names + rel_cols
        like_parts = " OR ".join(f"{c} LIKE ?" for c in search_cols)
        where_parts.append(f"({like_parts})")
        params.extend([f"%{search}%"] * len(search_cols))

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    allowed_sort = ["id", "owner", "created_at", "updated_at"] + field_names + rel_cols
    if sort_by and sort_by in allowed_sort:
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        order_clause = f"ORDER BY {sort_by} {direction}"
    else:
        order_clause = "ORDER BY id DESC"

    count_sql = f"SELECT COUNT(*) FROM {items_table} {where_clause}"
    total = conn.execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * page_size
    items_sql = f"SELECT * FROM {items_table} {where_clause} {order_clause} LIMIT ? OFFSET ?"
    rows = conn.execute(items_sql, params + [page_size, offset]).fetchall()

    items = [item_row_to_dict(r, fields) for r in rows]
    items = [enrich_item_with_relationships(conn, table_id, item) for item in items]
    conn.close()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{item_id}")
def get_item(table_id: int, item_id: int, user: dict | None = Depends(get_current_user_optional)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    if not check_table_permission(conn, table_id, "view", user):
        conn.close()
        raise HTTPException(403, "Not authorized to view items")
    fields = get_fields(conn, table_id)
    items_table = get_items_table(table_id)

    row = conn.execute(f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")
    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    conn.close()
    return item


@router.post("", status_code=201)
def create_item(table_id: int, payload: ItemCreate, user: dict | None = Depends(get_current_user_optional)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    if not check_table_permission(conn, table_id, "create", user):
        conn.close()
        raise HTTPException(403, "Not authorized to create items")
    fields = get_fields(conn, table_id)
    items_table = get_items_table(table_id)

    from ..database import validate_item_data
    validated = validate_item_data(fields, payload.data)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    json_data = json.dumps(validated, ensure_ascii=False)

    conn.execute(
        f"INSERT INTO {items_table} (owner, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (payload.owner, json_data, now, now),
    )
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    set_cols = ", ".join(f"{k} = ?" for k in validated if validated[k] is not None)
    set_vals = [v for v in validated.values() if v is not None]
    if set_cols:
        conn.execute(f"UPDATE {items_table} SET {set_cols} WHERE id = ?", set_vals + [item_id])
    conn.commit()

    row = conn.execute(f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)).fetchone()
    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    conn.close()
    return item


@router.put("/{item_id}")
def update_item(table_id: int, item_id: int, payload: ItemUpdate, user: dict | None = Depends(get_current_user_optional)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    if not check_table_permission(conn, table_id, "update", user):
        conn.close()
        raise HTTPException(403, "Not authorized to update items")
    fields = get_fields(conn, table_id)
    items_table = get_items_table(table_id)

    row = conn.execute(f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    if not check_table_permission(conn, table_id, "update", user, item):
        conn.close()
        raise HTTPException(403, "Not authorized to update this item")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if payload.owner is not None:
        conn.execute(f"UPDATE {items_table} SET owner = ?, updated_at = ? WHERE id = ?", (payload.owner, now, item_id))
    else:
        conn.execute(f"UPDATE {items_table} SET updated_at = ? WHERE id = ?", (now, item_id))

    if payload.data is not None:
        from ..database import validate_item_data
        validated = validate_item_data(fields, payload.data)
        json_data = json.dumps(validated, ensure_ascii=False)
        conn.execute(f"UPDATE {items_table} SET data = ? WHERE id = ?", (json_data, item_id))
        set_cols = ", ".join(f"{k} = ?" for k in validated if validated[k] is not None)
        set_vals = [v for v in validated.values() if v is not None]
        if set_cols:
            conn.execute(f"UPDATE {items_table} SET {set_cols} WHERE id = ?", set_vals + [item_id])

    conn.commit()
    row = conn.execute(f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)).fetchone()
    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    conn.close()
    return item


@router.delete("/{item_id}")
def delete_item(table_id: int, item_id: int, user: dict | None = Depends(get_current_user_optional)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    if not check_table_permission(conn, table_id, "delete", user):
        conn.close()
        raise HTTPException(403, "Not authorized to delete items")
    fields = get_fields(conn, table_id)
    items_table = get_items_table(table_id)

    row = conn.execute(f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    item = item_row_to_dict(row, fields)
    item = enrich_item_with_relationships(conn, table_id, item)
    if not check_table_permission(conn, table_id, "delete", user, item):
        conn.close()
        raise HTTPException(403, "Not authorized to delete this item")

    conn.execute(f"DELETE FROM {items_table} WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
