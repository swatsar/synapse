"""
Unit tests for MemoryVault (claude-mem integration).
"""

import pytest
from pathlib import Path
from synapse.memory.vault import MemoryVault, MemoryType, PROTOCOL_VERSION


@pytest.fixture
def vault(tmp_path):
    storage_file = tmp_path / "test_vault.json"
    return MemoryVault(storage_path=storage_file)


def test_protocol_version(vault):
    entry = vault.create_entry("Test Title", "Test Content", MemoryType.CONVENTION)
    assert entry.protocol_version == PROTOCOL_VERSION


def test_create_and_retrieve_entry(vault):
    entry = vault.create_entry("Architecture Pattern", "Always isolate plugins", MemoryType.PROJECT, tags=["arch", "plugins"])
    retrieved = vault.get_entry(entry.id)
    assert retrieved is not None
    assert retrieved.title == "Architecture Pattern"
    assert "arch" in retrieved.tags


def test_update_and_delete_entry(vault):
    entry = vault.create_entry("Temporary Note", "Old text", MemoryType.USER)
    vault.update_entry(entry.id, content="New updated text")
    assert vault.get_entry(entry.id).content == "New updated text"

    assert vault.delete_entry(entry.id) is True
    assert vault.get_entry(entry.id) is None


def test_hybrid_search(vault):
    vault.create_entry("Docker Compose Setup", "Run docker-compose.dev.yml for testing", MemoryType.PROJECT, tags=["docker"])
    vault.create_entry("Python Guidelines", "Use type annotations on all functions", MemoryType.CONVENTION, tags=["python"])

    results = vault.search("docker testing")
    assert len(results) >= 1
    assert "Docker Compose Setup" in results[0].title
    assert results[0].use_count == 1


def test_auto_distillation(vault):
    distilled = vault.distill_from_interaction(
        user_prompt="Remember: always use pytest basetemp on windows",
        assistant_response="Confirmed, I will configure basetemp for all test executions.",
    )
    assert distilled is not None
    assert distilled.memory_type == MemoryType.FEEDBACK
    assert "distilled" in distilled.tags
