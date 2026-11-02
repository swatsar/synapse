"""Comprehensive Security Tests for Fix Sprint #2.

Target: >90% coverage for security modules.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from synapse.security.capability_manager import (
    CapabilityManager,
    CapabilityError,
    CapabilityCheckResult,
    SecurityCheckResult
)
from synapse.security.execution_guard import (
    ExecutionGuard,
    ExecutionCheckResult
)
from synapse.core.isolation_policy import RuntimeIsolationType
from synapse.core.models import ResourceLimits, ExecutionContext


# ============================================================================
# CAPABILITY MANAGER COMPREHENSIVE TESTS
# ============================================================================

@pytest.mark.phase2
@pytest.mark.security
class TestCapabilityManagerComprehensive:
    """Comprehensive tests for CapabilityManager."""
    
    @pytest.fixture
    def capability_manager(self):
        """Create a fresh CapabilityManager for each test."""
        return CapabilityManager()
    
    @pytest.fixture
    def test_context(self):
        """Create a test execution context."""
        return ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=["fs:read:/workspace/**", "fs:write:/workspace/project/*"],
            memory_store=MagicMock(),
            logger=MagicMock(),
            resource_limits=ResourceLimits(
                cpu_seconds=60,
                memory_mb=512,
                disk_mb=100,
                network_kb=1024
            ),
            protocol_version="1.0"
        )
    
    def test_revoke_capability(self, capability_manager):
        """Test revoking a capability."""
        # Grant a capability
        capability_manager.grant("fs:read:/workspace/**")
        
        # Verify it's granted
        assert "fs:read:/workspace/**" in capability_manager._granted_capabilities
        
        # Revoke the capability
        capability_manager.revoke("fs:read:/workspace/**")
        
        # Verify it's revoked
        assert "fs:read:/workspace/**" not in capability_manager._granted_capabilities
    
    def test_revoke_nonexistent_capability(self, capability_manager):
        """Test revoking a capability that doesn't exist (should not raise)."""
        # Should not raise an error
        capability_manager.revoke("nonexistent:capability")
    
    def test_grant_capability_alias(self, capability_manager):
        """Test grant_capability alias method."""
        capability_manager.grant_capability("fs:read:/workspace/**")
        
        assert "fs:read:/workspace/**" in capability_manager._granted_capabilities
    
    @pytest.mark.asyncio
    async def test_check_capability_list_pattern(self, capability_manager):
        """Test check_capability with list as first argument."""
        capability_manager.grant("fs:read:/workspace/**")
        capability_manager.grant("fs:write:/workspace/**")
        
        # Should return True when all capabilities are granted
        result = await capability_manager.check_capability(["fs:read:/workspace/**", "fs:write:/workspace/**"])
        assert result == True
    
    @pytest.mark.asyncio
    async def test_check_capability_list_pattern_missing(self, capability_manager):
        """Test check_capability with list pattern when capability missing."""
        capability_manager.grant("fs:read:/workspace/**")
        
        # Should raise CapabilityError when capability missing
        with pytest.raises(CapabilityError) as exc_info:
            await capability_manager.check_capability(["fs:read:/workspace/**", "fs:delete:/workspace/**"])
        
        assert "fs:delete:/workspace/**" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_check_capability_capabilities_parameter(self, capability_manager):
        """Test check_capability with capabilities parameter."""
        capability_manager.grant("fs:read:/workspace/**")
        
        result = await capability_manager.check_capability(capabilities=["fs:read:/workspace/**", "fs:write:/workspace/**"])
        
        assert isinstance(result, SecurityCheckResult)
        assert result.approved == False  # fs:write not granted
        assert "fs:read:/workspace/**" in result.granted
        assert "fs:write:/workspace/**" in result.denied
    
    @pytest.mark.asyncio
    async def test_check_capability_required_without_context(self, capability_manager):
        """Test check_capability with required but no context."""
        capability_manager.grant("fs:read:/workspace/**")
        
        result = await capability_manager.check_capability(required="fs:read:/workspace/**")
        
        assert isinstance(result, SecurityCheckResult)
        assert result.approved == True
    
    @pytest.mark.asyncio
    async def test_check_capability_required_list_without_context(self, capability_manager):
        """Test check_capability with required list but no context."""
        capability_manager.grant("fs:read:/workspace/**")
        capability_manager.grant("fs:write:/workspace/**")
        
        result = await capability_manager.check_capability(required=["fs:read:/workspace/**", "fs:write:/workspace/**"])
        
        assert result == True
    
    @pytest.mark.asyncio
    async def test_check_capability_required_list_missing(self, capability_manager):
        """Test check_capability with required list when one missing."""
        capability_manager.grant("fs:read:/workspace/**")
        
        with pytest.raises(CapabilityError):
            await capability_manager.check_capability(required=["fs:read:/workspace/**", "fs:delete:/workspace/**"])
    
    @pytest.mark.asyncio
    async def test_check_capability_wildcard(self, capability_manager):
        """Test check_capability with wildcard capability."""
        capability_manager.grant("*")
        
        result = await capability_manager.check_capability(required="any:capability:here")
        
        assert isinstance(result, SecurityCheckResult)
        assert result.approved == True
    
    @pytest.mark.asyncio
    async def test_check_capability_context_with_capabilities(self, capability_manager, test_context):
        """Test check_capability with context that has capabilities."""
        result = await capability_manager.check_capability(context=test_context)
        
        assert isinstance(result, SecurityCheckResult)
        assert result.approved == True  # Context has capabilities
    
    @pytest.mark.asyncio
    async def test_check_capability_context_no_capabilities(self, capability_manager):
        """Test check_capability with context that has no capabilities."""
        context = ExecutionContext(
            session_id="test",
            agent_id="test",
            trace_id="test",
            capabilities=[],  # No capabilities
            memory_store=MagicMock(),
            logger=MagicMock(),
            resource_limits=ResourceLimits(cpu_seconds=60, memory_mb=512, disk_mb=100, network_kb=1024),
            protocol_version="1.0"
        )
        
        result = await capability_manager.check_capability(context=context)
        
        assert isinstance(result, SecurityCheckResult)
        assert result.approved == False  # No capabilities
    
    @pytest.mark.asyncio
    async def test_check_capability_fallback(self, capability_manager):
        """Test check_capability fallback when no parameters."""
        result = await capability_manager.check_capability()
        
        assert isinstance(result, SecurityCheckResult)
        assert result.approved == True  # Default approved
    
    @pytest.mark.asyncio
    async def test_check_single_capability_wildcard(self, capability_manager, test_context):
        """Test _check_single_capability with wildcard in context."""
        test_context.capabilities = ["*"]
        
        result = await capability_manager._check_single_capability(test_context, "any:capability")
        
        assert result == True
    
    @pytest.mark.asyncio
    async def test_check_single_capability_match(self, capability_manager, test_context):
        """Test _check_single_capability with matching capability."""
        result = await capability_manager._check_single_capability(test_context, "fs:read:/workspace/file.txt")
        
        assert result == True
    
    @pytest.mark.asyncio
    async def test_check_single_capability_denied(self, capability_manager, test_context):
        """Test _check_single_capability when capability denied."""
        test_context.capabilities = ["fs:read:/workspace/**"]
        
        result = await capability_manager._check_single_capability(test_context, "fs:delete:/workspace/**")
        
        assert result == False
    
    @pytest.mark.asyncio
    async def test_check_single_capability_internal_granted(self, capability_manager, test_context):
        """Test _check_single_capability with internally granted capability."""
        test_context.capabilities = []
        capability_manager.grant("fs:read:/workspace/**")
        
        result = await capability_manager._check_single_capability(test_context, "fs:read:/workspace/file.txt")
        
        assert result == True
    
    def test_check_capabilities_list(self, capability_manager):
        """Test check_capabilities method."""
        capability_manager.grant("fs:read:/workspace/**")
        
        context = MagicMock()
        context.capabilities = ["fs:read:/workspace/**"]
        
        result = capability_manager.check_capabilities(context, ["fs:read:/workspace/**", "fs:write:/workspace/**"])
        
        assert isinstance(result, CapabilityCheckResult)
        assert result.approved == False
        assert "fs:read:/workspace/**" in result.granted
        assert "fs:write:/workspace/**" in result.denied
    
    def test_sync_check_wildcard(self, capability_manager):
        """Test _sync_check with wildcard."""
        context = MagicMock()
        context.capabilities = ["*"]
        
        result = capability_manager._sync_check(context, "any:capability")
        
        assert result == True
    
    def test_sync_check_match(self, capability_manager):
        """Test _sync_check with matching capability."""
        context = MagicMock()
        context.capabilities = ["fs:read:/workspace/**"]
        
        result = capability_manager._sync_check(context, "fs:read:/workspace/file.txt")
        
        assert result == True
    
    def test_sync_check_internal_granted(self, capability_manager):
        """Test _sync_check with internally granted capability."""
        context = MagicMock()
        context.capabilities = []
        capability_manager.grant("fs:read:/workspace/**")
        
        result = capability_manager._sync_check(context, "fs:read:/workspace/file.txt")
        
        assert result == True
    
    def test_sync_check_denied(self, capability_manager):
        """Test _sync_check when capability denied."""
        context = MagicMock()
        context.capabilities = []
        
        result = capability_manager._sync_check(context, "fs:read:/workspace/**")
        
        assert result == False
    
    def test_matches_exact(self, capability_manager):
        """Test _matches with exact match."""
        assert capability_manager._matches("fs:read:/workspace", "fs:read:/workspace") == True
    
    def test_matches_wildcard_fnmatch(self, capability_manager):
        """Test _matches with wildcard using fnmatch."""
        assert capability_manager._matches("fs:read:/*", "fs:read:/workspace") == True
        assert capability_manager._matches("fs:*:/workspace", "fs:read:/workspace") == True
    
    def test_matches_prefix_double_asterisk(self, capability_manager):
        """Test _matches with /** prefix pattern."""
        assert capability_manager._matches("fs:read:/workspace/**", "fs:read:/workspace/file.txt") == True
        assert capability_manager._matches("fs:read:/workspace/**", "fs:read:/workspace/subdir/file.txt") == True
    
    def test_matches_no_match(self, capability_manager):
        """Test _matches when no match."""
        assert capability_manager._matches("fs:read:/workspace", "fs:write:/workspace") == False
    
    @pytest.mark.asyncio
    async def test_validate_capabilities_valid(self, capability_manager):
        """Test validate_capabilities with valid capabilities."""
        result = await capability_manager.validate_capabilities("test_skill", ["fs:read:/workspace", "fs:write:/workspace"])
        
        assert result == True
    
    @pytest.mark.asyncio
    async def test_validate_capabilities_invalid(self, capability_manager):
        """Test validate_capabilities with invalid capability format."""
        with pytest.raises(CapabilityError) as exc_info:
            await capability_manager.validate_capabilities("test_skill", ["invalid_capability"])
        
        assert "Invalid capability" in str(exc_info.value)
    
    def test_is_valid_capability_valid(self, capability_manager):
        """Test _is_valid_capability with valid format."""
        assert capability_manager._is_valid_capability("fs:read:/workspace") == True
        assert capability_manager._is_valid_capability("net:http:example.com") == True
    
    def test_is_valid_capability_invalid(self, capability_manager):
        """Test _is_valid_capability with invalid format."""
        assert capability_manager._is_valid_capability("invalid_capability") == False
        assert capability_manager._is_valid_capability("no_colon") == False
    
    def test_capability_error_initialization(self):
        """Test CapabilityError initialization."""
        error = CapabilityError(required="fs:read:/workspace")
        
        assert error.required == "fs:read:/workspace"
        assert "fs:read:/workspace" in error.message
    
    def test_capability_error_custom_message(self):
        """Test CapabilityError with custom message."""
        error = CapabilityError(required="fs:read", message="Custom error")
        
        assert error.message == "Custom error"
    
    def test_capability_check_result(self):
        """Test CapabilityCheckResult initialization."""
        result = CapabilityCheckResult(approved=True, granted=["cap1"], denied=[])
        
        assert result.approved == True
        assert result.granted == ["cap1"]
        assert result.denied == []
        assert result.blocked_capabilities == []
    
    def test_security_check_result(self):
        """Test SecurityCheckResult initialization."""
        result = SecurityCheckResult(approved=False, granted=[], denied=["cap1"])
        
        assert result.approved == False
        assert result.blocked_capabilities == ["cap1"]


