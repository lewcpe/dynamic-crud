from fastapi import APIRouter, HTTPException, Depends
from ..database import get_db, ensure_table_exists
from ..models import PermissionCreate, PermissionUpdate
from ..auth import get_current_user, require_admin
from ..permissions import check_table_permission, get_user_permissions

router = APIRouter(tags=["permissions"])


@router.get("/api/tables/{table_id}/permissions")
def list_permissions(table_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    perms = conn.execute("SELECT * FROM permissions WHERE table_id = ?", (table_id,)).fetchall()
    conn.close()
    return [dict(p) for p in perms]


@router.post("/api/tables/{table_id}/permissions", status_code=201)
def create_permission(table_id: int, payload: PermissionCreate, admin: dict = Depends(require_admin)):
    conn = get_db()
    ensure_table_exists(conn, table_id)

    conn.execute(
        "INSERT INTO permissions (table_id, target_type, target_id, target_role, "
        "list_rule, view_rule, create_rule, update_rule, delete_rule) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (table_id, payload.target_type, payload.target_id, payload.target_role,
         payload.list_rule, payload.view_rule, payload.create_rule,
         payload.update_rule, payload.delete_rule),
    )
    perm_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    perm = dict(conn.execute("SELECT * FROM permissions WHERE id = ?", (perm_id,)).fetchone())
    conn.close()
    return perm


@router.put("/api/tables/{table_id}/permissions/{perm_id}")
def update_permission(table_id: int, perm_id: int, payload: PermissionUpdate, admin: dict = Depends(require_admin)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    perm = conn.execute(
        "SELECT * FROM permissions WHERE id = ? AND table_id = ?", (perm_id, table_id)
    ).fetchone()
    if not perm:
        conn.close()
        raise HTTPException(404, "Permission not found")

    for field in ("list_rule", "view_rule", "create_rule", "update_rule", "delete_rule"):
        val = getattr(payload, field)
        if val is not None:
            conn.execute(f"UPDATE permissions SET {field} = ? WHERE id = ?", (val, perm_id))
    conn.commit()
    perm = dict(conn.execute("SELECT * FROM permissions WHERE id = ?", (perm_id,)).fetchone())
    conn.close()
    return perm


@router.delete("/api/tables/{table_id}/permissions/{perm_id}")
def delete_permission(table_id: int, perm_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    perm = conn.execute(
        "SELECT * FROM permissions WHERE id = ? AND table_id = ?", (perm_id, table_id)
    ).fetchone()
    if not perm:
        conn.close()
        raise HTTPException(404, "Permission not found")
    conn.execute("DELETE FROM permissions WHERE id = ?", (perm_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/tables/{table_id}/my-permissions")
def get_my_permissions(table_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    perms = get_user_permissions(conn, table_id, user)
    conn.close()
    return perms
