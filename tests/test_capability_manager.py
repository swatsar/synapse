"""Tests for capability manager."""
import pytest


class TestCapabilityManager:
    """Test capability manager."""

    @pytest.fixture
    def capability_manager(self):
        """Create a capability manager for testing."""
        from synapse.security.capability_manager import CapabilityManager
        return CapabilityManager()

    def test_capability_manager_creation(self, capability_manager):
        """Test capability manager creation."""
        assert capability_manager is not None

    def test_grant_capability(self, capability_manager):
        """Test granting capability."""
        capability_manager.grant_capability("test:capability")
        assert "test:capability" in capability_manager._granted_capabilities

    @pytest.mark.asyncio
    async def test_check_capability(self, capability_manager):
        """Test checking capability."""
        capability_manager.grant_capability("test:capability")
        result = await capability_manager.check_capability(["test:capability"])
        assert result == True

    @pytest.mark.asyncio
    async def test_check_capability_missing(self, capability_manager):
        """Test checking missing capability."""
        from synapse.security.capability_manager import CapabilityError
        with pytest.raises(CapabilityError):
            await capability_manager.check_capability(["missing:capability"])

    @pytest.mark.asyncio
    async def test_validate_capabilities(self, capability_manager):
        """Test validating capabilities."""
        await capability_manager.validate_capabilities("unknown_skill", [])
