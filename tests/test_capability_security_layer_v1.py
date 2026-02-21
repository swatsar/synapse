"""
Phase 1: Capability Security Layer v1 - Test Plan

TDD Methodology: These tests are written FIRST and should FAIL initially.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import uuid

# Mark all tests in this file as phase1
pytestmark = pytest.mark.phase1


class TestCapabilityContract:
    """Test Capability Contract component."""
    
    @pytest.fixture
    def capability_contract_data(self):
        """Sample capability contract data."""
        return {
            "capability": "fs:read:/workspace/**",
            "scope": "/workspace/**",
            "constraints": {"max_file_size": "10MB"},
            "issued_to": "agent_001",
            "issued_by": "system"
        }
    
    @pytest.mark.asyncio
    async def test_capability_contract_creation(self, capability_contract_data):
        """Test creating a capability contract."""
        # This test should FAIL initially - CapabilityContract not yet implemented
        from synapse.core.security import CapabilityContract
        
        contract = CapabilityContract(**capability_contract_data)
        
        assert contract.capability == "fs:read:/workspace/**"
        assert contract.scope == "/workspace/**"
        assert contract.issued_to == "agent_001"
        assert contract.protocol_version == "1.0"
        assert contract.id is not None
    
    @pytest.mark.asyncio
    async def test_capability_contract_immutability(self, capability_contract_data):
        """Test that capability contract is immutable after creation."""
        from synapse.core.security import CapabilityContract
        
        contract = CapabilityContract(**capability_contract_data)
        
        # Should raise error when trying to modify
        with pytest.raises(Exception):  # Pydantic ValidationError or similar
            contract.capability = "fs:write:/workspace/**"
    
    @pytest.mark.asyncio
    async def test_capability_contract_expiration(self, capability_contract_data):
        """Test capability contract expiration."""
        from synapse.core.security import CapabilityContract
        
        # Set expiration in the past
        capability_contract_data["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()
        
        contract = CapabilityContract(**capability_contract_data)
        
        # Contract should be expired
        assert contract.is_expired() == True


class TestPermissionEnforcer:
    """Test Permission Enforcement component."""
    
    @pytest.fixture
    def enforcer(self):
        """Create permission enforcer instance."""
        from synapse.core.security import PermissionEnforcer
        return PermissionEnforcer()
    
    @pytest.mark.asyncio
    async def test_enforcer_creation(self, enforcer):
        """Test permission enforcer creation."""
        assert enforcer is not None
    
    @pytest.mark.asyncio
    async def test_enforce_allowed_action(self, enforcer):
        """Test enforcing an allowed action."""
        from synapse.core.security import CapabilityManager
        
        # Setup capability
        manager = CapabilityManager()
        await manager.issue_token(
            capability="fs:read:/workspace/**",
            issued_to="agent_001",
            issued_by="system"
        )
        
        # Enforce should allow
        result = await enforcer.enforce(
            action="fs:read:/workspace/test.txt",
            agent_id="agent_001",
            capability_manager=manager
        )
        
        assert result.approved == True
        assert result.enforced == True
    
    @pytest.mark.asyncio
    async def test_enforce_denied_action(self, enforcer):
        """Test enforcing a denied action."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        # No capabilities issued
        
        result = await enforcer.enforce(
            action="fs:read:/workspace/test.txt",
            agent_id="agent_001",
            capability_manager=manager
        )
        
        assert result.approved == False
        assert result.reason is not None
    
    @pytest.mark.asyncio
    async def test_enforce_audit_emission(self, enforcer):
        """Test that enforcement emits audit event."""
        from synapse.core.security import CapabilityManager, AuditMechanism
        
        audit = AuditMechanism()
        manager = CapabilityManager(audit_logger=audit)
        
        await manager.issue_token(
            capability="fs:read:/workspace/**",
            issued_to="agent_001",
            issued_by="system"
        )
        
        result = await enforcer.enforce(
            action="fs:read:/workspace/test.txt",
            agent_id="agent_001",
            capability_manager=manager,
            audit=audit
        )
        
        # Check audit event was emitted
        events = await audit.get_events()
        assert any(e.event_type == "capability_checked" for e in events)


