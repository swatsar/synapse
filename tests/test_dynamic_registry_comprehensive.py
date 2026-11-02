"""Comprehensive tests for Dynamic Skill Registry.
Phase 2: Skill Lifecycle Tests
"""
import pytest
from unittest.mock import AsyncMock
from synapse.skills.dynamic.registry import (
    SkillRegistry,
    SkillLifecycleStatus,
    PROTOCOL_VERSION,
    SPEC_VERSION
)
from synapse.core.models import SkillManifest


@pytest.fixture
def mock_capability_manager():
    manager = AsyncMock()
    manager.check_capability = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def registry(mock_capability_manager):
    return SkillRegistry(capability_manager=mock_capability_manager)


@pytest.fixture
def manifest():
    return SkillManifest(
        name="test_skill",
        version="1.0.0",
        description="Test skill",
        author="test",
        inputs={},
        outputs={},
        required_capabilities=[],
        trust_level="unverified",
        risk_level=1
    )


@pytest.fixture
async def handler():
    async def mock_handler():
        return "test"
    return mock_handler


class TestDynamicSkillRegistryComprehensive:
    """Comprehensive tests for SkillRegistry."""
    
    def test_registry_creation(self, registry):
        """Test registry creation."""
        assert registry is not None
        assert registry.protocol_version == "1.0"
    
    def test_protocol_version(self, registry):
        """Test protocol version."""
        assert PROTOCOL_VERSION == "1.0"
        assert SPEC_VERSION == "3.1"
    
    @pytest.mark.asyncio
    async def test_register_skill(self, registry, manifest, handler):
        """Test registering a skill."""
        skill_id = await registry.register(manifest, handler)
        assert skill_id is not None
        assert isinstance(skill_id, str)
        # Verify skill is in registry
        assert skill_id in registry._registry
    
    @pytest.mark.asyncio
    async def test_get_skill(self, registry, manifest, handler):
        """Test getting a skill."""
        skill_id = await registry.register(manifest, handler)
        # Use get_by_id to get SkillRecord
        skill = registry.get_by_id(skill_id)
        assert skill is not None
        assert skill.skill_id == skill_id
    
    def test_list_skills(self, registry):
        """Test listing skills."""
        skills = registry.list_skills()
        assert isinstance(skills, dict)  # list_skills returns Dict
    
    def test_validate_manifest(self, registry, manifest):
        """Test manifest validation."""
        # Should not raise
        registry._validate_manifest(manifest)
    
    def test_validate_manifest_invalid(self, registry):
        """Test manifest validation with invalid manifest."""
        with pytest.raises(Exception):
            registry._validate_manifest(None)
