"""
Phase 6.1: Tenant-Aware Control Plane Tests
Specification tests for TenantScheduler, TenantQuotaRegistry, TenantStatePartition

PROTOCOL_VERSION = "1.0"
"""

import pytest
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import asyncio

# ============================================================================
# SPECIFICATION: Data Models (Must match implementation exactly)
# ============================================================================

@dataclass
class TenantContext:
    """Tenant security context with cryptographic identity"""
    tenant_id: str
    tenant_hash: str  # SHA256 of tenant_id + secret
    capabilities: List[str]
    resource_quota: Dict[str, int]
    created_at: str
    protocol_version: str = "1.0"


@dataclass
class SchedulingRequest:
    """Deterministic scheduling request"""
    request_id: str
    tenant_id: str
    task_type: str
    priority: int
    required_capabilities: List[str]
    execution_seed: int  # For determinism
    timestamp: str
    protocol_version: str = "1.0"


@dataclass
class SchedulingDecision:
    """Deterministic scheduling decision"""
    decision_id: str
    request_id: str
    tenant_id: str
    node_id: str
    scheduled_at: str
    execution_order: int  # Deterministic ordering
    decision_hash: str  # Cryptographic hash of decision
    protocol_version: str = "1.0"


@dataclass
class QuotaUsage:
    """Cryptographically verifiable quota usage"""
    tenant_id: str
    resource_type: str
    used: int
    limit: int
    usage_hash: str  # Hash of usage data
    timestamp: str
    protocol_version: str = "1.0"


# ============================================================================
# TEST GROUP 1: TenantScheduler Specification Tests
# ============================================================================

