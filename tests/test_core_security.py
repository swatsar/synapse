"""Tests for core security."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestCoreSecurity:
    """Test core security."""

    @pytest.fixture
    def capability_manager(self):
        """Create a capability manager for testing."""
        from synapse.core.security import CapabilityManager as CoreCapabilityManager

        return CoreCapabilityManager()

    def test_capability_manager_creation(self, capability_manager):
        """Test capability manager creation."""
        assert capability_manager is not None

    @pytest.mark.asyncio
    async def test_require_capabilities(self, capability_manager):
        """Test requiring capabilities."""
        result = await capability_manager.require(["test:capability"])
        assert result == True
