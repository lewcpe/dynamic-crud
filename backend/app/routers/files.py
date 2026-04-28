from fastapi import APIRouter, HTTPException, Depends, UploadFile, File as FastAPIFile, Form
from fastapi.responses import Response
from ..database import get_db, ensure_table_exists, get_items_table
from ..auth import get_current_user
from ..permissions import check_table_permission

router = APIRouter(tags=["files"])


@router.post("/api/tables/{table_id}/items/{item_id}/files", status_code=201)
def upload_file(
    table_id: int,
    item_id: int,
    file: UploadFile = FastAPIFile(...),
    field_name: str = Form(""),
    user: dict = Depends(get_current_user),
):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    items_table = get_items_table(table_id)
    row = conn.execute(f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    check_table_permission(conn, table_id, "update", user, dict(row))

    data = file.file.read()
    conn.execute(
        "INSERT INTO files (table_id, item_id, field_name, filename, mime_type, size, data, uploader_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (table_id, item_id, field_name, file.filename, file.content_type or "application/octet-stream",
         len(data), data, user["id"]),
    )
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    f = dict(conn.execute(
        "SELECT id, table_id, item_id, field_name, filename, mime_type, size, uploader_id, created_at FROM files WHERE id = ?",
        (file_id,),
    ).fetchone())
    conn.close()
    return f


@router.get("/api/tables/{table_id}/items/{item_id}/files")
def list_files(table_id: int, item_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    check_table_permission(conn, table_id, "view", user)
    files = conn.execute(
        "SELECT id, table_id, item_id, field_name, filename, mime_type, size, uploader_id, created_at "
        "FROM files WHERE table_id = ? AND item_id = ?",
        (table_id, item_id),
    ).fetchall()
    conn.close()
    return [dict(f) for f in files]


@router.get("/api/files/{file_id}")
def download_file(file_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    f = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if not f:
        conn.close()
        raise HTTPException(404, "File not found")
    check_table_permission(conn, f["table_id"], "view", user)
    conn.close()
    return Response(
        content=f["data"],
        media_type=f["mime_type"],
        headers={"Content-Disposition": f'attachment; filename="{f["filename"]}"'},
    )


@router.delete("/api/files/{file_id}")
def delete_file(file_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    f = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if not f:
        conn.close()
        raise HTTPException(404, "File not found")
    check_table_permission(conn, f["table_id"], "update", user)
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
