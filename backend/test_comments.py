import pytest


def _setup(client):
    admin = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    user = client.post("/api/auth/register", json={"email": "user@test.com", "password": "pass"})
    admin_token = admin.json()["access_token"]
    user_token = user.json()["access_token"]
    table = client.post("/api/tables", json={"name": "tasks"}, headers={"Authorization": f"Bearer {admin_token}"})
    table_id = table.json()["id"]
    item = client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "task1", "data": {}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    item_id = item.json()["id"]
    return admin_token, user_token, table_id, item_id


def test_create_comment(client):
    admin_token, user_token, table_id, item_id = _setup(client)
    resp = client.post(
        f"/api/tables/{table_id}/items/{item_id}/comments",
        json={"content": "This is a comment"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["content"] == "This is a comment"
    assert resp.json()["user_name"] == "user"


def test_list_comments(client):
    admin_token, user_token, table_id, item_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/items/{item_id}/comments",
        json={"content": "Comment 1"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items/{item_id}/comments",
        json={"content": "Comment 2"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items/{item_id}/comments",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_own_comment(client):
    admin_token, user_token, table_id, item_id = _setup(client)
    comment = client.post(
        f"/api/tables/{table_id}/items/{item_id}/comments",
        json={"content": "Original"},
        headers={"Authorization": f"Bearer {user_token}"},
    ).json()
    resp = client.put(
        f"/api/comments/{comment['id']}",
        json={"content": "Updated"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Updated"


def test_cannot_update_others_comment(client):
    admin_token, user_token, table_id, item_id = _setup(client)
    comment = client.post(
        f"/api/tables/{table_id}/items/{item_id}/comments",
        json={"content": "Admin comment"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    resp = client.put(
        f"/api/comments/{comment['id']}",
        json={"content": "Hacked"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


def test_admin_can_update_any_comment(client):
    admin_token, user_token, table_id, item_id = _setup(client)
    comment = client.post(
        f"/api/tables/{table_id}/items/{item_id}/comments",
        json={"content": "User comment"},
        headers={"Authorization": f"Bearer {user_token}"},
    ).json()
    resp = client.put(
        f"/api/comments/{comment['id']}",
        json={"content": "Admin edit"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Admin edit"


def test_delete_own_comment(client):
    admin_token, user_token, table_id, item_id = _setup(client)
    comment = client.post(
        f"/api/tables/{table_id}/items/{item_id}/comments",
        json={"content": "To delete"},
        headers={"Authorization": f"Bearer {user_token}"},
    ).json()
    resp = client.delete(
        f"/api/comments/{comment['id']}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200


def test_comment_requires_auth(client):
    admin_token, user_token, table_id, item_id = _setup(client)
    resp = client.post(
        f"/api/tables/{table_id}/items/{item_id}/comments",
        json={"content": "Anon"},
    )
    assert resp.status_code == 401


def test_comment_requires_write_permission(client):
    admin_token, user_token, table_id, item_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "update_rule": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.post(
        f"/api/tables/{table_id}/items/{item_id}/comments",
        json={"content": "Blocked"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403
