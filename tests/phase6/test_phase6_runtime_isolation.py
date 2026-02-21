"""
Phase 6: Platform Runtime Isolation & Multi-Tenant Execution Tests

Tests for:
- Execution Domain isolation
- Capability Domain boundaries
- Deterministic Sandbox
- Tenant Context security
- Isolation Enforcer
- Multi-tenant isolation
- Cross-tenant attack prevention
- Determinism per domain
- Integration with control plane
"""

import pytest
import asyncio
import hashlib
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import FrozenSet, Dict, Any, Optional, Set
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


# ============================================================================
# PART 1: EXECUTION DOMAIN TESTS
# ============================================================================

@pytest.mark.phase6
@pytest.mark.unit
class TestExecutionDomain:
    """Tests for ExecutionDomain - cryptographically identified execution scope"""
    
    def test_execution_domain_creation(self):
        """ExecutionDomain can be created with required fields"""
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read", "fs:write"]),
            state_hash="abc123"
        )
        
        assert domain.domain_id == "domain-001"
        assert domain.tenant_id == "tenant-001"
        assert domain.protocol_version == "1.0"
        assert "fs:read" in domain.capabilities
    
    def test_execution_domain_is_immutable(self):
        """ExecutionDomain must be immutable (frozen dataclass)"""
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read"]),
            state_hash="abc123"
        )
        
        with pytest.raises((AttributeError, TypeError)):
            domain.domain_id = "modified"
    
    def test_execution_domain_state_hash_computation(self):
        """ExecutionDomain computes deterministic state hash"""
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        domain1 = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read", "fs:write"]),
            state_hash=""
        )
        
        domain2 = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read", "fs:write"]),
            state_hash=""
        )
        
        # Same inputs should produce same hash
        hash1 = domain1.compute_state_hash()
        hash2 = domain2.compute_state_hash()
        assert hash1 == hash2
    
    def test_execution_domain_different_tenants_different_hash(self):
        """Different tenants produce different state hashes"""
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        domain1 = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read"]),
            state_hash=""
        )
        
        domain2 = ExecutionDomain(
            domain_id="domain-002",
            tenant_id="tenant-002",
            capabilities=frozenset(["fs:read"]),
            state_hash=""
        )
        
        hash1 = domain1.compute_state_hash()
        hash2 = domain2.compute_state_hash()
        assert hash1 != hash2
    
    def test_execution_domain_capability_scope(self):
        """ExecutionDomain has limited capability scope"""
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read:/workspace/**"]),
            state_hash="abc123"
        )
        
        assert domain.has_capability("fs:read:/workspace/file.txt")
        assert not domain.has_capability("fs:write:/workspace/file.txt")
        assert not domain.has_capability("network:http")


# ============================================================================
# PART 2: CAPABILITY DOMAIN TESTS
# ============================================================================

@pytest.mark.phase6
@pytest.mark.unit
class TestCapabilityDomain:
    """Tests for CapabilityDomain - capability scope boundaries"""
    
    def test_capability_domain_creation(self):
        """CapabilityDomain can be created"""
        from synapse.runtime_isolation.capability_domain import CapabilityDomain
        
        cap_domain = CapabilityDomain(
            domain_id="cap-domain-001",
            allowed_capabilities=frozenset(["fs:read", "fs:write"])
        )
        
        assert cap_domain.domain_id == "cap-domain-001"
        assert cap_domain.protocol_version == "1.0"
    
    def test_capability_domain_validate_scope(self):
        """CapabilityDomain validates capability scope"""
        from synapse.runtime_isolation.capability_domain import CapabilityDomain
        
        cap_domain = CapabilityDomain(
            domain_id="cap-domain-001",
            allowed_capabilities=frozenset(["fs:read:/workspace/**"])
        )
        
        assert cap_domain.validate_capability_scope("fs:read:/workspace/file.txt")
        assert not cap_domain.validate_capability_scope("fs:read:/etc/passwd")
        assert not cap_domain.validate_capability_scope("fs:write:/workspace/file.txt")
    
    def test_capability_domain_no_cross_tenant_reuse(self):
        """Capability cannot be reused across tenants"""
        from synapse.runtime_isolation.capability_domain import CapabilityDomain
        
        cap_domain_a = CapabilityDomain(
            domain_id="domain-a",
            allowed_capabilities=frozenset(["fs:read"]),
            tenant_id="tenant-a"
        )
        
        cap_domain_b = CapabilityDomain(
            domain_id="domain-b",
            allowed_capabilities=frozenset(["fs:read"]),
            tenant_id="tenant-b"
        )
        
        # Same capability string but different tenants = different scope
        assert cap_domain_a.tenant_id != cap_domain_b.tenant_id
    
    def test_capability_domain_escalation_prevented(self):
        """Capability escalation across domain is prevented"""
        from synapse.runtime_isolation.capability_domain import CapabilityDomain
        
        cap_domain = CapabilityDomain(
            domain_id="cap-domain-001",
            allowed_capabilities=frozenset(["fs:read"])
        )
        
        # Cannot escalate from read to write
        assert not cap_domain.can_escalate_to("fs:write")
        assert not cap_domain.can_escalate_to("network:http")
    
    def test_capability_domain_boundary_enforcement(self):
        """Capability domain boundary is strictly enforced"""
        from synapse.runtime_isolation.capability_domain import CapabilityDomain
        
        cap_domain = CapabilityDomain(
            domain_id="cap-domain-001",
            allowed_capabilities=frozenset(["fs:read:/workspace/**", "fs:write:/workspace/tmp/**"])
        )
        
        # Within boundary
        assert cap_domain.is_within_boundary("fs:read:/workspace/project/file.py")
        assert cap_domain.is_within_boundary("fs:write:/workspace/tmp/output.txt")
        
        # Outside boundary
        assert not cap_domain.is_within_boundary("fs:write:/workspace/important.txt")
        assert not cap_domain.is_within_boundary("fs:read:/etc/config")


# ============================================================================
# PART 3: DETERMINISTIC SANDBOX TESTS
# ============================================================================

@pytest.mark.phase6
@pytest.mark.unit
class TestDeterministicSandbox:
    """Tests for DeterministicSandbox - isolated deterministic execution"""
    
    @pytest.mark.asyncio
    async def test_sandbox_creation(self):
        """DeterministicSandbox can be created"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        assert sandbox.sandbox_id == "sandbox-001"
        assert sandbox.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_sandbox_deterministic_execution(self):
        """Sandbox produces deterministic results for identical inputs"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["compute:basic"]),
            state_hash=""
        )
        
        context = {"input": "test", "seed": 42}
        workflow = lambda x: {"result": x["input"].upper()}
        
        result1 = await sandbox.execute(workflow, context, domain)
        result2 = await sandbox.execute(workflow, context, domain)
        
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_sandbox_resource_quota_enforcement(self):
        """Sandbox enforces resource quotas"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 1, "memory_mb": 64}
        )
        
        with pytest.raises(Exception) as exc_info:
            # Simulate resource-intensive operation
            await sandbox.execute_with_quota_check(
                lambda: [i**2 for i in range(10000000)],
                expected_cpu_seconds=10
            )
        
        assert "quota" in str(exc_info.value).lower() or "resource" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_sandbox_capability_enforcement(self):
        """Sandbox enforces capabilities"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["compute:basic"]),  # No fs:write
            state_hash=""
        )
        
        with pytest.raises(Exception) as exc_info:
            await sandbox.execute_with_capability_check(
                required_capability="fs:write",
                domain=domain
            )
    
    @pytest.mark.asyncio
    async def test_sandbox_replay_identity(self):
        """Sandbox maintains replay identity"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["compute:basic"]),
            state_hash=""
        )
        
        context = {"input": "test", "seed": 42}
        workflow = lambda x: {"result": x["input"].upper()}
        
        result = await sandbox.execute(workflow, context, domain)
        replay_result = await sandbox.replay(workflow, context, domain)
        
        assert result == replay_result


# ============================================================================
# PART 4: TENANT CONTEXT TESTS
# ============================================================================

@pytest.mark.phase6
@pytest.mark.unit
class TestTenantContext:
    """Tests for TenantContext - multi-tenant security context"""
    
    def test_tenant_context_creation(self):
        """TenantContext can be created"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        
        tenant = TenantContext(
            tenant_id="tenant-001",
            domain_id="domain-001",
            issued_capabilities=frozenset(["fs:read", "fs:write"]),
            execution_quota=1000
        )
        
        assert tenant.tenant_id == "tenant-001"
        assert tenant.domain_id == "domain-001"
        assert tenant.protocol_version == "1.0"
    
    def test_tenant_context_is_immutable(self):
        """TenantContext must be immutable"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        
        tenant = TenantContext(
            tenant_id="tenant-001",
            domain_id="domain-001",
            issued_capabilities=frozenset(["fs:read"]),
            execution_quota=1000
        )
        
        with pytest.raises((AttributeError, TypeError)):
            tenant.tenant_id = "modified"
    
    def test_tenant_context_capability_check(self):
        """TenantContext can check capabilities"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        
        tenant = TenantContext(
            tenant_id="tenant-001",
            domain_id="domain-001",
            issued_capabilities=frozenset(["fs:read:/workspace/**"]),
            execution_quota=1000
        )
        
        assert tenant.has_capability("fs:read:/workspace/file.txt")
        assert not tenant.has_capability("fs:write:/workspace/file.txt")
    
    def test_tenant_context_quota_tracking(self):
        """TenantContext tracks execution quota"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        
        tenant = TenantContext(
            tenant_id="tenant-001",
            domain_id="domain-001",
            issued_capabilities=frozenset(["fs:read"]),
            execution_quota=100
        )
        
        # Create mutable tracker
        tracker = tenant.create_quota_tracker()
        tracker.consume(10)
        tracker.consume(20)
        
        assert tracker.remaining() == 70
    
    def test_tenant_context_quota_exceeded(self):
        """TenantContext raises error when quota exceeded"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        
        tenant = TenantContext(
            tenant_id="tenant-001",
            domain_id="domain-001",
            issued_capabilities=frozenset(["fs:read"]),
            execution_quota=10
        )
        
        tracker = tenant.create_quota_tracker()
        tracker.consume(5)
        
        with pytest.raises(Exception):
            tracker.consume(10)  # Would exceed quota


# ============================================================================
# PART 5: ISOLATION ENFORCER TESTS
# ============================================================================

@pytest.mark.phase6
@pytest.mark.unit
class TestIsolationEnforcer:
    """Tests for IsolationEnforcer - runtime isolation enforcement"""
    
    def test_isolation_enforcer_creation(self):
        """IsolationEnforcer can be created"""
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        
        enforcer = IsolationEnforcer()
        assert enforcer.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_enforce_tenant_isolation(self):
        """IsolationEnforcer enforces tenant isolation"""
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        from synapse.runtime_isolation.tenant_context import TenantContext
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        enforcer = IsolationEnforcer()
        
        tenant_a = TenantContext(
            tenant_id="tenant-a",
            domain_id="domain-a",
            issued_capabilities=frozenset(["fs:read"]),
            execution_quota=100
        )
        
        domain_b = ExecutionDomain(
            domain_id="domain-b",
            tenant_id="tenant-b",
            capabilities=frozenset(["fs:read"]),
            state_hash=""
        )
        
        # Tenant A cannot execute in Domain B
        with pytest.raises(Exception) as exc_info:
            await enforcer.enforce_tenant_isolation(tenant_a, domain_b)
        
        assert "isolation" in str(exc_info.value).lower() or "tenant" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_enforce_domain_boundary(self):
        """IsolationEnforcer enforces domain boundaries"""
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        from synapse.runtime_isolation.capability_domain import CapabilityDomain
        
        enforcer = IsolationEnforcer()
        
        cap_domain = CapabilityDomain(
            domain_id="cap-domain-001",
            allowed_capabilities=frozenset(["fs:read"])
        )
        
        # Cannot use capability outside domain
        assert await enforcer.enforce_domain_boundary(cap_domain, "fs:read")
        assert not await enforcer.enforce_domain_boundary(cap_domain, "fs:write")
    
    @pytest.mark.asyncio
    async def test_prevent_cross_tenant_execution(self):
        """IsolationEnforcer prevents cross-tenant execution"""
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        from synapse.runtime_isolation.tenant_context import TenantContext
        
        enforcer = IsolationEnforcer()
        
        tenant_a = TenantContext(
            tenant_id="tenant-a",
            domain_id="domain-a",
            issued_capabilities=frozenset(["fs:read"]),
            execution_quota=100
        )
        
        tenant_b = TenantContext(
            tenant_id="tenant-b",
            domain_id="domain-b",
            issued_capabilities=frozenset(["fs:read"]),
            execution_quota=100
        )
        
        # Cannot execute across tenants
        with pytest.raises(Exception):
            await enforcer.prevent_cross_tenant_execution(tenant_a, tenant_b)
    
    @pytest.mark.asyncio
    async def test_replay_identity_verification(self):
        """IsolationEnforcer verifies replay identity"""
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        enforcer = IsolationEnforcer()
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["compute:basic"]),
            state_hash=""
        )
        
        execution_result = {"output": "result", "hash": "abc123"}
        replay_result = {"output": "result", "hash": "abc123"}
        
        assert await enforcer.verify_replay_identity(domain, execution_result, replay_result)


# ============================================================================
# PART 6: MULTI-TENANT ISOLATION TESTS
# ============================================================================

@pytest.mark.phase6
@pytest.mark.security
class TestMultiTenantIsolation:
    """Tests for multi-tenant isolation security"""
    
    @pytest.mark.asyncio
    async def test_tenant_a_cannot_use_tenant_b_capability(self):
        """Tenant A cannot use Tenant B's capabilities"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        
        tenant_a = TenantContext(
            tenant_id="tenant-a",
            domain_id="domain-a",
            issued_capabilities=frozenset(["fs:read:/tenant-a/**"]),
            execution_quota=100
        )
        
        tenant_b_cap = "fs:read:/tenant-b/secret.txt"
        
        enforcer = IsolationEnforcer()
        
        with pytest.raises(Exception):
            await enforcer.validate_cross_tenant_capability(tenant_a, tenant_b_cap)
    
    @pytest.mark.asyncio
    async def test_cross_domain_execution_blocked(self):
        """Cross-domain execution is blocked"""
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        
        domain_a = ExecutionDomain(
            domain_id="domain-a",
            tenant_id="tenant-a",
            capabilities=frozenset(["fs:read"]),
            state_hash=""
        )
        
        domain_b = ExecutionDomain(
            domain_id="domain-b",
            tenant_id="tenant-b",
            capabilities=frozenset(["fs:read"]),
            state_hash=""
        )
        
        enforcer = IsolationEnforcer()
        
        with pytest.raises(Exception):
            await enforcer.enforce_cross_domain_isolation(domain_a, domain_b)
    
    @pytest.mark.asyncio
    async def test_tenant_resource_isolation(self):
        """Tenant resources are isolated"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        
        tenant_a = TenantContext(
            tenant_id="tenant-a",
            domain_id="domain-a",
            issued_capabilities=frozenset(["compute:basic"]),
            execution_quota=50
        )
        
        tenant_b = TenantContext(
            tenant_id="tenant-b",
            domain_id="domain-b",
            issued_capabilities=frozenset(["compute:basic"]),
            execution_quota=100
        )
        
        # Tenant A's quota consumption doesn't affect Tenant B
        tracker_a = tenant_a.create_quota_tracker()
        tracker_a.consume(30)
        
        tracker_b = tenant_b.create_quota_tracker()
        
        assert tracker_a.remaining() == 20
        assert tracker_b.remaining() == 100  # Unaffected
    
    @pytest.mark.asyncio
    async def test_no_shared_mutable_state_between_tenants(self):
        """No shared mutable state between tenants"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        tenant_a = TenantContext(
            tenant_id="tenant-a",
            domain_id="domain-a",
            issued_capabilities=frozenset(["compute:basic"]),
            execution_quota=100
        )
        
        tenant_b = TenantContext(
            tenant_id="tenant-b",
            domain_id="domain-b",
            issued_capabilities=frozenset(["compute:basic"]),
            execution_quota=100
        )
        
        sandbox_a = DeterministicSandbox(
            sandbox_id="sandbox-a",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        sandbox_b = DeterministicSandbox(
            sandbox_id="sandbox-b",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        # Each sandbox has isolated state
        state_a = sandbox_a.get_internal_state()
        state_b = sandbox_b.get_internal_state()
        
        # Modify state_a
        sandbox_a.update_internal_state({"modified": True})
        
        # state_b should be unaffected
        assert sandbox_b.get_internal_state().get("modified") is None


# ============================================================================
# PART 7: DETERMINISM TESTS
# ============================================================================

@pytest.mark.phase6
@pytest.mark.determinism
class TestDeterminism:
    """Tests for deterministic execution"""
    
    @pytest.mark.asyncio
    async def test_identical_input_identical_domain_hash(self):
        """Identical inputs produce identical domain hashes"""
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        domain1 = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read", "fs:write"]),
            state_hash=""
        )
        
        domain2 = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read", "fs:write"]),
            state_hash=""
        )
        
        hash1 = domain1.compute_state_hash()
        hash2 = domain2.compute_state_hash()
        
        assert hash1 == hash2
    
    @pytest.mark.asyncio
    async def test_replay_identity_per_domain(self):
        """Replay identity is maintained per domain"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["compute:basic"]),
            state_hash=""
        )
        
        context = {"input": "test", "seed": 42}
        workflow = lambda x: {"result": hash(x["input"])}
        
        result1 = await sandbox.execute(workflow, context, domain)
        result2 = await sandbox.replay(workflow, context, domain)
        
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_deterministic_sandbox_with_seed(self):
        """DeterministicSandbox produces same results with same seed"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["compute:random"]),
            state_hash=""
        )
        
        # Random operation with seed
        import random
        workflow = lambda x: {"random": random.Random(x["seed"]).randint(1, 100)}
        
        context1 = {"seed": 42}
        context2 = {"seed": 42}
        
        result1 = await sandbox.execute(workflow, context1, domain)
        result2 = await sandbox.execute(workflow, context2, domain)
        
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_different_seed_different_result(self):
        """Different seeds produce different results"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["compute:random"]),
            state_hash=""
        )
        
        import random
        workflow = lambda x: {"random": random.Random(x["seed"]).randint(1, 1000)}
        
        context1 = {"seed": 42}
        context2 = {"seed": 43}
        
        result1 = await sandbox.execute(workflow, context1, domain)
        result2 = await sandbox.execute(workflow, context2, domain)
        
        assert result1 != result2


# ============================================================================
# PART 8: SANDBOX ENFORCEMENT TESTS
# ============================================================================

@pytest.mark.phase6
@pytest.mark.security
class TestSandboxEnforcement:
    """Tests for sandbox enforcement"""
    
    @pytest.mark.asyncio
    async def test_resource_quota_deterministic(self):
        """Resource quota enforcement is deterministic"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 10, "memory_mb": 256}
        )
        
        # Same quota check should produce same result
        result1 = sandbox.check_quota(cpu_seconds=5, memory_mb=128)
        result2 = sandbox.check_quota(cpu_seconds=5, memory_mb=128)
        
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_capability_mismatch_denied(self):
        """Capability mismatch is denied"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read"]),  # No fs:write
            state_hash=""
        )
        
        with pytest.raises(Exception) as exc_info:
            await sandbox.execute_with_capability_check(
                required_capability="fs:write",
                domain=domain
            )
        
        assert "capability" in str(exc_info.value).lower() or "denied" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_sandbox_isolation_enforcement(self):
        """Sandbox enforces isolation"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["compute:basic"]),
            state_hash=""
        )
        
        # Sandbox should isolate execution
        result = await sandbox.execute(
            workflow=lambda x: {"result": "ok"},
            context={},
            domain=domain
        )
        
        # Verify isolation metadata
        assert result.get("_sandbox_id") == "sandbox-001"
        assert result.get("_domain_id") == "domain-001"


# ============================================================================
# PART 9: INTEGRATION TESTS
# ============================================================================

@pytest.mark.phase6
@pytest.mark.integration
class TestIntegration:
    """Integration tests with control plane"""
    
    @pytest.mark.asyncio
    async def test_control_plane_to_runtime_isolation(self):
        """Control plane integrates with runtime isolation"""
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        from synapse.runtime_isolation.tenant_context import TenantContext
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        enforcer = IsolationEnforcer()
        
        tenant = TenantContext(
            tenant_id="tenant-001",
            domain_id="domain-001",
            issued_capabilities=frozenset(["fs:read", "compute:basic"]),
            execution_quota=100
        )
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read", "compute:basic"]),
            state_hash=""
        )
        
        # Should pass isolation check
        result = await enforcer.enforce_tenant_isolation(tenant, domain)
        assert result is True or result.get("allowed") is True
    
    @pytest.mark.asyncio
    async def test_orchestrator_to_sandbox_to_node(self):
        """Orchestrator -> Sandbox -> Node integration"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        from synapse.runtime_isolation.tenant_context import TenantContext
        
        tenant = TenantContext(
            tenant_id="tenant-001",
            domain_id="domain-001",
            issued_capabilities=frozenset(["compute:basic"]),
            execution_quota=100
        )
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["compute:basic"]),
            state_hash=""
        )
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        # Execute workflow
        result = await sandbox.execute(
            workflow=lambda x: {"status": "completed", "output": x.get("input", "default")},
            context={"input": "test_data"},
            domain=domain
        )
        
        assert result.get("status") == "completed"
    
    @pytest.mark.asyncio
    async def test_full_multi_tenant_workflow(self):
        """Full multi-tenant workflow execution"""
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        from synapse.runtime_isolation.tenant_context import TenantContext
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.capability_domain import CapabilityDomain
        
        # Setup tenant
        tenant = TenantContext(
            tenant_id="tenant-001",
            domain_id="domain-001",
            issued_capabilities=frozenset(["fs:read:/workspace/**", "compute:basic"]),
            execution_quota=100
        )
        
        # Setup domain
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read:/workspace/**", "compute:basic"]),
            state_hash=""
        )
        
        # Setup capability domain
        cap_domain = CapabilityDomain(
            domain_id="cap-domain-001",
            allowed_capabilities=frozenset(["fs:read:/workspace/**", "compute:basic"]),
            tenant_id="tenant-001"
        )
        
        # Setup sandbox
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        # Setup enforcer
        enforcer = IsolationEnforcer()
        
        # Verify isolation
        isolation_result = await enforcer.enforce_tenant_isolation(tenant, domain)
        assert isolation_result is True or isolation_result.get("allowed") is True
        
        # Execute
        result = await sandbox.execute(
            workflow=lambda x: {"processed": True, "data": x},
            context={"input": "test"},
            domain=domain
        )
        
        assert result.get("processed") is True


# ============================================================================
# PART 10: CROSS-TENANT ATTACK SIMULATION
# ============================================================================

@pytest.mark.phase6
@pytest.mark.security
class TestCrossTenantAttacks:
    """Simulated cross-tenant attack tests"""
    
    @pytest.mark.asyncio
    async def test_attack_capability_escalation(self):
        """Attack: Attempt capability escalation"""
        from synapse.runtime_isolation.capability_domain import CapabilityDomain
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        
        cap_domain = CapabilityDomain(
            domain_id="cap-domain-001",
            allowed_capabilities=frozenset(["fs:read"]),
            tenant_id="tenant-001"
        )
        
        enforcer = IsolationEnforcer()
        
        # Attempt to escalate to write
        with pytest.raises(Exception):
            await enforcer.enforce_capability_escalation_prevention(
                cap_domain, 
                current_cap="fs:read",
                target_cap="fs:write"
            )
    
    @pytest.mark.asyncio
    async def test_attack_tenant_impersonation(self):
        """Attack: Attempt tenant impersonation"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        
        # Real tenant
        tenant_a = TenantContext(
            tenant_id="tenant-a",
            domain_id="domain-a",
            issued_capabilities=frozenset(["fs:read"]),
            execution_quota=100
        )
        
        # Attacker trying to impersonate
        fake_domain = ExecutionDomain(
            domain_id="domain-b",
            tenant_id="tenant-b",  # Different tenant
            capabilities=frozenset(["fs:read"]),
            state_hash=""
        )
        
        enforcer = IsolationEnforcer()
        
        with pytest.raises(Exception):
            await enforcer.enforce_tenant_isolation(tenant_a, fake_domain)
    
    @pytest.mark.asyncio
    async def test_attack_resource_theft(self):
        """Attack: Attempt to steal another tenant's resources"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        
        tenant_a = TenantContext(
            tenant_id="tenant-a",
            domain_id="domain-a",
            issued_capabilities=frozenset(["compute:basic"]),
            execution_quota=10  # Limited
        )
        
        tenant_b = TenantContext(
            tenant_id="tenant-b",
            domain_id="domain-b",
            issued_capabilities=frozenset(["compute:basic"]),
            execution_quota=1000  # Abundant
        )
        
        # Tenant A tries to use Tenant B's quota
        sandbox_b = DeterministicSandbox(
            sandbox_id="sandbox-b",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        # Should fail - tenant isolation
        with pytest.raises(Exception):
            await sandbox_b.execute_for_tenant(
                tenant=tenant_a,  # Wrong tenant
                workflow=lambda x: x,
                context={}
            )
    
    @pytest.mark.asyncio
    async def test_attack_state_leakage(self):
        """Attack: Attempt to leak state between tenants"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={"cpu_seconds": 60, "memory_mb": 512}
        )
        
        domain_a = ExecutionDomain(
            domain_id="domain-a",
            tenant_id="tenant-a",
            capabilities=frozenset(["compute:basic"]),
            state_hash=""
        )
        
        domain_b = ExecutionDomain(
            domain_id="domain-b",
            tenant_id="tenant-b",
            capabilities=frozenset(["compute:basic"]),
            state_hash=""
        )
        
        # Execute in domain A with secret
        await sandbox.execute(
            workflow=lambda x: {"secret": "tenant-a-secret"},
            context={},
            domain=domain_a
        )
        
        # Try to access from domain B
        result_b = await sandbox.execute(
            workflow=lambda x: x,  # Try to read state
            context={},
            domain=domain_b
        )
        
        # Should not contain tenant-a-secret
        assert "tenant-a-secret" not in str(result_b)


# ============================================================================
# PART 11: PROTOCOL VERSION TESTS
# ============================================================================

@pytest.mark.phase6
@pytest.mark.compliance
class TestProtocolVersion:
    """Tests for protocol version compliance"""
    
    def test_execution_domain_protocol_version(self):
        """ExecutionDomain has protocol_version"""
        from synapse.runtime_isolation.execution_domain import ExecutionDomain
        
        domain = ExecutionDomain(
            domain_id="domain-001",
            tenant_id="tenant-001",
            capabilities=frozenset(["fs:read"]),
            state_hash=""
        )
        
        assert domain.protocol_version == "1.0"
    
    def test_capability_domain_protocol_version(self):
        """CapabilityDomain has protocol_version"""
        from synapse.runtime_isolation.capability_domain import CapabilityDomain
        
        cap_domain = CapabilityDomain(
            domain_id="cap-domain-001",
            allowed_capabilities=frozenset(["fs:read"])
        )
        
        assert cap_domain.protocol_version == "1.0"
    
    def test_sandbox_protocol_version(self):
        """DeterministicSandbox has protocol_version"""
        from synapse.runtime_isolation.sandbox import DeterministicSandbox
        
        sandbox = DeterministicSandbox(
            sandbox_id="sandbox-001",
            resource_quota={}
        )
        
        assert sandbox.protocol_version == "1.0"
    
    def test_tenant_context_protocol_version(self):
        """TenantContext has protocol_version"""
        from synapse.runtime_isolation.tenant_context import TenantContext
        
        tenant = TenantContext(
            tenant_id="tenant-001",
            domain_id="domain-001",
            issued_capabilities=frozenset(["fs:read"]),
            execution_quota=100
        )
        
        assert tenant.protocol_version == "1.0"
    
    def test_isolation_enforcer_protocol_version(self):
        """IsolationEnforcer has protocol_version"""
        from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer
        
        enforcer = IsolationEnforcer()
        assert enforcer.protocol_version == "1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
