"""Tests to improve coverage for low-coverage modules."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import uuid

PROTOCOL_VERSION: str = "1.0"

# Test synapse/core/security.py
@pytest.mark.asyncio
async def test_security_capability_manager_require():
    """Test security capability manager require."""
    from synapse.core.security import CapabilityManager, CapabilityError
    manager = CapabilityManager()
    # Issue token first
    await manager.issue_token(capability="fs:read", issued_to="default", issued_by="test")
    await manager.require(["fs:read"], agent_id="default")
    assert True

@pytest.mark.asyncio
async def test_security_capability_manager_require_without_token():
    """Test security capability manager require without token - should raise error."""
    from synapse.core.security import CapabilityManager, CapabilityError
    manager = CapabilityManager()
    # Without issuing a token, require should raise CapabilityError
    with pytest.raises(CapabilityError):
        await manager.require(["fs:read"], agent_id="default")

@pytest.mark.asyncio
async def test_security_capability_error():
    """Test CapabilityError exception."""
    from synapse.core.security import CapabilityError
    error = CapabilityError("test error")
    assert str(error) == "test error"

# Test synapse/core/orchestrator.py
@pytest.mark.asyncio
async def test_orchestrator_with_mocks():
    """Test orchestrator with mocked dependencies."""
    from synapse.core.orchestrator import Orchestrator
    from synapse.core.determinism import DeterministicSeedManager, DeterministicIDGenerator
    
    seed_manager = MagicMock(spec=DeterministicSeedManager)
    id_generator = MagicMock(spec=DeterministicIDGenerator)
    # Use 'generate' instead of 'generate_id'
    id_generator.generate.return_value = "test-id"
    
    orch = Orchestrator(seed_manager, id_generator)
    assert orch is not None

@pytest.mark.asyncio
async def test_capability_token_creation():
    """Test CapabilityToken creation."""
    from synapse.core.security import CapabilityToken
    token = CapabilityToken(
        capability="fs:read:/workspace/**",
        scope="/workspace/**",
        issued_to="test_agent",
        issued_by="test_issuer"
    )
    assert token.capability == "fs:read:/workspace/**"
    assert token.issued_to == "test_agent"
    assert token.protocol_version == "1.0"

@pytest.mark.asyncio
async def test_security_check_result():
    """Test SecurityCheckResult creation."""
    from synapse.core.security import SecurityCheckResult
    result = SecurityCheckResult(approved=True)
    assert result.approved == True
    assert result.protocol_version == "1.0"

@pytest.mark.asyncio
async def test_capability_manager_issue_token():
    """Test CapabilityManager issue_token."""
    from synapse.core.security import CapabilityManager
    manager = CapabilityManager()
    token = await manager.issue_token(
        capability="fs:read:/workspace/**",
        issued_to="test_agent",
        issued_by="test_issuer"
    )
    assert token is not None
    assert token.capability == "fs:read:/workspace/**"

@pytest.mark.asyncio
async def test_capability_manager_check_capabilities():
    """Test CapabilityManager check_capabilities."""
    from synapse.core.security import CapabilityManager
    manager = CapabilityManager()
    
    # Issue token first
    await manager.issue_token(
        capability="fs:read:/workspace/**",
        issued_to="test_agent",
        issued_by="test_issuer"
    )
    
    # Check capabilities
    result = await manager.check_capabilities(
        required=["fs:read:/workspace/test.txt"],
        agent_id="test_agent"
    )
    assert result.approved == True

@pytest.mark.asyncio
async def test_capability_manager_revoke_token():
    """Test CapabilityManager revoke_token."""
    from synapse.core.security import CapabilityManager
    manager = CapabilityManager()
    
    # Issue token
    token = await manager.issue_token(
        capability="fs:read:/workspace/**",
        issued_to="test_agent",
        issued_by="test_issuer"
    )
    
    # Revoke token
    result = await manager.revoke_token(token.id, "test_agent")
    assert result == True

@pytest.mark.asyncio
async def test_capability_manager_get_agent_capabilities():
    """Test CapabilityManager get_agent_capabilities."""
    from synapse.core.security import CapabilityManager
    manager = CapabilityManager()
    
    # Issue token
    await manager.issue_token(
        capability="fs:read:/workspace/**",
        issued_to="test_agent",
        issued_by="test_issuer"
    )
    
    # Get capabilities
    capabilities = await manager.get_agent_capabilities("test_agent")
    assert len(capabilities) == 1
    assert capabilities[0] == "fs:read:/workspace/**"
