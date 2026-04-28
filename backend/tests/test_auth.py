import pytest


def test_register_first_user_is_admin(client):
    resp = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass123", "name": "Admin"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["access_token"]
    assert data["user"]["role"] == "admin"
    assert data["user"]["email"] == "admin@test.com"


def test_register_second_user_is_user(client):
    client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass123"})
    resp = client.post("/api/auth/register", json={"email": "user@test.com", "password": "pass123"})
    assert resp.status_code == 201
    assert resp.json()["user"]["role"] == "user"


def test_register_duplicate_email(client):
    client.post("/api/auth/register", json={"email": "a@test.com", "password": "pass"})
    resp = client.post("/api/auth/register", json={"email": "a@test.com", "password": "pass"})
    assert resp.status_code == 400


def test_login_success(client):
    client.post("/api/auth/register", json={"email": "a@test.com", "password": "mypass"})
    resp = client.post("/api/auth/login", json={"email": "a@test.com", "password": "mypass"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"email": "a@test.com", "password": "mypass"})
    resp = client.post("/api/auth/login", json={"email": "a@test.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/api/auth/login", json={"email": "no@test.com", "password": "x"})
    assert resp.status_code == 401


def test_get_me(client):
    reg = client.post("/api/auth/register", json={"email": "a@test.com", "password": "pass", "name": "Alice"})
    token = reg.json()["access_token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@test.com"
    assert resp.json()["name"] == "Alice"


def test_get_me_no_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_list_users_requires_admin(client):
    client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    reg_user = client.post("/api/auth/register", json={"email": "user@test.com", "password": "pass"})
    user_token = reg_user.json()["access_token"]

    resp = client.get("/api/users", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 403


def test_list_users_as_admin(client):
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    admin_token = reg.json()["access_token"]

    resp = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_update_user_role(client):
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    admin_token = reg.json()["access_token"]
    reg2 = client.post("/api/auth/register", json={"email": "user@test.com", "password": "pass"})
    user_id = reg2.json()["user"]["id"]

    resp = client.put(
        f"/api/users/{user_id}",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_make_and_remove_admin(client):
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    admin_token = reg.json()["access_token"]
    reg2 = client.post("/api/auth/register", json={"email": "user@test.com", "password": "pass"})
    user_id = reg2.json()["user"]["id"]

    client.post(f"/api/users/{user_id}/make-admin", headers={"Authorization": f"Bearer {admin_token}"})
    resp = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
    admins = [u for u in resp.json() if u["role"] == "admin"]
    assert len(admins) == 2

    client.post(f"/api/users/{user_id}/remove-admin", headers={"Authorization": f"Bearer {admin_token}"})
    resp = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
    admins = [u for u in resp.json() if u["role"] == "admin"]
    assert len(admins) == 1


def test_cannot_remove_last_admin(client):
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    admin_token = reg.json()["access_token"]
    admin_id = reg.json()["user"]["id"]

    resp = client.post(
        f"/api/users/{admin_id}/remove-admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


def test_delete_user(client):
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    admin_token = reg.json()["access_token"]
    reg2 = client.post("/api/auth/register", json={"email": "user@test.com", "password": "pass"})
    user_id = reg2.json()["user"]["id"]

    resp = client.delete(f"/api/users/{user_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
