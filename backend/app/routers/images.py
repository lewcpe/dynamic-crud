import io
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File as FastAPIFile, Form
from fastapi.responses import Response
from PIL import Image

from ..database import get_db, get_items_table, ensure_table_exists
from ..auth import get_current_user
from ..permissions import check_table_permission

router = APIRouter(tags=["field-images"])

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
THUMBNAIL_SIZE = (120, 120)


def get_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(exist_ok=True)
    return UPLOAD_DIR


def create_thumbnail(image_data: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_data))
    img.thumbnail(THUMBNAIL_SIZE)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@router.post("/api/tables/{table_id}/items/{item_id}/images/{field_name}", status_code=201)
def upload_image(
    table_id: int,
    item_id: int,
    field_name: str,
    file: UploadFile = FastAPIFile(...),
    user: dict = Depends(get_current_user),
):
    conn = get_db()
    ensure_table_exists(conn, table_id)

    # Verify item exists
    items_table = get_items_table(table_id)
    row = conn.execute(f"SELECT * FROM {items_table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Item not found")

    # Verify field exists and is image type
    field = conn.execute(
        "SELECT * FROM dynamic_fields WHERE table_id = ? AND field_name = ?",
        (table_id, field_name),
    ).fetchone()
    if not field:
        conn.close()
        raise HTTPException(404, "Field not found")
    if field["field_type"] != "image":
        conn.close()
        raise HTTPException(400, "Field is not an image field")

    # Read file
    data = file.file.read()
    if len(data) > 10 * 1024 * 1024:  # 10MB limit
        conn.close()
        raise HTTPException(400, "File too large (max 10MB)")

    # Create thumbnail
    try:
        thumbnail = create_thumbnail(data)
    except Exception:
        conn.close()
        raise HTTPException(400, "Invalid image file")

    # Save original file
    ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = get_upload_dir() / filename
    file_path.write_bytes(data)

    # Delete old image for this field if exists
    old = conn.execute(
        "SELECT id, file_path FROM field_images WHERE table_id = ? AND item_id = ? AND field_name = ?",
        (table_id, item_id, field_name),
    ).fetchone()
    if old:
        old_path = Path(old["file_path"])
        if old_path.exists():
            old_path.unlink()
        conn.execute("DELETE FROM field_images WHERE id = ?", (old["id"],))

    # Save to DB
    conn.execute(
        "INSERT INTO field_images (table_id, item_id, field_name, filename, mime_type, thumbnail, file_path) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (table_id, item_id, field_name, file.filename or filename,
         file.content_type or "image/jpeg", thumbnail, str(file_path)),
    )
    image_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Update item data with image reference
    from ..helpers import item_row_to_dict, get_fields
    fields = get_fields(conn, table_id)
    item = item_row_to_dict(row, fields)
    data_dict = dict(row)
    import json
    item_data = json.loads(data_dict.get("data", "{}"))
    item_data[field_name] = image_id
    conn.execute(
        f"UPDATE {items_table} SET data = ? WHERE id = ?",
        (json.dumps(item_data), item_id),
    )

    conn.commit()
    conn.close()
    return {"id": image_id, "filename": file.filename}


@router.get("/api/field-images/{image_id}/thumbnail")
def get_thumbnail(image_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute(
        "SELECT thumbnail, mime_type FROM field_images WHERE id = ?", (image_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Image not found")
    conn.close()
    return Response(content=row["thumbnail"], media_type="image/jpeg")


@router.get("/api/field-images/{image_id}/file")
def get_image_file(image_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute(
        "SELECT file_path, filename, mime_type FROM field_images WHERE id = ?", (image_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Image not found")

    file_path = Path(row["file_path"])
    if not file_path.exists():
        conn.close()
        raise HTTPException(404, "File not found on disk")

    conn.close()
    return Response(
        content=file_path.read_bytes(),
        media_type=row["mime_type"],
        headers={"Content-Disposition": f'attachment; filename="{row["filename"]}"'},
    )


@router.delete("/api/field-images/{image_id}")
def delete_image(image_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM field_images WHERE id = ?", (image_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Image not found")

    file_path = Path(row["file_path"])
    if file_path.exists():
        file_path.unlink()

    # Clear item data reference
    items_table = get_items_table(row["table_id"])
    item_row = conn.execute(f"SELECT data FROM {items_table} WHERE id = ?", (row["item_id"],)).fetchone()
    if item_row:
        import json
        item_data = json.loads(item_row["data"] or "{}")
        if item_data.get(row["field_name"]) == image_id:
            item_data[row["field_name"]] = None
            conn.execute(
                f"UPDATE {items_table} SET data = ? WHERE id = ?",
                (json.dumps(item_data), row["item_id"]),
            )

    conn.execute("DELETE FROM field_images WHERE id = ?", (image_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/tables/{table_id}/items/{item_id}/images")
def list_images(table_id: int, item_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    ensure_table_exists(conn, table_id)
    rows = conn.execute(
        "SELECT id, field_name, filename, mime_type, created_at FROM field_images "
        "WHERE table_id = ? AND item_id = ?",
        (table_id, item_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