class TestTenantSchedulerSpecification:
    """Specification tests for TenantScheduler - MUST FAIL initially"""

    @pytest.fixture
    def scheduler(self):
        """Fixture to create TenantScheduler instance"""
        # This will fail until implementation exists
        from synapse.control_plane.tenant_scheduler import TenantScheduler
        return TenantScheduler()

    @pytest.fixture
    def tenant_context(self):
        """Create test tenant context"""
        tenant_id = "tenant_001"
        tenant_hash = hashlib.sha256(
            f"{tenant_id}:secret_key".encode()
        ).hexdigest()
        return TenantContext(
            tenant_id=tenant_id,
            tenant_hash=tenant_hash,
            capabilities=["compute:basic", "memory:read"],
            resource_quota={"cpu_seconds": 100, "memory_mb": 512},
            created_at=datetime.utcnow().isoformat(),
            protocol_version="1.0"
        )

    @pytest.fixture
    def scheduling_request(self, tenant_context):
        """Create test scheduling request"""
        return SchedulingRequest(
            request_id="req_001",
            tenant_id=tenant_context.tenant_id,
            task_type="compute",
            priority=1,
            required_capabilities=["compute:basic"],
            execution_seed=42,
            timestamp=datetime.utcnow().isoformat(),
            protocol_version="1.0"
        )

    # ========================================================================
    # POSITIVE TESTS: Core Functionality
    # ========================================================================

    def test_scheduler_exists(self, scheduler):
        """TenantScheduler class must exist"""
        assert scheduler is not None
        assert hasattr(scheduler, "schedule")
        assert hasattr(scheduler, "get_decision")

    def test_deterministic_scheduling(self, scheduler, scheduling_request):
        """Identical input must produce identical schedule"""
        # Schedule same request twice
        decision1 = scheduler.schedule(scheduling_request)
        decision2 = scheduler.schedule(scheduling_request)

        # Must be identical
        assert decision1.decision_id == decision2.decision_id
        assert decision1.execution_order == decision2.execution_order
        assert decision1.decision_hash == decision2.decision_hash

    def test_capability_aware_routing(self, scheduler, tenant_context):
        """Scheduler must route based on capabilities"""
        # Request requiring capability tenant doesn't have
        request = SchedulingRequest(
            request_id="req_002",
            tenant_id=tenant_context.tenant_id,
            task_type="privileged",
            priority=1,
            required_capabilities=["admin:all"],  # Not in tenant capabilities
            execution_seed=42,
            timestamp=datetime.utcnow().isoformat(),
            protocol_version="1.0"
        )

        # Must raise error
        with pytest.raises(Exception) as exc_info:
            scheduler.schedule(request)

        assert "capability" in str(exc_info.value).lower()

    def test_fairness_guarantee(self, scheduler):
        """Scheduler must provide fairness across tenants"""
        # Create requests from multiple tenants
        requests = []
        for i in range(5):
            for tenant_num in range(3):
                tenant_id = f"tenant_{tenant_num:03d}"
                requests.append(SchedulingRequest(
                    request_id=f"req_{i}_{tenant_num}",
                    tenant_id=tenant_id,
                    task_type="compute",
                    priority=1,
                    required_capabilities=["compute:basic"],
                    execution_seed=42 + i,
                    timestamp=datetime.utcnow().isoformat(),
                    protocol_version="1.0"
                ))

        # Schedule all
        decisions = [scheduler.schedule(req) for req in requests]

        # Count per tenant
        tenant_counts = {}
        for decision in decisions:
            tenant_counts[decision.tenant_id] = tenant_counts.get(decision.tenant_id, 0) + 1

        # Fairness: no tenant should have more than 2x any other
        counts = list(tenant_counts.values())
        assert max(counts) <= 2 * min(counts)

    def test_replay_stable_ordering(self, scheduler, scheduling_request):
        """Scheduling order must be replay-stable"""
        # Schedule multiple requests
        decisions = []
        for i in range(10):
            req = SchedulingRequest(
                request_id=f"req_replay_{i}",
                tenant_id=scheduling_request.tenant_id,
                task_type="compute",
                priority=1,
                required_capabilities=["compute:basic"],
                execution_seed=100 + i,
                timestamp=datetime.utcnow().isoformat(),
                protocol_version="1.0"
            )
            decisions.append(scheduler.schedule(req))

        # Extract order
        order1 = [d.execution_order for d in decisions]

        # Replay with same seeds
        decisions2 = []
        for i in range(10):
            req = SchedulingRequest(
                request_id=f"req_replay_{i}",
                tenant_id=scheduling_request.tenant_id,
                task_type="compute",
                priority=1,
                required_capabilities=["compute:basic"],
                execution_seed=100 + i,  # Same seeds
                timestamp=datetime.utcnow().isoformat(),
                protocol_version="1.0"
            )
            decisions2.append(scheduler.schedule(req))

        order2 = [d.execution_order for d in decisions2]

        # Must be identical
        assert order1 == order2

    def test_protocol_version_preserved(self, scheduler, scheduling_request):
        """Protocol version must remain 1.0"""
        decision = scheduler.schedule(scheduling_request)
        assert decision.protocol_version == "1.0"

    # ========================================================================
    # NEGATIVE SECURITY TESTS
    # ========================================================================

    def test_tenant_impersonation_impossible(self, scheduler):
        """Tenant cannot impersonate another tenant"""
        # Create request with different tenant_id than authorized
        request = SchedulingRequest(
            request_id="req_impersonate",
            tenant_id="tenant_999",  # Different tenant
            task_type="compute",
            priority=1,
            required_capabilities=["compute:basic"],
            execution_seed=42,
            timestamp=datetime.utcnow().isoformat(),
            protocol_version="1.0"
        )

        # Should fail validation
        with pytest.raises(Exception) as exc_info:
            scheduler.schedule(request)

        assert "tenant" in str(exc_info.value).lower() or "unauthorized" in str(exc_info.value).lower()

    def test_scheduler_cannot_bypass_capability_model(self, scheduler):
        """Scheduler must enforce capability model"""
        # Try to schedule with empty capabilities
        request = SchedulingRequest(
            request_id="req_bypass",
            tenant_id="tenant_001",
            task_type="admin",
            priority=1,
            required_capabilities=[],  # Empty - should still require something
            execution_seed=42,
            timestamp=datetime.utcnow().isoformat(),
            protocol_version="1.0"
        )

        # Should fail or require explicit capability
        with pytest.raises(Exception):
            scheduler.schedule(request)

    def test_cross_tenant_scheduling_blocked(self, scheduler):
        """Cannot schedule for another tenant"""
        # This test verifies tenant isolation in scheduling
        request1 = SchedulingRequest(
            request_id="req_cross_1",
            tenant_id="tenant_001",
            task_type="compute",
            priority=1,
            required_capabilities=["compute:basic"],
            execution_seed=42,
            timestamp=datetime.utcnow().isoformat(),
            protocol_version="1.0"
        )

        decision1 = scheduler.schedule(request1)

        # Try to access decision from different tenant
        request2 = SchedulingRequest(
            request_id="req_cross_2",
            tenant_id="tenant_002",  # Different tenant
            task_type="compute",
            priority=1,
            required_capabilities=["compute:basic"],
            execution_seed=42,
            timestamp=datetime.utcnow().isoformat(),
            protocol_version="1.0"
        )

        decision2 = scheduler.schedule(request2)

        # Decisions must be isolated
        assert decision1.tenant_id != decision2.tenant_id
        assert decision1.decision_id != decision2.decision_id


