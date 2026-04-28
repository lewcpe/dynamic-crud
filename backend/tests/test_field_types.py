"""Tests for multiline and image field types."""
import io
import pytest


def _setup(client):
    admin = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    token = admin.json()["access_token"]
    table = client.post("/api/tables", json={"name": "docs", "represent": "{title}"}, headers={"Authorization": f"Bearer {token}"}).json()
    return token, table["id"]


def test_create_multiline_field(client):
    token, tid = _setup(client)
    resp = client.post(
        f"/api/tables/{tid}/fields",
        json={"field_name": "description", "field_type": "multiline", "field_label": "Description"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["field_type"] == "multiline"


def test_create_image_field(client):
    token, tid = _setup(client)
    resp = client.post(
        f"/api/tables/{tid}/fields",
        json={"field_name": "photo", "field_type": "image", "field_label": "Photo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["field_type"] == "image"


def test_multiline_field_crud(client):
    token, tid = _setup(client)
    client.post(
        f"/api/tables/{tid}/fields",
        json={"field_name": "body", "field_type": "multiline", "field_label": "Body"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Create item with multiline content
    content = "Line 1\nLine 2\nLine 3"
    item = client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "test", "data": {"body": content}},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert item["fields"]["body"] == content

    # Read back
    fetched = client.get(
        f"/api/tables/{tid}/items/{item['id']}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert fetched["fields"]["body"] == content


def test_image_upload_and_thumbnail(client):
    token, tid = _setup(client)
    client.post(
        f"/api/tables/{tid}/fields",
        json={"field_name": "photo", "field_type": "image", "field_label": "Photo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Create item
    item = client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "test", "data": {}},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    # Create a simple test image (1x1 pixel JPEG)
    from PIL import Image
    img = Image.new("RGB", (200, 200), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    # Upload image
    resp = client.post(
        f"/api/tables/{tid}/items/{item['id']}/images/photo",
        files={"file": ("test.jpg", image_bytes, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    image_id = resp.json()["id"]

    # Get thumbnail
    resp = client.get(
        f"/api/field-images/{image_id}/thumbnail",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"

    # Verify item has image reference
    fetched = client.get(
        f"/api/tables/{tid}/items/{item['id']}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert fetched["fields"]["photo"] == image_id


def test_image_delete(client):
    token, tid = _setup(client)
    client.post(
        f"/api/tables/{tid}/fields",
        json={"field_name": "photo", "field_type": "image", "field_label": "Photo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    item = client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "test", "data": {}},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    from PIL import Image
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    resp = client.post(
        f"/api/tables/{tid}/items/{item['id']}/images/photo",
        files={"file": ("test.jpg", image_bytes, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    image_id = resp.json()["id"]

    # Delete
    resp = client.delete(
        f"/api/field-images/{image_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Verify item field is cleared
    fetched = client.get(
        f"/api/tables/{tid}/items/{item['id']}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert fetched["fields"]["photo"] is None


def test_image_list(client):
    token, tid = _setup(client)
    client.post(
        f"/api/tables/{tid}/fields",
        json={"field_name": "photo", "field_type": "image", "field_label": "Photo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    item = client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "test", "data": {}},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    from PIL import Image
    img = Image.new("RGB", (50, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    client.post(
        f"/api/tables/{tid}/items/{item['id']}/images/photo",
        files={"file": ("test.jpg", buf.getvalue(), "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = client.get(
        f"/api/tables/{tid}/items/{item['id']}/images",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["field_name"] == "photo"
