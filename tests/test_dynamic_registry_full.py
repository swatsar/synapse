"""Full tests for Dynamic Skill Registry.
Phase 2: Skill Lifecycle Tests
"""
import pytest
from unittest.mock import AsyncMock
from synapse.skills.dynamic.registry import (
    SkillRegistry,
    SkillLifecycleStatus,
    PROTOCOL_VERSION
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


class TestDynamicRegistryFull:
    """Full tests for SkillRegistry."""
    
    def test_registry_creation(self, registry):
        """Test registry creation."""
        assert registry is not None
    
    def test_protocol_version(self, registry):
        """Test protocol version."""
        assert PROTOCOL_VERSION == "1.0"
    
    @pytest.mark.asyncio
    async def test_register_skill(self, registry, manifest, handler):
        """Test registering a skill."""
        skill_id = await registry.register(manifest, handler)
        assert skill_id is not None
        assert isinstance(skill_id, str)
    
    @pytest.mark.asyncio
    async def test_get_skill(self, registry, manifest, handler):
        """Test getting a skill."""
        skill_id = await registry.register(manifest, handler)
        # Use get_by_id to get SkillRecord
        skill = registry.get_by_id(skill_id)
        assert skill is not None
        assert skill.skill_id == skill_id
    
    @pytest.mark.asyncio
    async def test_lifecycle_transition(self, registry, manifest, handler):
        """Test lifecycle transition."""
        skill_id = await registry.register(manifest, handler)
        
        # Transition from GENERATED to TESTED
        result = await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        assert result == True
        assert registry.get_status(skill_id) == SkillLifecycleStatus.TESTED
