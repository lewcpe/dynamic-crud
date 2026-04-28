def test_create_item(client_with_fields):
    resp = client_with_fields.post("/api/items", json={"owner": "alice", "data": {"name": "Alice", "age": 30}})
    assert resp.status_code == 201
    data = resp.json()
    assert data["owner"] == "alice"
    assert data["fields"]["name"] == "Alice"
    assert data["fields"]["age"] == 30


def test_get_item(client_with_fields):
    created = client_with_fields.post("/api/items", json={"owner": "bob", "data": {"name": "Bob", "age": 25}}).json()
    resp = client_with_fields.get(f"/api/items/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["fields"]["name"] == "Bob"


def test_list_items(client_with_fields):
    client_with_fields.post("/api/items", json={"owner": "a", "data": {"name": "A", "age": 1}})
    client_with_fields.post("/api/items", json={"owner": "b", "data": {"name": "B", "age": 2}})
    resp = client_with_fields.get("/api/items")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_update_item(client_with_fields):
    created = client_with_fields.post("/api/items", json={"owner": "old", "data": {"name": "Old", "age": 10}}).json()
    resp = client_with_fields.put(f"/api/items/{created['id']}", json={"owner": "new", "data": {"name": "New", "age": 20}})
    assert resp.status_code == 200
    assert resp.json()["owner"] == "new"
    assert resp.json()["fields"]["name"] == "New"


def test_delete_item(client_with_fields):
    created = client_with_fields.post("/api/items", json={"owner": "x", "data": {}}).json()
    resp = client_with_fields.delete(f"/api/items/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_search_items(client_with_fields):
    client_with_fields.post("/api/items", json={"owner": "alice", "data": {"name": "Alice", "age": 30}})
    client_with_fields.post("/api/items", json={"owner": "bob", "data": {"name": "Bob", "age": 25}})
    resp = client_with_fields.get("/api/items", params={"search": "alice"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["owner"] == "alice"


def test_sort_items(client_with_fields):
    client_with_fields.post("/api/items", json={"owner": "a", "data": {"name": "Z", "age": 1}})
    client_with_fields.post("/api/items", json={"owner": "b", "data": {"name": "A", "age": 2}})
    resp = client_with_fields.get("/api/items", params={"sort_by": "name", "sort_dir": "asc"})
    items = resp.json()["items"]
    assert items[0]["fields"]["name"] == "A"