class TestAuditMechanism:
    """Test Audit Mechanism component."""
    
    @pytest.fixture
    def audit(self):
        """Create audit mechanism instance."""
        from synapse.core.security import AuditMechanism
        return AuditMechanism()
    
    @pytest.mark.asyncio
    async def test_audit_creation(self, audit):
        """Test audit mechanism creation."""
        assert audit is not None
    
    @pytest.mark.asyncio
    async def test_emit_capability_created_event(self, audit):
        """Test emitting capability_created event."""
        event_id = await audit.emit_event(
            event_type="capability_created",
            details={
                "capability": "fs:read:/workspace/**",
                "agent_id": "agent_001"
            }
        )
        
        assert event_id is not None
        
        events = await audit.get_events()
        assert len(events) == 1
        assert events[0].event_type == "capability_created"
    
    @pytest.mark.asyncio
    async def test_emit_capability_denied_event(self, audit):
        """Test emitting capability_denied event."""
        await audit.emit_event(
            event_type="capability_denied",
            details={
                "capability": "fs:write:/etc/**",
                "agent_id": "agent_001",
                "reason": "Insufficient permissions"
            }
        )
        
        events = await audit.get_events()
        denied_events = [e for e in events if e.event_type == "capability_denied"]
        assert len(denied_events) == 1
    
    @pytest.mark.asyncio
    async def test_audit_event_structure(self, audit):
        """Test audit event has required structure."""
        from synapse.core.security import AuditEvent
        
        await audit.emit_event(
            event_type="capability_checked",
            details={
                "agent_id": "agent_001",
                "capability": "fs:read:/workspace/**"
            }
        )
        
        events = await audit.get_events()
        event = events[0]
        
        assert hasattr(event, 'event_type')
        assert hasattr(event, 'timestamp')
        assert hasattr(event, 'agent_id')
        assert hasattr(event, 'protocol_version')
        assert event.protocol_version == "1.0"


class TestRuntimeGuard:
    """Test Runtime Guard Middleware component."""
    
    @pytest.fixture
    def guard(self):
        """Create runtime guard instance."""
        from synapse.core.security import RuntimeGuard
        return RuntimeGuard()
    
    @pytest.mark.asyncio
    async def test_guard_creation(self, guard):
        """Test runtime guard creation."""
        assert guard is not None
    
    @pytest.mark.asyncio
    async def test_guard_allows_authorized_action(self, guard):
        """Test guard allows authorized action."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        await manager.issue_token(
            capability="fs:read:/workspace/**",
            issued_to="agent_001",
            issued_by="system"
        )
        
        async def test_action():
            return "success"
        
        result = await guard.guard(
            action=test_action,
            capabilities=["fs:read:/workspace/test.txt"],
            agent_id="agent_001",
            capability_manager=manager
        )
        
        assert result.allowed == True
        assert result.result == "success"
    
    @pytest.mark.asyncio
    async def test_guard_blocks_unauthorized_action(self, guard):
        """Test guard blocks unauthorized action."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        # No capabilities issued
        
        async def test_action():
            return "should not execute"
        
        result = await guard.guard(
            action=test_action,
            capabilities=["fs:read:/workspace/test.txt"],
            agent_id="agent_001",
            capability_manager=manager
        )
        
        assert result.allowed == False
        assert result.result is None
    
    @pytest.mark.asyncio
    async def test_guard_emits_audit_event(self, guard):
        """Test guard emits audit event."""
        from synapse.core.security import CapabilityManager, AuditMechanism
        
        audit = AuditMechanism()
        manager = CapabilityManager(audit_logger=audit)
        
        async def test_action():
            return "success"
        
        await guard.guard(
            action=test_action,
            capabilities=["fs:read:/workspace/test.txt"],
            agent_id="agent_001",
            capability_manager=manager,
            audit=audit
        )
        
        events = await audit.get_events()
        assert any(e.event_type in ["capability_checked", "capability_denied"] for e in events)


