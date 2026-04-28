def test_create_item(client_with_fields):
    client, tid = client_with_fields
    resp = client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "alice", "data": {"name": "Alice", "age": 30}},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["owner"] == "alice"
    assert data["fields"]["name"] == "Alice"
    assert data["fields"]["age"] == 30


def test_get_item(client_with_fields):
    client, tid = client_with_fields
    created = client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "bob", "data": {"name": "Bob", "age": 25}},
    ).json()
    resp = client.get(f"/api/tables/{tid}/items/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["fields"]["name"] == "Bob"


def test_list_items(client_with_fields):
    client, tid = client_with_fields
    client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "a", "data": {"name": "A", "age": 1}},
    )
    client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "b", "data": {"name": "B", "age": 2}},
    )
    resp = client.get(f"/api/tables/{tid}/items")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_update_item(client_with_fields):
    client, tid = client_with_fields
    created = client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "old", "data": {"name": "Old", "age": 10}},
    ).json()
    resp = client.put(
        f"/api/tables/{tid}/items/{created['id']}",
        json={"owner": "new", "data": {"name": "New", "age": 20}},
    )
    assert resp.status_code == 200
    assert resp.json()["owner"] == "new"
    assert resp.json()["fields"]["name"] == "New"


def test_delete_item(client_with_fields):
    client, tid = client_with_fields
    created = client.post(
        f"/api/tables/{tid}/items", json={"owner": "x", "data": {}}
    ).json()
    resp = client.delete(f"/api/tables/{tid}/items/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_search_items(client_with_fields):
    client, tid = client_with_fields
    client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "alice", "data": {"name": "Alice", "age": 30}},
    )
    client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "bob", "data": {"name": "Bob", "age": 25}},
    )
    resp = client.get(f"/api/tables/{tid}/items", params={"search": "alice"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["owner"] == "alice"


def test_sort_items(client_with_fields):
    client, tid = client_with_fields
    client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "a", "data": {"name": "Z", "age": 1}},
    )
    client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "b", "data": {"name": "A", "age": 2}},
    )
    resp = client.get(
        f"/api/tables/{tid}/items",
        params={"sort_by": "name", "sort_dir": "asc"},
    )
    items = resp.json()["items"]
    assert items[0]["fields"]["name"] == "A"
