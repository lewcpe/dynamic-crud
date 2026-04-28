def test_create_field(client, default_table):
    tid = default_table
    resp = client.post(
        f"/api/tables/{tid}/fields",
        json={"field_name": "status", "field_type": "text", "field_label": "Status"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["field_name"] == "status"
    assert data["field_type"] == "text"
    assert data["field_label"] == "Status"


def test_list_fields(client_with_fields):
    client, tid = client_with_fields
    resp = client.get(f"/api/tables/{tid}/fields")
    assert resp.status_code == 200
    fields = resp.json()
    assert len(fields) == 2
    names = [f["field_name"] for f in fields]
    assert "name" in names
    assert "age" in names


def test_update_field(client_with_fields):
    client, tid = client_with_fields
    fields = client.get(f"/api/tables/{tid}/fields").json()
    fid = fields[0]["id"]
    resp = client.put(
        f"/api/tables/{tid}/fields/{fid}",
        json={"field_label": "Full Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["field_label"] == "Full Name"


def test_delete_field(client_with_fields):
    client, tid = client_with_fields
    fields = client.get(f"/api/tables/{tid}/fields").json()
    fid = fields[0]["id"]
    resp = client.delete(f"/api/tables/{tid}/fields/{fid}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    remaining = client.get(f"/api/tables/{tid}/fields").json()
    assert len(remaining) == 1


def test_create_duplicate_field(client_with_fields):
    client, tid = client_with_fields
    resp = client.post(
        f"/api/tables/{tid}/fields",
        json={"field_name": "name", "field_type": "text", "field_label": "Dup"},
    )
    assert resp.status_code == 400
