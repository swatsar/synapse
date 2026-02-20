"""Tests for Settings API.

Following TDD: Write tests first, then implement.
"""
import pytest
from fastapi.testclient import TestClient

PROTOCOL_VERSION = "1.0"


@pytest.fixture
def client():
    """Create test client."""
    from synapse.api.app import app
    return TestClient(app)


# === SYSTEM SETTINGS ===

@pytest.mark.api
@pytest.mark.tdd
def test_get_system_settings(client):
    """Test getting system settings."""
    response = client.get("/api/v1/settings/system")
    assert response.status_code == 200
    data = response.json()
    assert "settings" in data
    assert data["protocol_version"] == PROTOCOL_VERSION


@pytest.mark.api
@pytest.mark.tdd
def test_update_system_settings(client):
    """Test updating system settings."""
    response = client.put("/api/v1/settings/system", json={
        "log_level": "DEBUG",
        "max_agents": 10
    })
    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["log_level"] == "DEBUG"


# === SECURITY SETTINGS ===

@pytest.mark.api
@pytest.mark.tdd
def test_get_security_settings(client):
    """Test getting security settings."""
    response = client.get("/api/v1/settings/security")
    assert response.status_code == 200
    data = response.json()
    assert "settings" in data


@pytest.mark.api
@pytest.mark.tdd
def test_update_security_settings(client):
    """Test updating security settings."""
    response = client.put("/api/v1/settings/security", json={
        "require_approval_for_risk": 3,
        "rate_limit_per_minute": 60
    })
    assert response.status_code == 200


# === MEMORY SETTINGS ===

@pytest.mark.api
@pytest.mark.tdd
def test_get_memory_settings(client):
    """Test getting memory settings."""
    response = client.get("/api/v1/settings/memory")
    assert response.status_code == 200
    data = response.json()
    assert "settings" in data


# === CONNECTOR SETTINGS ===

@pytest.mark.api
@pytest.mark.tdd
def test_get_connector_settings(client):
    """Test getting connector settings."""
    response = client.get("/api/v1/settings/connectors")
    assert response.status_code == 200
    data = response.json()
    assert "settings" in data


@pytest.mark.api
@pytest.mark.tdd
def test_update_telegram_settings(client):
    """Test updating Telegram settings."""
    response = client.put("/api/v1/settings/connectors/telegram", json={
        "enabled": True,
        "token": "test_token"
    })
    assert response.status_code == 200


# === ENVIRONMENT VARIABLES ===

@pytest.mark.api
@pytest.mark.tdd
def test_list_env_vars(client):
    """Test listing environment variables."""
    response = client.get("/api/v1/settings/env")
    assert response.status_code == 200
    data = response.json()
    assert "variables" in data


@pytest.mark.api
@pytest.mark.tdd
def test_set_env_var(client):
    """Test setting an environment variable."""
    response = client.post("/api/v1/settings/env", json={
        "key": "TEST_VAR",
        "value": "test_value"
    })
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tdd
def test_delete_env_var(client):
    """Test deleting an environment variable."""
    response = client.delete("/api/v1/settings/env/TEST_VAR")
    assert response.status_code in [200, 204]


# === BACKUP/RESTORE ===

@pytest.mark.api
@pytest.mark.tdd
def test_create_backup(client):
    """Test creating a backup."""
    response = client.post("/api/v1/settings/backup")
    assert response.status_code == 200
    data = response.json()
    assert "backup_id" in data


@pytest.mark.api
@pytest.mark.tdd
def test_list_backups(client):
    """Test listing backups."""
    response = client.get("/api/v1/settings/backups")
    assert response.status_code == 200
    data = response.json()
    assert "backups" in data


@pytest.mark.api
@pytest.mark.tdd
def test_restore_backup(client):
    """Test restoring from backup."""
    response = client.post("/api/v1/settings/restore/backup_123")
    assert response.status_code in [200, 404]
