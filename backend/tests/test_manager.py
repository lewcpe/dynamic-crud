"""Tests for manager feature."""
import pytest


def _setup(client):
    admin = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    user1 = client.post("/api/auth/register", json={"email": "alice@test.com", "password": "pass", "name": "Alice"})
    user2 = client.post("/api/auth/register", json={"email": "bob@test.com", "password": "pass", "name": "Bob"})
    user3 = client.post("/api/auth/register", json={"email": "charlie@test.com", "password": "pass", "name": "Charlie"})
    return {
        "admin": admin.json(),
        "alice": user1.json(),
        "bob": user2.json(),
        "charlie": user3.json(),
    }


def test_set_manager(client):
    users = _setup(client)
    admin_token = users["admin"]["access_token"]
    alice_id = users["alice"]["user"]["id"]
    bob_id = users["bob"]["user"]["id"]

    resp = client.put(
        f"/api/users/{alice_id}/manager",
        json={"manager_id": bob_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["manager_id"] == bob_id


def test_remove_manager(client):
    users = _setup(client)
    admin_token = users["admin"]["access_token"]
    alice_id = users["alice"]["user"]["id"]
    bob_id = users["bob"]["user"]["id"]

    client.put(
        f"/api/users/{alice_id}/manager",
        json={"manager_id": bob_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.put(
        f"/api/users/{alice_id}/manager",
        json={"manager_id": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["manager_id"] is None


def test_cannot_set_self_as_manager(client):
    users = _setup(client)
    admin_token = users["admin"]["access_token"]
    alice_id = users["alice"]["user"]["id"]

    resp = client.put(
        f"/api/users/{alice_id}/manager",
        json={"manager_id": alice_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


def test_manager_chain(client):
    users = _setup(client)
    token = users["alice"]["access_token"]
    admin_token = users["admin"]["access_token"]
    alice_id = users["alice"]["user"]["id"]
    bob_id = users["bob"]["user"]["id"]
    charlie_id = users["charlie"]["user"]["id"]

    # Chain: alice -> bob -> charlie
    client.put(f"/api/users/{alice_id}/manager", json={"manager_id": bob_id}, headers={"Authorization": f"Bearer {admin_token}"})
    client.put(f"/api/users/{bob_id}/manager", json={"manager_id": charlie_id}, headers={"Authorization": f"Bearer {admin_token}"})

    resp = client.get(f"/api/users/{alice_id}/manager-chain", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    chain = resp.json()
    assert len(chain["managers"]) == 2
    assert chain["managers"][0]["id"] == bob_id
    assert chain["managers"][1]["id"] == charlie_id


def test_manager_rule_direct(client):
    """Test rule: allowed_users.id ?= @request.auth.manager.id"""
    users = _setup(client)
    admin_token = users["admin"]["access_token"]
    alice_id = users["alice"]["user"]["id"]
    bob_id = users["bob"]["user"]["id"]

    # Set bob as alice's manager
    client.put(f"/api/users/{alice_id}/manager", json={"manager_id": bob_id}, headers={"Authorization": f"Bearer {admin_token}"})

    # Create table with relationship to users
    table = client.post("/api/tables", json={"name": "tasks", "represent": "{title}"}, headers={"Authorization": f"Bearer {admin_token}"}).json()
    client.post(f"/api/tables/{table['id']}/fields", json={"field_name": "title", "field_type": "text", "field_label": "Title"}, headers={"Authorization": f"Bearer {admin_token}"})

    # Create relationship to users (1-n: task has one assigned user)
    rel = client.post(f"/api/tables/{table['id']}/relationships", json={
        "rel_name": "assigned_to", "rel_label": "Assigned To", "rel_type": "1-n", "to_system_table": "users"
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()

    # Create task assigned to bob
    task = client.post(f"/api/tables/{table['id']}/items", json={"owner": "admin", "data": {"title": "Task 1"}}, headers={"Authorization": f"Bearer {admin_token}"}).json()
    client.post(f"/api/tables/{table['id']}/relationships/{rel['id']}/link", json={"item_id": task["id"], "target_ids": [bob_id]}, headers={"Authorization": f"Bearer {admin_token}"})

    # Set permission: bob can view if assigned_to.id = @request.auth.id
    client.post(f"/api/tables/{table['id']}/permissions", json={
        "target_type": "role", "target_role": "user",
        "view_rule": 'assigned_to.id ?= @request.auth.id'
    }, headers={"Authorization": f"Bearer {admin_token}"})

    # Bob can view (he's assigned)
    bob_token = users["bob"]["access_token"]
    resp = client.get(f"/api/tables/{table['id']}/items/{task['id']}", headers={"Authorization": f"Bearer {bob_token}"})
    assert resp.status_code == 200

    # Charlie cannot view (not assigned, not manager)
    charlie_token = users["charlie"]["access_token"]
    resp = client.get(f"/api/tables/{table['id']}/items/{task['id']}", headers={"Authorization": f"Bearer {charlie_token}"})
    assert resp.status_code == 403

    # Alice can view (bob is her manager, and bob is assigned)
    # This uses @request.auth.manager.id rule - let's test that separately
    alice_token = users["alice"]["access_token"]
    resp = client.get(f"/api/tables/{table['id']}/items/{task['id']}", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 403  # alice is not assigned directly


def test_manager_rule_with_manager_syntax(client):
    """Test rule: assigned_to.id ?= @request.auth.manager.id"""
    users = _setup(client)
    admin_token = users["admin"]["access_token"]
    alice_id = users["alice"]["user"]["id"]
    bob_id = users["bob"]["user"]["id"]

    # Set bob as alice's manager
    client.put(f"/api/users/{alice_id}/manager", json={"manager_id": bob_id}, headers={"Authorization": f"Bearer {admin_token}"})

    # Create table
    table = client.post("/api/tables", json={"name": "tasks", "represent": "{title}"}, headers={"Authorization": f"Bearer {admin_token}"}).json()
    client.post(f"/api/tables/{table['id']}/fields", json={"field_name": "title", "field_type": "text", "field_label": "Title"}, headers={"Authorization": f"Bearer {admin_token}"})

    # Create relationship to users
    rel = client.post(f"/api/tables/{table['id']}/relationships", json={
        "rel_name": "assigned_to", "rel_label": "Assigned To", "rel_type": "1-n", "to_system_table": "users"
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()

    # Create task assigned to bob
    task = client.post(f"/api/tables/{table['id']}/items", json={"owner": "admin", "data": {"title": "Task 1"}}, headers={"Authorization": f"Bearer {admin_token}"}).json()
    client.post(f"/api/tables/{table['id']}/relationships/{rel['id']}/link", json={"item_id": task["id"], "target_ids": [bob_id]}, headers={"Authorization": f"Bearer {admin_token}"})

    # Permission: can view if assigned_to matches user's manager
    client.post(f"/api/tables/{table['id']}/permissions", json={
        "target_type": "role", "target_role": "user",
        "view_rule": 'assigned_to.id ?= @request.auth.manager.id'
    }, headers={"Authorization": f"Bearer {admin_token}"})

    # Alice can view (her manager bob is assigned)
    alice_token = users["alice"]["access_token"]
    resp = client.get(f"/api/tables/{table['id']}/items/{task['id']}", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200

    # Bob cannot view directly (the rule checks manager, not self)
    bob_token = users["bob"]["access_token"]
    resp = client.get(f"/api/tables/{table['id']}/items/{task['id']}", headers={"Authorization": f"Bearer {bob_token}"})
    assert resp.status_code == 403


def test_managers_rule_all_levels(client):
    """Test rule: assigned_to.id ?= @request.auth.managers.id (all levels)"""
    users = _setup(client)
    admin_token = users["admin"]["access_token"]
    alice_id = users["alice"]["user"]["id"]
    bob_id = users["bob"]["user"]["id"]
    charlie_id = users["charlie"]["user"]["id"]

    # Chain: alice -> bob -> charlie
    client.put(f"/api/users/{alice_id}/manager", json={"manager_id": bob_id}, headers={"Authorization": f"Bearer {admin_token}"})
    client.put(f"/api/users/{bob_id}/manager", json={"manager_id": charlie_id}, headers={"Authorization": f"Bearer {admin_token}"})

    # Create table
    table = client.post("/api/tables", json={"name": "tasks", "represent": "{title}"}, headers={"Authorization": f"Bearer {admin_token}"}).json()
    client.post(f"/api/tables/{table['id']}/fields", json={"field_name": "title", "field_type": "text", "field_label": "Title"}, headers={"Authorization": f"Bearer {admin_token}"})

    # Create relationship to users
    rel = client.post(f"/api/tables/{table['id']}/relationships", json={
        "rel_name": "assigned_to", "rel_label": "Assigned To", "rel_type": "1-n", "to_system_table": "users"
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()

    # Create task assigned to charlie (top manager)
    task = client.post(f"/api/tables/{table['id']}/items", json={"owner": "admin", "data": {"title": "Task 1"}}, headers={"Authorization": f"Bearer {admin_token}"}).json()
    client.post(f"/api/tables/{table['id']}/relationships/{rel['id']}/link", json={"item_id": task["id"], "target_ids": [charlie_id]}, headers={"Authorization": f"Bearer {admin_token}"})

    # Permission: can view if any manager in chain is assigned
    client.post(f"/api/tables/{table['id']}/permissions", json={
        "target_type": "role", "target_role": "user",
        "view_rule": 'assigned_to.id ?= @request.auth.managers.id'
    }, headers={"Authorization": f"Bearer {admin_token}"})

    # Alice can view (charlie is in her manager chain and is assigned)
    alice_token = users["alice"]["access_token"]
    resp = client.get(f"/api/tables/{table['id']}/items/{task['id']}", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200

    # Bob can view (charlie is his direct manager and is assigned)
    bob_token = users["bob"]["access_token"]
    resp = client.get(f"/api/tables/{table['id']}/items/{task['id']}", headers={"Authorization": f"Bearer {bob_token}"})
    assert resp.status_code == 200

    # Charlie cannot view (he has no manager, so managers list is empty)
    charlie_token = users["charlie"]["access_token"]
    resp = client.get(f"/api/tables/{table['id']}/items/{task['id']}", headers={"Authorization": f"Bearer {charlie_token}"})
    assert resp.status_code == 403
