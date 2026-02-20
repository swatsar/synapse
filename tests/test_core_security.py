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
        """Test requiring capabilities with token issued first."""
        # Issue token first
        token = await capability_manager.issue_token(
            capability="test:capability",
            issued_to="default",
            issued_by="test"
        )
        assert token is not None
        
        # Now require should succeed
        result = await capability_manager.require(["test:capability"], agent_id="default")
        assert result == True

    @pytest.mark.asyncio
    async def test_require_capabilities_denied(self, capability_manager):
        """Test requiring capabilities without token fails."""
        from synapse.core.security import CapabilityError
        
        # Should fail without token
        with pytest.raises(CapabilityError):
            await capability_manager.require(["missing:capability"], agent_id="default")

    @pytest.mark.asyncio
    async def test_issue_token(self, capability_manager):
        """Test issuing a token."""
        token = await capability_manager.issue_token(
            capability="fs:read:/workspace/**",
            issued_to="agent1",
            issued_by="system"
        )
        assert token.capability == "fs:read:/workspace/**"
        assert token.issued_to == "agent1"
        assert token.protocol_version == "1.0"

    @pytest.mark.asyncio
    async def test_check_capabilities(self, capability_manager):
        """Test checking capabilities."""
        # Issue token
        await capability_manager.issue_token(
            capability="fs:read:/workspace/**",
            issued_to="agent1",
            issued_by="system"
        )
        
        # Check should pass
        result = await capability_manager.check_capabilities(
            required=["fs:read:/workspace/test.txt"],
            agent_id="agent1"
        )
        assert result.approved == True

    @pytest.mark.asyncio
    async def test_revoke_token(self, capability_manager):
        """Test revoking a token."""
        # Issue token
        token = await capability_manager.issue_token(
            capability="test:capability",
            issued_to="agent1",
            issued_by="system"
        )
        
        # Revoke token
        result = await capability_manager.revoke_token(token.id, "agent1")
        assert result == True
        
        # Check should now fail
        check_result = await capability_manager.check_capabilities(
            required=["test:capability"],
            agent_id="agent1"
        )
        assert check_result.approved == False
