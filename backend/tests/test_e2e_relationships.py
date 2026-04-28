"""End-to-end tests for relationship flow with item options."""
import pytest


def test_relationship_dropdown_shows_items(client):
    """Test that relationship dropdown shows items from related table."""
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create two tables with represent expressions
    t1 = client.post("/api/tables", json={"name": "companies", "label": "Companies", "represent": "{name}"}, headers=headers).json()
    t2 = client.post("/api/tables", json={"name": "people", "label": "People", "represent": "{first_name} {last_name}"}, headers=headers).json()

    # Add fields
    client.post(f"/api/tables/{t1['id']}/fields", json={"field_name": "name", "field_type": "text", "field_label": "Name"}, headers=headers)
    client.post(f"/api/tables/{t2['id']}/fields", json={"field_name": "first_name", "field_type": "text", "field_label": "First Name"}, headers=headers)
    client.post(f"/api/tables/{t2['id']}/fields", json={"field_name": "last_name", "field_type": "text", "field_label": "Last Name"}, headers=headers)

    # Create items
    c1 = client.post(f"/api/tables/{t1['id']}/items", json={"owner": "default", "data": {"name": "Acme Corp"}}, headers=headers).json()
    c2 = client.post(f"/api/tables/{t1['id']}/items", json={"owner": "default", "data": {"name": "Widget Inc"}}, headers=headers).json()
    p1 = client.post(f"/api/tables/{t2['id']}/items", json={"owner": "default", "data": {"first_name": "John", "last_name": "Doe"}}, headers=headers).json()
    p2 = client.post(f"/api/tables/{t2['id']}/items", json={"owner": "default", "data": {"first_name": "Jane", "last_name": "Smith"}}, headers=headers).json()

    # Verify item options for companies use represent expression
    options = client.get(f"/api/tables/{t1['id']}/items/options", headers=headers).json()
    assert len(options) == 2
    assert options[0] == {"id": c1["id"], "label": "Acme Corp"}
    assert options[1] == {"id": c2["id"], "label": "Widget Inc"}

    # Verify item options for people use represent expression
    options = client.get(f"/api/tables/{t2['id']}/items/options", headers=headers).json()
    assert len(options) == 2
    assert options[0] == {"id": p1["id"], "label": "John Doe"}
    assert options[1] == {"id": p2["id"], "label": "Jane Smith"}


def test_relationship_options_update_after_create(client):
    """Test that new items appear in relationship options immediately."""
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    t = client.post("/api/tables", json={"name": "tasks", "label": "Tasks"}, headers=headers).json()
    client.post(f"/api/tables/{t['id']}/fields", json={"field_name": "title", "field_type": "text", "field_label": "Title"}, headers=headers)

    # Empty initially
    options = client.get(f"/api/tables/{t['id']}/items/options", headers=headers).json()
    assert len(options) == 0

    # Create item
    item = client.post(f"/api/tables/{t['id']}/items", json={"owner": "default", "data": {"title": "Task 1"}}, headers=headers).json()

    # Now shows in options
    options = client.get(f"/api/tables/{t['id']}/items/options", headers=headers).json()
    assert len(options) == 1
    assert options[0]["id"] == item["id"]


def test_1n_relationship_from_side(client):
    """Test 1-n relationship: from side shows single item_id."""
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    t1 = client.post("/api/tables", json={"name": "projects", "represent": "{name}"}, headers=headers).json()
    t2 = client.post("/api/tables", json={"name": "tasks", "represent": "{title}"}, headers=headers).json()
    client.post(f"/api/tables/{t1['id']}/fields", json={"field_name": "name", "field_type": "text", "field_label": "Name"}, headers=headers)
    client.post(f"/api/tables/{t2['id']}/fields", json={"field_name": "title", "field_type": "text", "field_label": "Title"}, headers=headers)

    # Create 1-n: project has many tasks
    rel = client.post(f"/api/tables/{t1['id']}/relationships", json={
        "rel_name": "tasks", "rel_label": "Tasks", "rel_type": "1-n", "to_table_id": t2["id"]
    }, headers=headers).json()

    project = client.post(f"/api/tables/{t1['id']}/items", json={"owner": "default", "data": {"name": "Project Alpha"}}, headers=headers).json()
    task1 = client.post(f"/api/tables/{t2['id']}/items", json={"owner": "default", "data": {"title": "Task 1"}}, headers=headers).json()

    # Link task to project (FK is on tasks table)
    client.post(f"/api/tables/{t2['id']}/relationships/{rel['id']}/link", json={
        "item_id": task1["id"], "target_ids": [project["id"]]
    }, headers=headers)

    # From project side: shows item_id (single reference)
    project_data = client.get(f"/api/tables/{t1['id']}/items/{project['id']}", headers=headers).json()
    assert project_data["relationships"]["tasks"]["item_id"] == task1["id"]
    assert project_data["relationships"]["tasks"]["label"] == "Task 1"

    # From task side: shows items list (reverse lookup)
    task_data = client.get(f"/api/tables/{t2['id']}/items/{task1['id']}", headers=headers).json()
    assert len(task_data["relationships"]["tasks"]["items"]) == 1
    assert task_data["relationships"]["tasks"]["items"][0]["item_id"] == project["id"]


