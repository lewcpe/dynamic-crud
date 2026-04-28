import pytest
from fastapi.testclient import TestClient
import main


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Each test gets a fresh temporary database."""
    old_path = main.DB_PATH
    main.DB_PATH = tmp_path / "test.db"
    main.init_db()
    yield
    main.DB_PATH = old_path


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def client_with_fields(client):
    """Client with 2 pre-created fields: name (text), age (int)."""
    client.post("/api/fields", json={"field_name": "name", "field_type": "text", "field_label": "Name"})
    client.post("/api/fields", json={"field_name": "age", "field_type": "int", "field_label": "Age"})
    return client
