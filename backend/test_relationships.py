import pytest


@pytest.fixture
def two_tables(client, default_table):
    """Two tables: default (id=default_table) and users."""
    resp = client.post("/api/tables", json={"name": "users", "label": "Users"})
    users_id = resp.json()["id"]
    return default_table, users_id


def test_create_relationship(client, two_tables):
    tid, users_id = two_tables
    resp = client.post(
        f"/api/tables/{tid}/relationships",
        json={
            "to_table_id": users_id,
            "rel_name": "owner",
            "rel_label": "Owner",
            "rel_type": "1-n",
            "from_label": "owns",
            "to_label": "owned by",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["rel_name"] == "owner"
    assert data["rel_type"] == "1-n"
    assert data["from_table_id"] == tid
    assert data["to_table_id"] == users_id


def test_list_relationships(client, two_tables):
    tid, users_id = two_tables
    client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "owner", "rel_type": "1-n"},
    )
    client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "team", "rel_type": "n-n"},
    )
    resp = client.get(f"/api/tables/{tid}/relationships")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_relationships_from_both_sides(client, two_tables):
    tid, users_id = two_tables
    client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "owner", "rel_type": "1-n"},
    )
    resp = client.get(f"/api/tables/{users_id}/relationships")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_update_relationship(client, two_tables):
    tid, users_id = two_tables
    rel = client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "owner", "rel_type": "1-n"},
    ).json()
    resp = client.put(
        f"/api/tables/{tid}/relationships/{rel['id']}",
        json={"rel_label": "Owner Person"},
    )
    assert resp.status_code == 200
    assert resp.json()["rel_label"] == "Owner Person"


def test_delete_relationship(client, two_tables):
    tid, users_id = two_tables
    rel = client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "owner", "rel_type": "1-n"},
    ).json()
    resp = client.delete(f"/api/tables/{tid}/relationships/{rel['id']}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert len(client.get(f"/api/tables/{tid}/relationships").json()) == 0


def test_duplicate_relationship_name_rejected(client, two_tables):
    tid, users_id = two_tables
    client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "owner", "rel_type": "1-n"},
    )
    resp = client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "owner", "rel_type": "n-n"},
    )
    assert resp.status_code == 400


def test_1n_relationship_link(client, two_tables):
    tid, users_id = two_tables
    client.post(
        f"/api/tables/{users_id}/fields",
        json={"field_name": "name", "field_type": "text", "field_label": "Name"},
    )
    user = client.post(
        f"/api/tables/{users_id}/items",
        json={"owner": "alice", "data": {"name": "Alice"}},
    ).json()

    rel = client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "owner", "rel_type": "1-n"},
    ).json()

    item = client.post(
        f"/api/tables/{tid}/items",
        json={"owner": "deal1", "data": {}},
    ).json()

    resp = client.post(
        f"/api/tables/{tid}/relationships/{rel['id']}/link",
        json={"item_id": item["id"], "target_ids": [user["id"]]},
    )
    assert resp.status_code == 200

    fetched = client.get(f"/api/tables/{tid}/items/{item['id']}").json()
    assert fetched["relationships"]["owner"]["item_id"] == user["id"]
    assert fetched["relationships"]["owner"]["label"] == "alice"


def test_nn_relationship_link(client, two_tables):
    tid, users_id = two_tables
    u1 = client.post(
        f"/api/tables/{users_id}/items", json={"owner": "alice", "data": {}}
    ).json()
    u2 = client.post(
        f"/api/tables/{users_id}/items", json={"owner": "bob", "data": {}}
    ).json()

    rel = client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "team", "rel_type": "n-n"},
    ).json()

    item = client.post(
        f"/api/tables/{tid}/items", json={"owner": "project1", "data": {}}
    ).json()

    client.post(
        f"/api/tables/{tid}/relationships/{rel['id']}/link",
        json={"item_id": item["id"], "target_ids": [u1["id"], u2["id"]]},
    )

    fetched = client.get(f"/api/tables/{tid}/items/{item['id']}").json()
    team = fetched["relationships"]["team"]["items"]
    assert len(team) == 2
    labels = {t["label"] for t in team}
    assert labels == {"alice", "bob"}


def test_nn_relationship_replace_links(client, two_tables):
    tid, users_id = two_tables
    u1 = client.post(
        f"/api/tables/{users_id}/items", json={"owner": "alice", "data": {}}
    ).json()
    u2 = client.post(
        f"/api/tables/{users_id}/items", json={"owner": "bob", "data": {}}
    ).json()

    rel = client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "team", "rel_type": "n-n"},
    ).json()

    item = client.post(
        f"/api/tables/{tid}/items", json={"owner": "project1", "data": {}}
    ).json()

    client.post(
        f"/api/tables/{tid}/relationships/{rel['id']}/link",
        json={"item_id": item["id"], "target_ids": [u1["id"], u2["id"]]},
    )

    client.post(
        f"/api/tables/{tid}/relationships/{rel['id']}/link",
        json={"item_id": item["id"], "target_ids": [u2["id"]]},
    )

    fetched = client.get(f"/api/tables/{tid}/items/{item['id']}").json()
    team = fetched["relationships"]["team"]["items"]
    assert len(team) == 1
    assert team[0]["label"] == "bob"


def test_delete_table_cleans_relationships(client, two_tables):
    tid, users_id = two_tables
    client.post(
        f"/api/tables/{tid}/relationships",
        json={"to_table_id": users_id, "rel_name": "owner", "rel_type": "1-n"},
    )
    client.delete(f"/api/tables/{tid}")
    remaining = [t for t in client.get("/api/tables").json() if t["id"] == tid]
    assert len(remaining) == 0


def test_multiple_rels_to_same_table(client, two_tables):
    tid, users_id = two_tables
    r1 = client.post(
        f"/api/tables/{tid}/relationships",
        json={
            "to_table_id": users_id,
            "rel_name": "owner",
            "rel_label": "Owner",
            "rel_type": "1-n",
        },
    )
    r2 = client.post(
        f"/api/tables/{tid}/relationships",
        json={
            "to_table_id": users_id,
            "rel_name": "team",
            "rel_label": "Team Members",
            "rel_type": "n-n",
        },
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert len(client.get(f"/api/tables/{tid}/relationships").json()) == 2
