import os
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Depends
import bcrypt
from jose import jwt, JWTError
from .database import get_db

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_user_by_id(conn, user_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(conn, email: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_groups(conn, user_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT group_id FROM user_groups WHERE user_id = ?", (user_id,)
    ).fetchall()
    return [r["group_id"] for r in rows]


def get_manager_chain(conn, user_id: int, levels: int = 0) -> list[int]:
    """Get manager chain for a user.
    
    Args:
        conn: database connection
        user_id: the user to get managers for
        levels: 0 = all levels (recursive), 1 = direct manager only, 2 = two levels, etc.
    
    Returns:
        List of manager user IDs (from direct manager up to top)
    """
    chain = []
    current_id = user_id
    depth = 0
    while True:
        if levels > 0 and depth >= levels:
            break
        row = conn.execute(
            "SELECT manager_id FROM users WHERE id = ?", (current_id,)
        ).fetchone()
        if not row or row["manager_id"] is None:
            break
        manager_id = row["manager_id"]
        # Prevent infinite loops
        if manager_id in chain or manager_id == user_id:
            break
        chain.append(manager_id)
        current_id = manager_id
        depth += 1
    return chain


def get_current_user_optional(request: Request) -> dict | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None
    conn = get_db()
    user = get_user_by_id(conn, int(payload["sub"]))
    conn.close()
    return user


def get_current_user(request: Request) -> dict:
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required")
    return user
