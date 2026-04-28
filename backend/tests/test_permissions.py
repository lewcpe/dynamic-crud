import pytest


def _setup(client):
    admin = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    user = client.post("/api/auth/register", json={"email": "user@test.com", "password": "pass"})
    admin_token = admin.json()["access_token"]
    user_token = user.json()["access_token"]
    table = client.post("/api/tables", json={"name": "tasks"}, headers={"Authorization": f"Bearer {admin_token}"})
    table_id = table.json()["id"]
    return admin_token, user_token, table_id


def test_create_permission(client):
    admin_token, user_token, table_id = _setup(client)
    resp = client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": "", "view_rule": ""},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["target_type"] == "role"


def test_list_permissions(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": ""},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/permissions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert len(resp.json()) == 1


def test_update_permission(client):
    admin_token, user_token, table_id = _setup(client)
    perm = client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": ""},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    resp = client.put(
        f"/api/tables/{table_id}/permissions/{perm['id']}",
        json={"view_rule": "@request.auth.id != \"\""},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["view_rule"] == '@request.auth.id != ""'


def test_delete_permission(client):
    admin_token, user_token, table_id = _setup(client)
    perm = client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": ""},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    resp = client.delete(
        f"/api/tables/{table_id}/permissions/{perm['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200


def test_permissions_require_admin(client):
    admin_token, user_token, table_id = _setup(client)
    resp = client.get(
        f"/api/tables/{table_id}/permissions",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


def test_locked_rule_blocks_non_admin(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": None, "view_rule": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "test", "data": {}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


def test_empty_rule_allows_all(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": "", "view_rule": ""},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "test", "data": {}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_auth_rule_requires_login(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": '@request.auth.id != ""'},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "test", "data": {}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(f"/api/tables/{table_id}/items")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_my_permissions(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": "", "view_rule": "", "create_rule": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/my-permissions",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["list"] is True
    assert resp.json()["view"] is True
    assert resp.json()["create"] is False


def test_no_permissions_allows_all(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "test", "data": {}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