class TestDeterministicBehavior:
    """Test deterministic behavior of capability checks."""
    
    @pytest.mark.asyncio
    async def test_deterministic_capability_check(self):
        """Test that capability checks are deterministic."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        await manager.issue_token(
            capability="fs:read:/workspace/**",
            issued_to="agent_001",
            issued_by="system"
        )
        
        # Run same check multiple times
        results = []
        for _ in range(10):
            result = await manager.check_capabilities(
                required=["fs:read:/workspace/test.txt"],
                agent_id="agent_001"
            )
            results.append(result.approved)
        
        # All results should be identical
        assert all(r == True for r in results)
    
    @pytest.mark.asyncio
    async def test_deterministic_denial(self):
        """Test that denials are deterministic."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        # No capabilities
        
        results = []
        for _ in range(10):
            result = await manager.check_capabilities(
                required=["fs:read:/workspace/test.txt"],
                agent_id="agent_001"
            )
            results.append(result.approved)
        
        assert all(r == False for r in results)


class TestConcurrencySafety:
    """Test concurrency safety of capability system."""
    
    @pytest.mark.asyncio
    async def test_concurrent_capability_checks(self):
        """Test concurrent capability checks are safe."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        await manager.issue_token(
            capability="fs:read:/workspace/**",
            issued_to="agent_001",
            issued_by="system"
        )
        
        async def check_capability():
            return await manager.check_capabilities(
                required=["fs:read:/workspace/test.txt"],
                agent_id="agent_001"
            )
        
        # Run 100 concurrent checks
        tasks = [check_capability() for _ in range(100)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(r.approved for r in results)
    
    @pytest.mark.asyncio
    async def test_concurrent_token_issuance(self):
        """Test concurrent token issuance is safe."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        
        async def issue_token(i):
            return await manager.issue_token(
                capability=f"test:capability:{i}",
                issued_to=f"agent_{i}",
                issued_by="system"
            )
        
        # Issue 100 tokens concurrently
        tasks = [issue_token(i) for i in range(100)]
        tokens = await asyncio.gather(*tasks)
        
        # All tokens should be unique
        token_ids = [t.id for t in tokens]
        assert len(set(token_ids)) == 100


class TestAgentIsolation:
    """Test agent isolation in capability system."""
    
    @pytest.mark.asyncio
    async def test_agent_cannot_use_other_agent_capabilities(self):
        """Test that agent cannot use another agent's capabilities."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        
        # Issue capability to agent_001
        await manager.issue_token(
            capability="fs:read:/workspace/**",
            issued_to="agent_001",
            issued_by="system"
        )
        
        # agent_002 should not have access
        result = await manager.check_capabilities(
            required=["fs:read:/workspace/test.txt"],
            agent_id="agent_002"
        )
        
        assert result.approved == False
    
    @pytest.mark.asyncio
    async def test_revoked_capability_not_usable(self):
        """Test that revoked capability cannot be used."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        
        token = await manager.issue_token(
            capability="fs:read:/workspace/**",
            issued_to="agent_001",
            issued_by="system"
        )
        
        # Should work initially
        result1 = await manager.check_capabilities(
            required=["fs:read:/workspace/test.txt"],
            agent_id="agent_001"
        )
        assert result1.approved == True
        
        # Revoke token
        await manager.revoke_token(token.id, "agent_001")
        
        # Should fail now
        result2 = await manager.check_capabilities(
            required=["fs:read:/workspace/test.txt"],
            agent_id="agent_001"
        )
        assert result2.approved == False


class TestZeroImplicitPermissions:
    """Test zero implicit permissions principle."""
    
    @pytest.mark.asyncio
    async def test_no_default_capabilities(self):
        """Test that agents have no capabilities by default."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        
        # Check various capabilities - all should be denied
        capabilities_to_test = [
            "fs:read:/workspace/**",
            "fs:write:/workspace/**",
            "network:http",
            "os:process"
        ]
        
        for cap in capabilities_to_test:
            result = await manager.check_capabilities(
                required=[cap],
                agent_id="new_agent"
            )
            assert result.approved == False, f"Capability {cap} should be denied by default"
    
    @pytest.mark.asyncio
    async def test_wildcard_denied_without_explicit_permission(self):
        """Test that wildcard access is denied without explicit permission."""
        from synapse.core.security import CapabilityManager
        
        manager = CapabilityManager()
        
        result = await manager.check_capabilities(
            required=["*"],
            agent_id="agent_001"
        )
        
        assert result.approved == False
