import pytest
import io


def _setup(client):
    admin = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    admin_token = admin.json()["access_token"]
    table = client.post("/api/tables", json={"name": "docs"}, headers={"Authorization": f"Bearer {admin_token}"})
    table_id = table.json()["id"]
    item = client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "doc1", "data": {}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    item_id = item.json()["id"]
    return admin_token, table_id, item_id


def test_upload_file(client):
    token, table_id, item_id = _setup(client)
    resp = client.post(
        f"/api/tables/{table_id}/items/{item_id}/files",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        data={"field_name": "attachment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["filename"] == "test.txt"
    assert data["mime_type"] == "text/plain"
    assert data["size"] == 11


def test_list_files(client):
    token, table_id, item_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/items/{item_id}/files",
        files={"file": ("a.txt", b"aaa", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items/{item_id}/files",
        files={"file": ("b.txt", b"bbb", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items/{item_id}/files",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_download_file(client):
    token, table_id, item_id = _setup(client)
    upload = client.post(
        f"/api/tables/{table_id}/items/{item_id}/files",
        files={"file": ("data.bin", b"\x00\x01\x02", "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )
    file_id = upload.json()["id"]
    resp = client.get(f"/api/files/{file_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.content == b"\x00\x01\x02"


def test_delete_file(client):
    token, table_id, item_id = _setup(client)
    upload = client.post(
        f"/api/tables/{table_id}/items/{item_id}/files",
        files={"file": ("tmp.txt", b"tmp", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    file_id = upload.json()["id"]
    resp = client.delete(f"/api/files/{file_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_upload_requires_auth(client):
    _, table_id, item_id = _setup(client)
    resp = client.post(
        f"/api/tables/{table_id}/items/{item_id}/files",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 401
