from fastapi import APIRouter, HTTPException, Depends
from ..database import get_db
from ..models import RegisterRequest, LoginRequest, UserUpdate
from ..auth import hash_password, verify_password, create_access_token, get_user_by_email, get_user_by_id, get_current_user, require_admin

router = APIRouter(tags=["auth"])


@router.post("/api/auth/register", status_code=201)
def register(payload: RegisterRequest):
    conn = get_db()
    existing = get_user_by_email(conn, payload.email)
    if existing:
        conn.close()
        raise HTTPException(400, "Email already registered")

    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    role = "admin" if user_count == 0 else "user"

    conn.execute(
        "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)",
        (payload.email, hash_password(payload.password), payload.name or payload.email.split("@")[0], role),
    )
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    user = get_user_by_id(conn, user_id)
    conn.close()

    token = create_access_token({"sub": str(user_id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/api/auth/login")
def login(payload: LoginRequest):
    conn = get_db()
    user = get_user_by_email(conn, payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        conn.close()
        raise HTTPException(401, "Invalid email or password")
    conn.close()

    token = create_access_token({"sub": str(user["id"])})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/api/auth/me")
def get_me(user: dict = Depends(get_current_user)):
    conn = get_db()
    groups = conn.execute(
        "SELECT g.* FROM groups g JOIN user_groups ug ON g.id = ug.group_id WHERE ug.user_id = ?",
        (user["id"],),
    ).fetchall()
    conn.close()
    user["groups"] = [dict(g) for g in groups]
    return user


@router.get("/api/users")
def list_users(admin: dict = Depends(require_admin)):
    conn = get_db()
    users = conn.execute("SELECT id, email, name, role, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(u) for u in users]


@router.put("/api/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate, admin: dict = Depends(require_admin)):
    conn = get_db()
    user = get_user_by_id(conn, user_id)
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")

    if payload.name is not None:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (payload.name, user_id))
    if payload.role is not None:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (payload.role, user_id))
    conn.commit()
    user = get_user_by_id(conn, user_id)
    conn.close()
    return user


@router.delete("/api/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    user = get_user_by_id(conn, user_id)
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/api/users/{user_id}/make-admin")
def make_admin(user_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    user = get_user_by_id(conn, user_id)
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")
    conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/api/users/{user_id}/remove-admin")
def remove_admin(user_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    user = get_user_by_id(conn, user_id)
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")
    if user["role"] == "admin":
        admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
        if admin_count <= 1:
            conn.close()
            raise HTTPException(400, "Cannot remove the last admin")
    conn.execute("UPDATE users SET role = 'user' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
