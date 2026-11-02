"""Tests for dynamic skill registry."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestDynamicSkillRegistry:
    """Test dynamic skill registry."""

    @pytest.fixture
    def registry(self):
        """Create a dynamic skill registry for testing."""
        from synapse.skills.dynamic.registry import SkillRegistry
        from synapse.security.capability_manager import CapabilityManager

        caps = CapabilityManager()
        caps.grant_capability("skill:register")
        caps.grant_capability("skill:load")

        return SkillRegistry(capability_manager=caps)

    def test_registry_creation(self, registry):
        """Test registry creation."""
        assert registry is not None

    def test_protocol_version(self, registry):
        """Test protocol version."""
        assert registry.protocol_version == "1.0"

    def test_list_skills(self, registry):
        """Test listing skills."""
        skills = registry.list_skills()
        assert isinstance(skills, dict)

    @pytest.mark.asyncio
    async def test_register_skill(self, registry):
        """Test registering a skill."""
        from synapse.core.models import SkillManifest

        manifest = SkillManifest(
            name="test_skill",
            version="1.0.0",
            description="Test skill",
            author="test",
            inputs={},
            outputs={},
            required_capabilities=[]
        )

        handler = AsyncMock(return_value={"result": "success"})

        await registry.register(manifest, handler)

        # Check skill is registered
        skills = registry.list_skills()
        assert "test_skill" in skills

    def test_get_skill(self, registry):
        """Test getting a skill."""
        # This should raise KeyError for non-existent skill
        with pytest.raises(KeyError):
            registry.get("non_existent_skill")