def test_nn_relationship(client):
    """Test n-n relationship: both sides show items list."""
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    t1 = client.post("/api/tables", json={"name": "articles", "represent": "{title}"}, headers=headers).json()
    t2 = client.post("/api/tables", json={"name": "tags", "represent": "{name}"}, headers=headers).json()
    client.post(f"/api/tables/{t1['id']}/fields", json={"field_name": "title", "field_type": "text", "field_label": "Title"}, headers=headers)
    client.post(f"/api/tables/{t2['id']}/fields", json={"field_name": "name", "field_type": "text", "field_label": "Name"}, headers=headers)

    # Create n-n relationship
    rel = client.post(f"/api/tables/{t1['id']}/relationships", json={
        "rel_name": "tags", "rel_label": "Tags", "rel_type": "n-n", "to_table_id": t2["id"]
    }, headers=headers).json()

    article = client.post(f"/api/tables/{t1['id']}/items", json={"owner": "default", "data": {"title": "My Article"}}, headers=headers).json()
    tag1 = client.post(f"/api/tables/{t2['id']}/items", json={"owner": "default", "data": {"name": "python"}}, headers=headers).json()
    tag2 = client.post(f"/api/tables/{t2['id']}/items", json={"owner": "default", "data": {"name": "fastapi"}}, headers=headers).json()

    # Link tags to article
    client.post(f"/api/tables/{t1['id']}/relationships/{rel['id']}/link", json={
        "item_id": article["id"], "target_ids": [tag1["id"], tag2["id"]]
    }, headers=headers)

    # From article side: shows items list
    article_data = client.get(f"/api/tables/{t1['id']}/items/{article['id']}", headers=headers).json()
    tags = article_data["relationships"]["tags"]["items"]
    assert len(tags) == 2
    assert tags[0]["label"] == "python"
    assert tags[1]["label"] == "fastapi"

    # From tag side: shows items list (reverse)
    tag_data = client.get(f"/api/tables/{t2['id']}/items/{tag1['id']}", headers=headers).json()
    articles = tag_data["relationships"]["tags"]["items"]
    assert len(articles) == 1
    assert articles[0]["label"] == "My Article"


def test_system_table_relationship(client):
    """Test relationship to system tables (users/groups)."""
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create group
    client.post("/api/groups", json={"name": "developers"}, headers=headers)

    # Create table with relationship to users
    t = client.post("/api/tables", json={"name": "tasks", "represent": "{title}"}, headers=headers).json()
    client.post(f"/api/tables/{t['id']}/fields", json={"field_name": "title", "field_type": "text", "field_label": "Title"}, headers=headers)

    client.post(f"/api/tables/{t['id']}/relationships", json={
        "rel_name": "assigned_to", "rel_label": "Assigned To", "rel_type": "1-n", "to_system_table": "users"
    }, headers=headers)

    # System users available
    users = client.get("/api/system/users", headers=headers).json()
    assert len(users) >= 1
    assert users[0]["label"] == "admin"

    # System groups available
    groups = client.get("/api/system/groups", headers=headers).json()
    assert any(g["label"] == "developers" for g in groups)


def test_multiple_rels_to_same_target(client):
    """Test multiple relationships to the same target table."""
    reg = client.post("/api/auth/register", json={"email": "admin@test.com", "password": "pass"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    t1 = client.post("/api/tables", json={"name": "deals", "represent": "{title}"}, headers=headers).json()
    t2 = client.post("/api/tables", json={"name": "contacts", "represent": "{name}"}, headers=headers).json()
    client.post(f"/api/tables/{t1['id']}/fields", json={"field_name": "title", "field_type": "text", "field_label": "Title"}, headers=headers)
    client.post(f"/api/tables/{t2['id']}/fields", json={"field_name": "name", "field_type": "text", "field_label": "Name"}, headers=headers)

    # Two relationships to contacts
    r1 = client.post(f"/api/tables/{t1['id']}/relationships", json={
        "rel_name": "primary_contact", "rel_label": "Primary Contact", "rel_type": "1-n", "to_table_id": t2["id"]
    }, headers=headers).json()
    r2 = client.post(f"/api/tables/{t1['id']}/relationships", json={
        "rel_name": "team_members", "rel_label": "Team Members", "rel_type": "n-n", "to_table_id": t2["id"]
    }, headers=headers).json()

    deal = client.post(f"/api/tables/{t1['id']}/items", json={"owner": "default", "data": {"title": "Big Deal"}}, headers=headers).json()
    c1 = client.post(f"/api/tables/{t2['id']}/items", json={"owner": "default", "data": {"name": "Alice"}}, headers=headers).json()
    c2 = client.post(f"/api/tables/{t2['id']}/items", json={"owner": "default", "data": {"name": "Bob"}}, headers=headers).json()

    # Options show both contacts
    options = client.get(f"/api/tables/{t2['id']}/items/options", headers=headers).json()
    assert len(options) == 2
    assert options[0]["label"] == "Alice"
    assert options[1]["label"] == "Bob"

    # Link primary contact (1-n, FK on contacts)
    client.post(f"/api/tables/{t2['id']}/relationships/{r1['id']}/link", json={
        "item_id": c1["id"], "target_ids": [deal["id"]]
    }, headers=headers)

    # Link team members (n-n)
    client.post(f"/api/tables/{t1['id']}/relationships/{r2['id']}/link", json={
        "item_id": deal["id"], "target_ids": [c1["id"], c2["id"]]
    }, headers=headers)

    # Verify
    deal_data = client.get(f"/api/tables/{t1['id']}/items/{deal['id']}", headers=headers).json()
    assert deal_data["relationships"]["primary_contact"]["item_id"] == c1["id"]
    assert deal_data["relationships"]["primary_contact"]["label"] == "Alice"
    assert len(deal_data["relationships"]["team_members"]["items"]) == 2
