import json
from fastapi import APIRouter, HTTPException, Depends
from ..database import get_db, ensure_table_exists, get_fields
from ..auth import get_current_user

router = APIRouter(tags=["view-prefs"])


@router.get("/api/tables/{table_id}/view-prefs")
def get_view_prefs(table_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    row = conn.execute(
        "SELECT hidden_columns FROM user_view_prefs WHERE user_id = ? AND table_id = ?",
        (user["id"], table_id),
    ).fetchone()
    conn.close()
    if row:
        return {"hidden_columns": json.loads(row["hidden_columns"])}
    return {"hidden_columns": None}


@router.put("/api/tables/{table_id}/view-prefs")
def set_view_prefs(table_id: int, payload: dict, user: dict = Depends(get_current_user)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    hidden = payload.get("hidden_columns", [])
    hidden_json = json.dumps(hidden)

    existing = conn.execute(
        "SELECT id FROM user_view_prefs WHERE user_id = ? AND table_id = ?",
        (user["id"], table_id),
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE user_view_prefs SET hidden_columns = ? WHERE user_id = ? AND table_id = ?",
            (hidden_json, user["id"], table_id),
        )
    else:
        conn.execute(
            "INSERT INTO user_view_prefs (user_id, table_id, hidden_columns) VALUES (?, ?, ?)",
            (user["id"], table_id, hidden_json),
        )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/api/tables/{table_id}/view-prefs")
def delete_view_prefs(table_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    conn.execute(
        "DELETE FROM user_view_prefs WHERE user_id = ? AND table_id = ?",
        (user["id"], table_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}
