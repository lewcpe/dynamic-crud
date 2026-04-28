def test_create_field(client):
    resp = client.post("/api/fields", json={"field_name": "status", "field_type": "text", "field_label": "Status"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["field_name"] == "status"
    assert data["field_type"] == "text"
    assert data["field_label"] == "Status"


def test_list_fields(client_with_fields):
    resp = client_with_fields.get("/api/fields")
    assert resp.status_code == 200
    fields = resp.json()
    assert len(fields) == 2
    names = [f["field_name"] for f in fields]
    assert "name" in names
    assert "age" in names


def test_update_field(client_with_fields):
    fields = client_with_fields.get("/api/fields").json()
    fid = fields[0]["id"]
    resp = client_with_fields.put(f"/api/fields/{fid}", json={"field_label": "Full Name"})
    assert resp.status_code == 200
    assert resp.json()["field_label"] == "Full Name"


def test_delete_field(client_with_fields):
    fields = client_with_fields.get("/api/fields").json()
    fid = fields[0]["id"]
    resp = client_with_fields.delete(f"/api/fields/{fid}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    remaining = client_with_fields.get("/api/fields").json()
    assert len(remaining) == 1


def test_create_duplicate_field(client_with_fields):
    resp = client_with_fields.post("/api/fields", json={"field_name": "name", "field_type": "text", "field_label": "Dup"})
    assert resp.status_code == 400
