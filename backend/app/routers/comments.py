from fastapi import APIRouter, HTTPException, Depends
from ..database import get_db, ensure_table_exists, get_items_table
from ..models import CommentCreate, CommentUpdate
from ..auth import get_current_user
from ..permissions import check_table_permission

router = APIRouter(tags=["comments"])


@router.get("/api/tables/{table_id}/items/{item_id}/comments")
def list_comments(table_id: int, item_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    check_table_permission(conn, table_id, "view", user)
    comments = conn.execute(
        "SELECT c.*, u.name as user_name, u.email as user_email FROM comments c "
        "JOIN users u ON c.user_id = u.id "
        "WHERE c.table_id = ? AND c.item_id = ? ORDER BY c.created_at",
        (table_id, item_id),
    ).fetchall()
    conn.close()
    return [dict(c) for c in comments]


@router.post("/api/tables/{table_id}/items/{item_id}/comments", status_code=201)
def create_comment(table_id: int, item_id: int, payload: CommentCreate, user: dict = Depends(get_current_user)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    items_table = get_items_table(table_id)
    row = conn.execute(f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    if not check_table_permission(conn, table_id, "update", user, dict(row)):
        conn.close()
        raise HTTPException(403, "Not authorized to comment on this item")

    conn.execute(
        "INSERT INTO comments (table_id, item_id, user_id, content) VALUES (?, ?, ?, ?)",
        (table_id, item_id, user["id"], payload.content),
    )
    comment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    comment = dict(conn.execute(
        "SELECT c.*, u.name as user_name, u.email as user_email FROM comments c "
        "JOIN users u ON c.user_id = u.id WHERE c.id = ?", (comment_id,)
    ).fetchone())
    conn.close()
    return comment


@router.put("/api/comments/{comment_id}")
def update_comment(comment_id: int, payload: CommentUpdate, user: dict = Depends(get_current_user)):
    conn = get_db()
    comment = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
    if not comment:
        conn.close()
        raise HTTPException(404, "Comment not found")
    if comment["user_id"] != user["id"] and user["role"] != "admin":
        conn.close()
        raise HTTPException(403, "Can only edit your own comments")
    conn.execute(
        "UPDATE comments SET content = ?, updated_at = datetime('now') WHERE id = ?",
        (payload.content, comment_id),
    )
    conn.commit()
    comment = dict(conn.execute(
        "SELECT c.*, u.name as user_name, u.email as user_email FROM comments c "
        "JOIN users u ON c.user_id = u.id WHERE c.id = ?", (comment_id,)
    ).fetchone())
    conn.close()
    return comment


@router.delete("/api/comments/{comment_id}")
def delete_comment(comment_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    comment = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
    if not comment:
        conn.close()
        raise HTTPException(404, "Comment not found")
    if comment["user_id"] != user["id"] and user["role"] != "admin":
        conn.close()
        raise HTTPException(403, "Can only delete your own comments")
    conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
