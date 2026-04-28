from fastapi import APIRouter, HTTPException
from ..database import get_db, get_fields, alter_table_for_new_field, drop_column_from_table, ensure_table_exists, RESERVED_FIELD_NAMES
from ..models import FieldCreate, FieldUpdate

router = APIRouter(prefix="/api/tables/{table_id}/fields", tags=["fields"])


@router.get("")
def list_fields(table_id: int):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    fields = get_fields(conn, table_id)
    conn.close()
    return fields


@router.post("", status_code=201)
def create_field(table_id: int, payload: FieldCreate):
    conn = get_db()
    ensure_table_exists(conn, table_id)

    existing = conn.execute(
        "SELECT id FROM dynamic_fields WHERE table_id = ? AND field_name = ?",
        (table_id, payload.field_name),
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, f"Field '{payload.field_name}' already exists in this table")
    if payload.field_name in RESERVED_FIELD_NAMES:
        conn.close()
        raise HTTPException(400, f"Field name '{payload.field_name}' is reserved")

    max_order = conn.execute(
        "SELECT COALESCE(MAX(field_order), -1) FROM dynamic_fields WHERE table_id = ?",
        (table_id,),
    ).fetchone()[0]

    conn.execute(
        "INSERT INTO dynamic_fields (table_id, field_name, field_type, field_label, field_order) VALUES (?, ?, ?, ?, ?)",
        (table_id, payload.field_name, payload.field_type, payload.field_label or payload.field_name, max_order + 1),
    )
    alter_table_for_new_field(conn, table_id, payload.field_name, payload.field_type)
    conn.commit()

    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE table_id = ? AND field_name = ?",
        (table_id, payload.field_name),
    ).fetchone()
    conn.close()
    return dict(row)


@router.put("/{field_id}")
def update_field(table_id: int, field_id: int, payload: FieldUpdate):
    conn = get_db()
    ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE id = ? AND table_id = ?", (field_id, table_id)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Field not found")

    if payload.field_label is not None:
        conn.execute("UPDATE dynamic_fields SET field_label = ? WHERE id = ?", (payload.field_label, field_id))
    if payload.field_type is not None:
        conn.execute("UPDATE dynamic_fields SET field_type = ? WHERE id = ?", (payload.field_type, field_id))
    conn.commit()
    row = conn.execute("SELECT * FROM dynamic_fields WHERE id = ?", (field_id,)).fetchone()
    conn.close()
    return dict(row)


@router.delete("/{field_id}")
def delete_field(table_id: int, field_id: int):
    conn = get_db()
    ensure_table_exists(conn, table_id)

    row = conn.execute(
        "SELECT * FROM dynamic_fields WHERE id = ? AND table_id = ?", (field_id, table_id)
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


@router.post("/reorder")
def reorder_fields(table_id: int, order: list[int]):
    conn = get_db()
    ensure_table_exists(conn, table_id)

    for idx, fid in enumerate(order):
        conn.execute(
            "UPDATE dynamic_fields SET field_order = ? WHERE id = ? AND table_id = ?",
            (idx, fid, table_id),
        )
    conn.commit()
    conn.close()
    return {"ok": True}
