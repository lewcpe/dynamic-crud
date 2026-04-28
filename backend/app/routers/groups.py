from fastapi import APIRouter, HTTPException, Depends
from ..database import get_db
from ..models import GroupCreate, GroupUpdate, GroupMemberAction
from ..auth import require_admin, get_current_user

router = APIRouter(tags=["groups"])


@router.get("/api/groups")
def list_groups(admin: dict = Depends(require_admin)):
    conn = get_db()
    groups = conn.execute("SELECT * FROM groups ORDER BY id").fetchall()
    conn.close()
    return [dict(g) for g in groups]


@router.post("/api/groups", status_code=201)
def create_group(payload: GroupCreate, admin: dict = Depends(require_admin)):
    conn = get_db()
    existing = conn.execute("SELECT id FROM groups WHERE name = ?", (payload.name,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, f"Group '{payload.name}' already exists")
    conn.execute("INSERT INTO groups (name, description) VALUES (?, ?)", (payload.name, payload.description))
    group_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    group = dict(conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone())
    conn.close()
    return group


@router.put("/api/groups/{group_id}")
def update_group(group_id: int, payload: GroupUpdate, admin: dict = Depends(require_admin)):
    conn = get_db()
    group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    if not group:
        conn.close()
        raise HTTPException(404, "Group not found")
    if payload.name is not None:
        conn.execute("UPDATE groups SET name = ? WHERE id = ?", (payload.name, group_id))
    if payload.description is not None:
        conn.execute("UPDATE groups SET description = ? WHERE id = ?", (payload.description, group_id))
    conn.commit()
    group = dict(conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone())
    conn.close()
    return group


@router.delete("/api/groups/{group_id}")
def delete_group(group_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    if not group:
        conn.close()
        raise HTTPException(404, "Group not found")
    conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/groups/{group_id}/members")
def list_group_members(group_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    members = conn.execute(
        "SELECT u.id, u.email, u.name, u.role FROM users u "
        "JOIN user_groups ug ON u.id = ug.user_id WHERE ug.group_id = ?",
        (group_id,),
    ).fetchall()
    conn.close()
    return [dict(m) for m in members]


@router.post("/api/groups/{group_id}/members", status_code=201)
def add_group_member(group_id: int, payload: GroupMemberAction, admin: dict = Depends(require_admin)):
    conn = get_db()
    group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    if not group:
        conn.close()
        raise HTTPException(404, "Group not found")
    from ..auth import get_user_by_id
    user = get_user_by_id(conn, payload.user_id)
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")
    try:
        conn.execute("INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)", (payload.user_id, group_id))
        conn.commit()
    except:
        pass
    conn.close()
    return {"ok": True}


@router.delete("/api/groups/{group_id}/members/{user_id}")
def remove_group_member(group_id: int, user_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    conn.execute("DELETE FROM user_groups WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/system/users")
def list_system_users(q: str = "", limit: int = 20, user: dict = Depends(get_current_user)):
    conn = get_db()
    if q:
        rows = conn.execute(
            "SELECT id, name, email FROM users WHERE name LIKE ? OR email LIKE ? ORDER BY id LIMIT ?",
            (f"%{q}%", f"%{q}%", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, email FROM users ORDER BY id LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [{"id": r["id"], "label": r["name"] or r["email"]} for r in rows]


@router.get("/api/system/groups")
def list_system_groups(q: str = "", limit: int = 20, user: dict = Depends(get_current_user)):
    conn = get_db()
    if q:
        rows = conn.execute(
            "SELECT id, name FROM groups WHERE name LIKE ? ORDER BY id LIMIT ?",
            (f"%{q}%", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name FROM groups ORDER BY id LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [{"id": r["id"], "label": r["name"]} for r in rows]