# ============================================================================
# EXECUTION GUARD COMPREHENSIVE TESTS
# ============================================================================

@pytest.mark.phase2
@pytest.mark.security
class TestExecutionGuardComprehensive:
    """Comprehensive tests for ExecutionGuard."""
    
    @pytest.fixture
    def capability_manager(self):
        """Create a CapabilityManager for tests."""
        cm = CapabilityManager()
        cm.grant("fs:read:/workspace/**")
        return cm
    
    @pytest.fixture
    def execution_guard(self, capability_manager):
        """Create an ExecutionGuard for tests."""
        return ExecutionGuard(capability_manager=capability_manager)
    
    @pytest.fixture
    def test_skill(self):
        """Create a mock skill for tests."""
        skill = MagicMock()
        skill.manifest = MagicMock()
        skill.manifest.name = "test_skill"
        skill.manifest.required_capabilities = ["fs:read:/workspace/**"]
        skill.manifest.risk_level = 1
        skill.manifest.trust_level = "trusted"
        return skill
    
    @pytest.fixture
    def test_context(self):
        """Create a test execution context."""
        return ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=["fs:read:/workspace/**"],
            memory_store=MagicMock(),
            logger=MagicMock(),
            resource_limits=ResourceLimits(
                cpu_seconds=60,
                memory_mb=512,
                disk_mb=100,
                network_kb=1024
            ),
            protocol_version="1.0"
        )
    
    def test_execution_guard_properties(self, execution_guard):
        """Test ExecutionGuard properties."""
        assert execution_guard.isolation_policy is not None
        assert isinstance(execution_guard.limits, dict)
    
    def test_execution_guard_with_limits_dict(self):
        """Test ExecutionGuard with limits as dict."""
        guard = ExecutionGuard(limits={"cpu_seconds": 60, "memory_mb": 512})
        
        assert guard.limits["cpu_seconds"] == 60
        assert guard.limits["memory_mb"] == 512
    
    def test_execution_guard_with_pydantic_limits(self):
        """Test ExecutionGuard with Pydantic ResourceLimits."""
        limits = ResourceLimits(cpu_seconds=60, memory_mb=512, disk_mb=100, network_kb=1024)
        guard = ExecutionGuard(limits=limits)
        
        assert guard.limits == limits
    
    @pytest.mark.asyncio
    async def test_async_context_manager_success(self, execution_guard):
        """Test async context manager with successful execution."""
        async with execution_guard as guard:
            assert guard == execution_guard
    
    @pytest.mark.asyncio
    async def test_async_context_manager_with_exception(self, execution_guard):
        """Test async context manager with exception."""
        with pytest.raises(ValueError):
            async with execution_guard:
                raise ValueError("Test error")
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_exceeded_cpu(self):
        """Test resource limit check with exceeded CPU."""
        guard = ExecutionGuard(limits={"cpu_seconds": 400, "memory_mb": 512})
        
        with pytest.raises(ValueError) as exc_info:
            async with guard:
                pass
        
        assert "CPU limit" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_exceeded_memory(self):
        """Test resource limit check with exceeded memory."""
        guard = ExecutionGuard(limits={"cpu_seconds": 60, "memory_mb": 5000})
        
        with pytest.raises(ValueError) as exc_info:
            async with guard:
                pass
        
        assert "Memory limit" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_pydantic_exceeded_cpu(self):
        """Test resource limit check with Pydantic model exceeded CPU."""
        limits = ResourceLimits(cpu_seconds=400, memory_mb=512, disk_mb=100, network_kb=1024)
        guard = ExecutionGuard(limits=limits)
        
        with pytest.raises(ValueError) as exc_info:
            async with guard:
                pass
        
        assert "CPU limit" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_pydantic_exceeded_memory(self):
        """Test resource limit check with Pydantic model exceeded memory."""
        limits = ResourceLimits(cpu_seconds=60, memory_mb=5000, disk_mb=100, network_kb=1024)
        guard = ExecutionGuard(limits=limits)
        
        with pytest.raises(ValueError) as exc_info:
            async with guard:
                pass
        
        assert "Memory limit" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_check_execution_allowed(self, execution_guard, test_skill, test_context):
        """Test check_execution_allowed with valid skill."""
        result = await execution_guard.check_execution_allowed(test_skill, test_context)
        
        assert isinstance(result, ExecutionCheckResult)
        assert result.allowed == True
        assert result.requires_approval == False
    
    @pytest.mark.asyncio
    async def test_check_execution_allowed_missing_capability(self, execution_guard, test_context):
        """Test check_execution_allowed with missing capability."""
        skill = MagicMock()
        skill.manifest = MagicMock()
        skill.manifest.name = "restricted_skill"
        skill.manifest.required_capabilities = ["fs:delete:/workspace/**"]  # Not granted
        skill.manifest.risk_level = 1
        skill.manifest.trust_level = "trusted"
        
        result = await execution_guard.check_execution_allowed(skill, test_context)
        
        assert result.allowed == False
        assert "Missing capability" in result.reason
        assert "fs:delete:/workspace/**" in result.blocked_capabilities
    
    @pytest.mark.asyncio
    async def test_check_execution_allowed_high_risk(self, execution_guard, test_context):
        """Test check_execution_allowed with high risk skill."""
        skill = MagicMock()
        skill.manifest = MagicMock()
        skill.manifest.name = "high_risk_skill"
        skill.manifest.required_capabilities = []
        skill.manifest.risk_level = 4  # High risk
        skill.manifest.trust_level = "verified"
        
        result = await execution_guard.check_execution_allowed(skill, test_context)
        
        assert result.allowed == False
        assert result.requires_approval == True
        assert "requires human approval" in result.reason
    
    @pytest.mark.asyncio
    async def test_check_execution_allowed_no_capability_manager(self, test_skill, test_context):
        """Test check_execution_allowed without capability manager."""
        guard = ExecutionGuard()  # No capability manager
        
        result = await guard.check_execution_allowed(test_skill, test_context)
        
        # Should still work, just skip capability check
        assert result.allowed == True
    
    def test_get_required_isolation(self, execution_guard):
        """Test get_required_isolation method."""
        isolation = execution_guard.get_required_isolation("trusted", 1)
        
        assert isinstance(isolation, RuntimeIsolationType)
    
    @pytest.mark.asyncio
    async def test_run_method(self, execution_guard):
        """Test run method for async execution."""
        async def test_func():
            return "success"
        
        result = await execution_guard.run(test_func)
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_run_method_with_args(self, execution_guard):
        """Test run method with arguments."""
        async def test_func(a, b):
            return a + b
        
        result = await execution_guard.run(test_func, 1, 2)
        
        assert result == 3
    
    @pytest.mark.asyncio
    async def test_run_method_with_exception(self, execution_guard):
        """Test run method when function raises exception."""
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await execution_guard.run(failing_func)
    
    def test_execution_check_result_defaults(self):
        """Test ExecutionCheckResult default values."""
        result = ExecutionCheckResult(allowed=True)
        
        assert result.allowed == True
        assert result.requires_approval == False
        assert result.approval_granted == False
        assert result.reason == ""
        assert result.required_isolation is None
        assert result.blocked_capabilities == []


# ============================================================================
# DEPRECATION WARNING FIXES TESTS
# ============================================================================

@pytest.mark.phase2
@pytest.mark.security
class TestDeprecationFixes:
    """Tests to verify deprecation warnings are fixed."""
    
    def test_capability_manager_protocol_version(self):
        """Verify CapabilityManager has correct protocol version."""
        cm = CapabilityManager()
        
        assert cm.protocol_version == "1.0"
        assert CapabilityManager.protocol_version == "1.0"
    
    def test_execution_guard_protocol_version(self):
        """Verify ExecutionGuard has correct protocol version."""
        guard = ExecutionGuard()
        
        assert guard.protocol_version == "1.0"
        assert ExecutionGuard.protocol_version == "1.0"
    
    def test_capability_error_attributes(self):
        """Verify CapabilityError has required attributes."""
        error = CapabilityError(required="test:cap", message="Test")
        
        assert hasattr(error, 'required')
        assert hasattr(error, 'message')
