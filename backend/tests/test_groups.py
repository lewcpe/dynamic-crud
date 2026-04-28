import pytest


def _admin_token(client):
    resp = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    return resp.json()["access_token"]


def _user_token(client):
    client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    resp = client.post("/api/auth/register", json={"email": "user@test.com", "password": "pass"})
    return resp.json()["access_token"]


def test_create_group(client):
    token = _admin_token(client)
    resp = client.post("/api/groups", json={"name": "editors", "description": "Editors"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "editors"


def test_list_groups(client):
    token = _admin_token(client)
    client.post("/api/groups", json={"name": "g1"}, headers={"Authorization": f"Bearer {token}"})
    client.post("/api/groups", json={"name": "g2"}, headers={"Authorization": f"Bearer {token}"})
    resp = client.get("/api/groups", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_group(client):
    token = _admin_token(client)
    g = client.post("/api/groups", json={"name": "g1"}, headers={"Authorization": f"Bearer {token}"}).json()
    resp = client.put(f"/api/groups/{g['id']}", json={"name": "renamed"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed"


def test_delete_group(client):
    token = _admin_token(client)
    g = client.post("/api/groups", json={"name": "g1"}, headers={"Authorization": f"Bearer {token}"}).json()
    resp = client.delete(f"/api/groups/{g['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_groups_require_admin(client):
    token = _user_token(client)
    resp = client.get("/api/groups", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_add_and_list_members(client):
    token = _admin_token(client)
    user_reg = client.post("/api/auth/register", json={"email": "member@test.com", "password": "pass"})
    user_id = user_reg.json()["user"]["id"]
    g = client.post("/api/groups", json={"name": "team"}, headers={"Authorization": f"Bearer {token}"}).json()

    client.post(f"/api/groups/{g['id']}/members", json={"user_id": user_id}, headers={"Authorization": f"Bearer {token}"})
    resp = client.get(f"/api/groups/{g['id']}/members", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()) == 1
    assert resp.json()[0]["email"] == "member@test.com"


def test_remove_member(client):
    token = _admin_token(client)
    user_reg = client.post("/api/auth/register", json={"email": "member@test.com", "password": "pass"})
    user_id = user_reg.json()["user"]["id"]
    g = client.post("/api/groups", json={"name": "team"}, headers={"Authorization": f"Bearer {token}"}).json()

    client.post(f"/api/groups/{g['id']}/members", json={"user_id": user_id}, headers={"Authorization": f"Bearer {token}"})
    client.delete(f"/api/groups/{g['id']}/members/{user_id}", headers={"Authorization": f"Bearer {token}"})
    resp = client.get(f"/api/groups/{g['id']}/members", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()) == 0


def test_duplicate_group_name(client):
    token = _admin_token(client)
    client.post("/api/groups", json={"name": "team"}, headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/api/groups", json={"name": "team"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400
