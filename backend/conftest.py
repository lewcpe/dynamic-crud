import pytest
from fastapi.testclient import TestClient
import main


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Each test gets a fresh temporary database."""
    old_path = main.DB_PATH
    main.DB_PATH = tmp_path / "test.db"
    main.run_migrations()
    yield
    main.DB_PATH = old_path


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def default_table(client):
    """Returns the default table id created by migration."""
    resp = client.get("/api/tables")
    assert resp.status_code == 200
    tables = resp.json()
    assert len(tables) >= 1
    return tables[0]["id"]


@pytest.fixture
def client_with_fields(client, default_table):
    """Client with default table and 2 pre-created fields: name (text), age (int)."""
    tid = default_table
    client.post(
        f"/api/tables/{tid}/fields",
        json={"field_name": "name", "field_type": "text", "field_label": "Name"},
    )
    client.post(
        f"/api/tables/{tid}/fields",
        json={"field_name": "age", "field_type": "int", "field_label": "Age"},
    )
    return client, tid