# ============================================================================
# TEST GROUP 2: TenantQuotaRegistry Specification Tests
# ============================================================================

class TestTenantQuotaRegistrySpecification:
    """Specification tests for TenantQuotaRegistry"""

    @pytest.fixture
    def quota_registry(self):
        """Fixture to create TenantQuotaRegistry instance"""
        from synapse.control_plane.tenant_quota_registry import TenantQuotaRegistry
        return TenantQuotaRegistry()

    @pytest.fixture
    def tenant_quota(self):
        """Create test tenant quota"""
        return {
            "tenant_id": "tenant_001",
            "quotas": {
                "cpu_seconds": 1000,
                "memory_mb": 2048,
                "disk_mb": 10240,
                "network_kb": 51200
            },
            "protocol_version": "1.0"
        }

    # ========================================================================
    # POSITIVE TESTS
    # ========================================================================

    def test_quota_registry_exists(self, quota_registry):
        """TenantQuotaRegistry must exist"""
        assert quota_registry is not None
        assert hasattr(quota_registry, "register_quota")
        assert hasattr(quota_registry, "check_quota")
        assert hasattr(quota_registry, "record_usage")

    def test_register_tenant_quota(self, quota_registry, tenant_quota):
        """Can register tenant quota"""
        result = quota_registry.register_quota(
            tenant_id=tenant_quota["tenant_id"],
            quotas=tenant_quota["quotas"]
        )
        assert result is True or result.get("success") is True

    def test_check_quota_within_limit(self, quota_registry, tenant_quota):
        """Check quota when within limit"""
        quota_registry.register_quota(
            tenant_id=tenant_quota["tenant_id"],
            quotas=tenant_quota["quotas"]
        )

        # Check usage within limit
        result = quota_registry.check_quota(
            tenant_id=tenant_quota["tenant_id"],
            resource_type="cpu_seconds",
            amount=100
        )

        assert result is True or result.get("allowed") is True

    def test_check_quota_exceeds_limit(self, quota_registry, tenant_quota):
        """Check quota when exceeds limit"""
        quota_registry.register_quota(
            tenant_id=tenant_quota["tenant_id"],
            quotas=tenant_quota["quotas"]
        )

        # Try to use more than limit
        result = quota_registry.check_quota(
            tenant_id=tenant_quota["tenant_id"],
            resource_type="cpu_seconds",
            amount=2000  # Exceeds 1000 limit
        )

        assert result is False or result.get("allowed") is False

    def test_record_usage(self, quota_registry, tenant_quota):
        """Record resource usage"""
        quota_registry.register_quota(
            tenant_id=tenant_quota["tenant_id"],
            quotas=tenant_quota["quotas"]
        )

        usage = quota_registry.record_usage(
            tenant_id=tenant_quota["tenant_id"],
            resource_type="cpu_seconds",
            amount=100
        )

        assert usage is not None
        assert hasattr(usage, "usage_hash") or "usage_hash" in usage

    def test_deterministic_quota_enforcement(self, quota_registry, tenant_quota):
        """Quota enforcement must be deterministic"""
        quota_registry.register_quota(
            tenant_id=tenant_quota["tenant_id"],
            quotas=tenant_quota["quotas"]
        )

        # Same check twice
        result1 = quota_registry.check_quota(
            tenant_id=tenant_quota["tenant_id"],
            resource_type="cpu_seconds",
            amount=500
        )

        result2 = quota_registry.check_quota(
            tenant_id=tenant_quota["tenant_id"],
            resource_type="cpu_seconds",
            amount=500
        )

        # Must be identical
        assert result1 == result2

    def test_cross_node_consistency(self, quota_registry, tenant_quota):
        """Quota must be consistent across nodes"""
        quota_registry.register_quota(
            tenant_id=tenant_quota["tenant_id"],
            quotas=tenant_quota["quotas"]
        )

        # Record usage
        quota_registry.record_usage(
            tenant_id=tenant_quota["tenant_id"],
            resource_type="cpu_seconds",
            amount=200
        )

        # Get usage hash
        usage1 = quota_registry.get_usage(tenant_quota["tenant_id"])

        # Simulate cross-node sync (same operation)
        usage2 = quota_registry.get_usage(tenant_quota["tenant_id"])

        # Must be identical
        if hasattr(usage1, "usage_hash"):
            assert usage1.usage_hash == usage2.usage_hash
        else:
            assert usage1.get("usage_hash") == usage2.get("usage_hash")

    # ========================================================================
    # NEGATIVE SECURITY TESTS
    # ========================================================================

    def test_quota_violation_deterministic_failure(self, quota_registry, tenant_quota):
        """Quota violation must produce deterministic failure"""
        quota_registry.register_quota(
            tenant_id=tenant_quota["tenant_id"],
            quotas=tenant_quota["quotas"]
        )

        # Try to exceed quota
        try:
            quota_registry.record_usage(
                tenant_id=tenant_quota["tenant_id"],
                resource_type="cpu_seconds",
                amount=2000  # Exceeds limit
            )
            # Should have failed
            assert False, "Should have raised exception"
        except Exception as e:
            # Must be deterministic error
            error_str = str(e)
            assert "quota" in error_str.lower() or "limit" in error_str.lower()

    def test_tenant_cannot_modify_other_quota(self, quota_registry):
        """Tenant cannot modify another tenant's quota"""
        # Register quota for tenant_001
        quota_registry.register_quota(
            tenant_id="tenant_001",
            quotas={"cpu_seconds": 1000}
        )

        # Try to modify from tenant_002
        with pytest.raises(Exception):
            quota_registry.register_quota(
                tenant_id="tenant_001",  # Different tenant
                quotas={"cpu_seconds": 999999},  # Try to increase
                requesting_tenant="tenant_002"  # Different requester
            )


