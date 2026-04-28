import pytest


def _setup(client):
    admin = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    user = client.post("/api/auth/register", json={"email": "user@test.com", "password": "pass"})
    admin_token = admin.json()["access_token"]
    user_token = user.json()["access_token"]
    table = client.post("/api/tables", json={"name": "tasks"}, headers={"Authorization": f"Bearer {admin_token}"})
    table_id = table.json()["id"]
    client.post(
        f"/api/tables/{table_id}/fields",
        json={"field_name": "status", "field_type": "text", "field_label": "Status"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return admin_token, user_token, table_id


def test_field_value_filter(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "a", "data": {"status": "active"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "b", "data": {"status": "draft"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": 'status = "active"'},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["fields"]["status"] == "active"


def test_owner_filter(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "mine", "data": {"status": "active"}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "other", "data": {"status": "active"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": 'owner = "mine"'},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["owner"] == "mine"


def test_compound_rule(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "a", "data": {"status": "active"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "b", "data": {"status": "draft"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "c", "data": {"status": "active"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": 'status = "active" && owner = "a"'},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["owner"] == "a"


def test_or_rule(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "a", "data": {"status": "active"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "b", "data": {"status": "draft"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "c", "data": {"status": "archived"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": 'status = "active" || status = "draft"'},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_admin_bypasses_row_filter(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "a", "data": {"status": "active"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "b", "data": {"status": "draft"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "list_rule": 'status = "active"'},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_no_permissions_allows_all(client):
    admin_token, user_token, table_id = _setup(client)
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "a", "data": {"status": "active"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "b", "data": {"status": "draft"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/tables/{table_id}/items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_update_rule_row_level(client):
    admin_token, user_token, table_id = _setup(client)
    item1 = client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "a", "data": {"status": "active"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    item2 = client.post(
        f"/api/tables/{table_id}/items",
        json={"owner": "b", "data": {"status": "draft"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    client.post(
        f"/api/tables/{table_id}/permissions",
        json={"target_type": "role", "target_role": "user", "update_rule": 'status = "active"'},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.put(
        f"/api/tables/{table_id}/items/{item1['id']}",
        json={"data": {"status": "updated"}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200

    resp = client.put(
        f"/api/tables/{table_id}/items/{item2['id']}",
        json={"data": {"status": "updated"}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403
