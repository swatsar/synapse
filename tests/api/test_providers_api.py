"""Tests for LLM Providers API.

Following TDD: Write tests first, then implement.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

PROTOCOL_VERSION = "1.0"


@pytest.fixture
def client():
    """Create test client."""
    from synapse.api.app import app
    return TestClient(app)


@pytest.fixture
def mock_provider_service():
    """Mock provider service."""
    with patch("synapse.api.routes.providers.provider_service") as mock:
        yield mock


# === LIST PROVIDERS ===

@pytest.mark.api
@pytest.mark.tdd
def test_list_providers_returns_empty_list(client):
    """Test listing providers when none exist."""
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)
    assert data["protocol_version"] == PROTOCOL_VERSION


@pytest.mark.api
@pytest.mark.tdd
def test_list_providers_returns_providers(client, mock_provider_service):
    """Test listing providers when they exist."""
    mock_provider_service.list_providers.return_value = [
        {"id": "openai", "name": "OpenAI", "models": ["gpt-4o"], "priority": 1}
    ]
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    data = response.json()
    assert len(data["providers"]) == 1
    assert data["providers"][0]["id"] == "openai"


# === GET PROVIDER ===

@pytest.mark.api
@pytest.mark.tdd
def test_get_provider_by_id(client, mock_provider_service):
    """Test getting a specific provider."""
    mock_provider_service.get_provider.return_value = {
        "id": "openai",
        "name": "OpenAI",
        "models": ["gpt-4o"],
        "priority": 1
    }
    response = client.get("/api/v1/providers/openai")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "openai"


@pytest.mark.api
@pytest.mark.tdd
def test_get_provider_not_found(client, mock_provider_service):
    """Test getting a non-existent provider."""
    mock_provider_service.get_provider.return_value = None
    response = client.get("/api/v1/providers/nonexistent")
    assert response.status_code == 404


# === CREATE PROVIDER ===

@pytest.mark.api
@pytest.mark.tdd
def test_create_provider_success(client, mock_provider_service):
    """Test creating a new provider."""
    mock_provider_service.create_provider.return_value = {
        "id": "anthropic",
        "name": "Anthropic",
        "api_key": "***",
        "models": ["claude-3.5"],
        "priority": 2
    }
    response = client.post("/api/v1/providers", json={
        "name": "Anthropic",
        "api_key": "sk-ant-test",
        "models": ["claude-3.5"],
        "priority": 2
    })
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "anthropic"


@pytest.mark.api
@pytest.mark.tdd
def test_create_provider_missing_api_key(client):
    """Test creating provider without API key."""
    response = client.post("/api/v1/providers", json={
        "name": "OpenAI",
        "models": ["gpt-4o"]
    })
    assert response.status_code == 422  # Validation error


# === UPDATE PROVIDER ===

@pytest.mark.api
@pytest.mark.tdd
def test_update_provider_success(client, mock_provider_service):
    """Test updating a provider."""
    mock_provider_service.update_provider.return_value = {
        "id": "openai",
        "name": "OpenAI",
        "models": ["gpt-4o", "gpt-4-turbo"],
        "priority": 1
    }
    response = client.put("/api/v1/providers/openai", json={
        "models": ["gpt-4o", "gpt-4-turbo"]
    })
    assert response.status_code == 200
    data = response.json()
    assert "gpt-4-turbo" in data["models"]


# === DELETE PROVIDER ===

@pytest.mark.api
@pytest.mark.tdd
def test_delete_provider_success(client, mock_provider_service):
    """Test deleting a provider."""
    mock_provider_service.delete_provider.return_value = True
    response = client.delete("/api/v1/providers/openai")
    assert response.status_code == 204


@pytest.mark.api
@pytest.mark.tdd
def test_delete_provider_not_found(client, mock_provider_service):
    """Test deleting a non-existent provider."""
    mock_provider_service.delete_provider.return_value = False
    response = client.delete("/api/v1/providers/nonexistent")
    assert response.status_code == 404


# === TEST CONNECTION ===

@pytest.mark.api
@pytest.mark.tdd
def test_provider_test_connection_success(client, mock_provider_service):
    """Test provider connection."""
    mock_provider_service.test_connection.return_value = {
        "success": True,
        "latency_ms": 150,
        "model": "gpt-4o"
    }
    response = client.post("/api/v1/providers/openai/test")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True


@pytest.mark.api
@pytest.mark.tdd
def test_provider_test_connection_failure(client, mock_provider_service):
    """Test provider connection failure."""
    mock_provider_service.test_connection.return_value = {
        "success": False,
        "error": "Invalid API key"
    }
    response = client.post("/api/v1/providers/openai/test")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == False


# === MODELS ===

@pytest.mark.api
@pytest.mark.tdd
def test_list_provider_models(client, mock_provider_service):
    """Test listing models for a provider."""
    mock_provider_service.list_models.return_value = [
        {"id": "gpt-4o", "name": "GPT-4o", "context_window": 128000},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context_window": 128000}
    ]
    response = client.get("/api/v1/providers/openai/models")
    assert response.status_code == 200
    data = response.json()
    assert len(data["models"]) == 2


# === PRIORITY ===

@pytest.mark.api
@pytest.mark.tdd
def test_set_provider_priority(client, mock_provider_service):
    """Test setting provider priority."""
    mock_provider_service.set_priority.return_value = {
        "id": "openai",
        "priority": 1
    }
    response = client.patch("/api/v1/providers/openai/priority", json={
        "priority": 1
    })
    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == 1