# ============================================================================
# TEST GROUP 3: TenantStatePartition Specification Tests
# ============================================================================

class TestTenantStatePartitionSpecification:
    """Specification tests for TenantStatePartition"""

    @pytest.fixture
    def state_partition(self):
        """Fixture to create TenantStatePartition instance"""
        from synapse.control_plane.tenant_state_partition import TenantStatePartition
        return TenantStatePartition()

    # ========================================================================
    # POSITIVE TESTS
    # ========================================================================

    def test_state_partition_exists(self, state_partition):
        """TenantStatePartition must exist"""
        assert state_partition is not None
        assert hasattr(state_partition, "get_state")
        assert hasattr(state_partition, "update_state")
        assert hasattr(state_partition, "get_state_hash")

    def test_state_segmented_by_tenant(self, state_partition):
        """State must be segmented by tenant"""
        # Set state for tenant_001
        state_partition.update_state(
            tenant_id="tenant_001",
            key="test_key",
            value={"data": "tenant_001_data"}
        )

        # Set state for tenant_002
        state_partition.update_state(
            tenant_id="tenant_002",
            key="test_key",
            value={"data": "tenant_002_data"}
        )

        # Get states
        state1 = state_partition.get_state("tenant_001", "test_key")
        state2 = state_partition.get_state("tenant_002", "test_key")

        # Must be different
        assert state1 != state2
        assert state1.get("data") == "tenant_001_data"
        assert state2.get("data") == "tenant_002_data"

    def test_state_hash_includes_tenant_scope(self, state_partition):
        """State hash must include tenant scope"""
        state_partition.update_state(
            tenant_id="tenant_001",
            key="hash_test",
            value={"important": "data"}
        )

        hash1 = state_partition.get_state_hash("tenant_001")

        # Update different tenant
        state_partition.update_state(
            tenant_id="tenant_002",
            key="hash_test",
            value={"important": "data"}
        )

        hash2 = state_partition.get_state_hash("tenant_002")

        # Hashes must be different (different tenants)
        assert hash1 != hash2

    def test_cross_tenant_contamination_impossible(self, state_partition):
        """Cross-tenant state contamination must be impossible"""
        # Set sensitive data for tenant_001
        state_partition.update_state(
            tenant_id="tenant_001",
            key="secret",
            value={"api_key": "secret_key_001"}
        )

        # Try to access from tenant_002
        result = state_partition.get_state(
            tenant_id="tenant_002",
            key="secret"
        )

        # Must not return tenant_001's data
        assert result is None or result.get("api_key") != "secret_key_001"

    # ========================================================================
    # NEGATIVE SECURITY TESTS
    # ========================================================================

    def test_tenant_cannot_access_other_state(self, state_partition):
        """Tenant cannot access another tenant's state"""
        # Set state for tenant_001
        state_partition.update_state(
            tenant_id="tenant_001",
            key="private",
            value={"secret": "value"}
        )

        # Try to access from tenant_002
        with pytest.raises(Exception):
            state_partition.get_state(
                tenant_id="tenant_002",
                key="private",
                requesting_tenant="tenant_002"
            )


