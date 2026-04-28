def test_list_tables(client, default_table):
    resp = client.get("/api/tables")
    assert resp.status_code == 200
    tables = resp.json()
    assert len(tables) >= 1
    assert any(t["name"] == "default" for t in tables)


def test_create_table(client):
    resp = client.post("/api/tables", json={"name": "contacts", "label": "Contacts"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "contacts"
    assert data["label"] == "Contacts"


def test_create_duplicate_table(client, default_table):
    resp = client.post("/api/tables", json={"name": "default", "label": "Dup"})
    assert resp.status_code == 400


def test_update_table(client, default_table):
    tid = default_table
    resp = client.put(f"/api/tables/{tid}", json={"label": "Updated Label"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "Updated Label"


def test_delete_table(client):
    created = client.post("/api/tables", json={"name": "tmp"}).json()
    resp = client.delete(f"/api/tables/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    remaining = [t for t in client.get("/api/tables").json() if t["id"] == created["id"]]
    assert len(remaining) == 0


def test_fields_isolated_between_tables(client):
    r1 = client.post("/api/tables", json={"name": "t1"})
    r2 = client.post("/api/tables", json={"name": "t2"})
    t1, t2 = r1.json()["id"], r2.json()["id"]

    client.post(
        f"/api/tables/{t1}/fields",
        json={"field_name": "x", "field_type": "text", "field_label": "X"},
    )
    assert len(client.get(f"/api/tables/{t1}/fields").json()) == 1
    assert len(client.get(f"/api/tables/{t2}/fields").json()) == 0


def test_items_isolated_between_tables(client):
    r1 = client.post("/api/tables", json={"name": "t1"})
    r2 = client.post("/api/tables", json={"name": "t2"})
    t1, t2 = r1.json()["id"], r2.json()["id"]

    client.post(f"/api/tables/{t1}/items", json={"owner": "a", "data": {}})
    client.post(f"/api/tables/{t1}/items", json={"owner": "b", "data": {}})
    client.post(f"/api/tables/{t2}/items", json={"owner": "c", "data": {}})

    d1 = client.get(f"/api/tables/{t1}/items").json()
    d2 = client.get(f"/api/tables/{t2}/items").json()
    assert d1["total"] == 2
    assert d2["total"] == 1