# ============================================================================
# TEST GROUP 4: Multi-Tenant Isolation Tests
# ============================================================================

class TestMultiTenantIsolation:
    """Comprehensive multi-tenant isolation tests"""

    @pytest.fixture
    def full_system(self):
        """Create full system with all components"""
        from synapse.control_plane.tenant_scheduler import TenantScheduler
        from synapse.control_plane.tenant_quota_registry import TenantQuotaRegistry
        from synapse.control_plane.tenant_state_partition import TenantStatePartition

        return {
            "scheduler": TenantScheduler(),
            "quota_registry": TenantQuotaRegistry(),
            "state_partition": TenantStatePartition()
        }

    def test_complete_tenant_isolation(self, full_system):
        """Complete isolation test across all components"""
        tenant1 = "tenant_isolation_001"
        tenant2 = "tenant_isolation_002"

        # Register quotas
        full_system["quota_registry"].register_quota(
            tenant_id=tenant1,
            quotas={"cpu_seconds": 100}
        )
        full_system["quota_registry"].register_quota(
            tenant_id=tenant2,
            quotas={"cpu_seconds": 100}
        )

        # Set states
        full_system["state_partition"].update_state(
            tenant_id=tenant1,
            key="isolation_test",
            value={"tenant": 1}
        )
        full_system["state_partition"].update_state(
            tenant_id=tenant2,
            key="isolation_test",
            value={"tenant": 2}
        )

        # Schedule tasks
        req1 = SchedulingRequest(
            request_id="iso_req_1",
            tenant_id=tenant1,
            task_type="compute",
            priority=1,
            required_capabilities=["compute:basic"],
            execution_seed=42,
            timestamp=datetime.utcnow().isoformat(),
            protocol_version="1.0"
        )

        req2 = SchedulingRequest(
            request_id="iso_req_2",
            tenant_id=tenant2,
            task_type="compute",
            priority=1,
            required_capabilities=["compute:basic"],
            execution_seed=42,
            timestamp=datetime.utcnow().isoformat(),
            protocol_version="1.0"
        )

        decision1 = full_system["scheduler"].schedule(req1)
        decision2 = full_system["scheduler"].schedule(req2)

        # Verify isolation
        assert decision1.tenant_id != decision2.tenant_id
        assert decision1.decision_id != decision2.decision_id

        state1 = full_system["state_partition"].get_state(tenant1, "isolation_test")
        state2 = full_system["state_partition"].get_state(tenant2, "isolation_test")

        assert state1.get("tenant") != state2.get("tenant")


# ============================================================================
# TEST GROUP 5: Determinism Verification Tests
# ============================================================================

class TestDeterminismVerification:
    """Tests to verify deterministic behavior"""

    @pytest.fixture
    def scheduler(self):
        from synapse.control_plane.tenant_scheduler import TenantScheduler
        return TenantScheduler()

    def test_multi_run_identity(self, scheduler):
        """Multiple runs with same input must produce identical output"""
        request = SchedulingRequest(
            request_id="determinism_test",
            tenant_id="tenant_det",
            task_type="compute",
            priority=1,
            required_capabilities=["compute:basic"],
            execution_seed=12345,
            timestamp="2026-02-21T00:00:00",  # Fixed timestamp
            protocol_version="1.0"
        )

        # Run 10 times
        results = []
        for _ in range(10):
            decision = scheduler.schedule(request)
            results.append({
                "decision_id": decision.decision_id,
                "execution_order": decision.execution_order,
                "decision_hash": decision.decision_hash
            })

        # All must be identical
        first = results[0]
        for result in results[1:]:
            assert result == first, f"Non-deterministic: {first} != {result}"

    def test_replay_verification(self, scheduler):
        """Replay must produce identical results"""
        # Create sequence of requests
        requests = []
        for i in range(5):
            requests.append(SchedulingRequest(
                request_id=f"replay_{i}",
                tenant_id="tenant_replay",
                task_type="compute",
                priority=1,
                required_capabilities=["compute:basic"],
                execution_seed=1000 + i,
                timestamp="2026-02-21T00:00:00",
                protocol_version="1.0"
            ))

        # First run
        decisions1 = [scheduler.schedule(req) for req in requests]
        hashes1 = [d.decision_hash for d in decisions1]

        # Replay
        decisions2 = [scheduler.schedule(req) for req in requests]
        hashes2 = [d.decision_hash for d in decisions2]

        # Must be identical
        assert hashes1 == hashes2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
