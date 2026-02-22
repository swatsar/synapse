"""
Integration Tests for Phase 6.1
"""

import pytest
import hashlib
import json
from datetime import datetime

from synapse.control_plane.tenant_scheduler import TenantScheduler
from synapse.control_plane.tenant_quota_registry import TenantQuotaRegistry
from synapse.control_plane.tenant_state_partition import TenantStatePartition
from synapse.audit.tenant_audit_chain import TenantAuditChain, AuditHashTree
from synapse.runtime.sandbox_interface import (
    SandboxRegistry,
    ProcessSandbox,
    ExecutionContract
)
from synapse.runtime_api.deterministic_runtime_api import (
    DeterministicRuntimeAPI,
    ExecutionDomain
)
from synapse.capability.domain_registry import (
    DomainRegistry,
    CapabilityDescriptor,
    DependencyType
)


class TestPhase61Integration:
    """Integration tests for Phase 6.1"""

    @pytest.mark.asyncio
    async def test_full_tenant_workflow(self):
        """Full tenant workflow integration"""
        # 1. Setup components
        scheduler = TenantScheduler()
        quota_registry = TenantQuotaRegistry()
        state_partition = TenantStatePartition()
        audit_chain = TenantAuditChain()
        audit_tree = AuditHashTree()
        sandbox_registry = SandboxRegistry()
        runtime_api = DeterministicRuntimeAPI()
        domain_registry = DomainRegistry()

        # 2. Register sandbox
        sandbox = ProcessSandbox()
        sandbox_registry.register(sandbox, is_default=True)

        # 3. Register tenant
        tenant_id = "tenant_integration"
        quota_registry.register_tenant(
            tenant_id=tenant_id,
            quotas={"cpu_seconds": 100, "memory_mb": 512}
        )

        # 4. Create execution contract
        contract = runtime_api.create_contract(
            tenant_id=tenant_id,
            capability_set=["fs:read"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={"memory_mb": 256},
            deterministic_seed=42
        )

        # 5. Register function
        def test_func(x: int) -> int:
            return x * 2

        runtime_api.register_function(
            name="double",
            func=test_func,
            required_capabilities=[]
        )

        # 6. Execute
        result = await runtime_api.call(
            contract_id=contract.contract_id,
            function_name="double",
            arguments={"x": 21}
        )

        # 7. Record audit
        audit_chain.append(
            tenant_id=tenant_id,
            event_type="execution",
            event_data={
                "function": "double",
                "success": result.success
            }
        )

        # 8. Update audit tree
        audit_tree.add_tenant_leaf("cluster_1", tenant_id, audit_chain)

        # 9. Verify
        assert result.success == True
        assert result.output == 42
        assert audit_chain.verify_chain(tenant_id) == True

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self):
        """Multi-tenant isolation integration"""
        # Setup
        scheduler = TenantScheduler()
        quota_registry = TenantQuotaRegistry()
        state_partition = TenantStatePartition()
        audit_chain = TenantAuditChain()

        tenants = ["tenant_a", "tenant_b", "tenant_c"]

        # Register tenants
        for tenant_id in tenants:
            quota_registry.register_tenant(
                tenant_id=tenant_id,
                quotas={"cpu_seconds": 100}
            )

        # Execute for each tenant
        for tenant_id in tenants:
            # Record usage
            quota_registry.record_usage(
                tenant_id=tenant_id,
                resource_type="cpu_seconds",
                amount=10
            )

            # Record audit
            audit_chain.append(
                tenant_id=tenant_id,
                event_type="execution",
                event_data={"tenant": tenant_id}
            )

            # Update state
            state_partition.update_state(
                tenant_id=tenant_id,
                state_key="last_execution",
                state_value=datetime.utcnow().isoformat()
            )

        # Verify isolation
        for tenant_id in tenants:
            # Check quota
            quota = quota_registry.get_tenant_quota(tenant_id)
            assert quota["cpu_seconds"]["used"] == 10

            # Check audit
            chain = audit_chain.get_chain(tenant_id)
            assert len(chain) == 1
            assert chain[0].tenant_id == tenant_id

            # Check state
            state = state_partition.get_tenant_state(tenant_id)
            assert "last_execution" in state

    @pytest.mark.asyncio
    async def test_deterministic_replay(self):
        """Deterministic replay integration"""
        # Setup
        runtime_api = DeterministicRuntimeAPI()
        sandbox_registry = SandboxRegistry()
        sandbox = ProcessSandbox()
        sandbox_registry.register(sandbox)

        # Register function
        def compute(x: int, y: int) -> int:
            return x + y

        runtime_api.register_function(
            name="add",
            func=compute,
            required_capabilities=[]
        )

        # Create contract
        contract = runtime_api.create_contract(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        # Execute
        result1 = await runtime_api.call(
            contract_id=contract.contract_id,
            function_name="add",
            arguments={"x": 10, "y": 20}
        )

        # Replay
        result2 = await runtime_api.call(
            contract_id=contract.contract_id,
            function_name="add",
            arguments={"x": 10, "y": 20}
        )

        # Verify identical
        assert result1.output == result2.output
        assert result1.result_hash == result2.result_hash

    @pytest.mark.asyncio
    async def test_capability_enforcement_integration(self):
        """Capability enforcement integration"""
        # Setup
        runtime_api = DeterministicRuntimeAPI()
        domain_registry = DomainRegistry()

        # Register capability
        cap = CapabilityDescriptor.create(
            name="math:basic",
            version="1.0.0",
            domain="math",
            description="Basic math operations",
            permissions=["add", "subtract"]
        )
        domain_registry.register(cap)

        # Register function requiring capability
        def add(x: int, y: int) -> int:
            return x + y

        runtime_api.register_function(
            name="add",
            func=add,
            required_capabilities=["math:basic"]
        )

        # Create contract WITH capability
        contract_with = runtime_api.create_contract(
            tenant_id="tenant_1",
            capability_set=["math:basic"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        # Execute - should succeed
        result = await runtime_api.call(
            contract_id=contract_with.contract_id,
            function_name="add",
            arguments={"x": 5, "y": 10}
        )

        assert result.success == True

        # Create contract WITHOUT capability
        contract_without = runtime_api.create_contract(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        # Execute - should fail
        with pytest.raises(PermissionError):
            await runtime_api.call(
                contract_id=contract_without.contract_id,
                function_name="add",
                arguments={"x": 5, "y": 10}
            )

    @pytest.mark.asyncio
    async def test_audit_chain_integrity(self):
        """Audit chain integrity integration"""
        # Setup
        audit_chain = TenantAuditChain()
        audit_tree = AuditHashTree()

        # Add multiple entries
        for i in range(10):
            audit_chain.append(
                tenant_id="tenant_1",
                event_type=f"event_{i}",
                event_data={"index": i}
            )

        # Verify chain
        assert audit_chain.verify_chain("tenant_1") == True

        # Add to tree
        audit_tree.add_tenant_leaf("cluster_1", "tenant_1", audit_chain)

        # Get root
        root = audit_tree.get_root("cluster_1")

        # Verify root is deterministic
        root2 = audit_tree.get_root("cluster_1")
        assert root == root2

    @pytest.mark.asyncio
    async def test_quota_enforcement_integration(self):
        """Quota enforcement integration"""
        # Setup
        quota_registry = TenantQuotaRegistry()
        audit_chain = TenantAuditChain()

        # Register tenant with limited quota
        quota_registry.register_tenant(
            tenant_id="tenant_limited",
            quotas={"cpu_seconds": 50}
        )

        # Use quota
        for i in range(5):
            result = quota_registry.record_usage(
                tenant_id="tenant_limited",
                resource_type="cpu_seconds",
                amount=10
            )

            # Record audit
            audit_chain.append(
                tenant_id="tenant_limited",
                event_type="usage",
                event_data={"amount": 10, "success": result}
            )

        # Check quota exceeded
        check = quota_registry.check_quota(
            tenant_id="tenant_limited",
            resource_type="cpu_seconds",
            amount=1
        )

        assert check == False

        # Verify audit
        chain = audit_chain.get_chain("tenant_limited")
        assert len(chain) == 5


class TestPhase61SecurityIntegration:
    """Security integration tests for Phase 6.1"""

    @pytest.mark.asyncio
    async def test_cross_tenant_attack_prevention(self):
        """Cross-tenant attack prevention"""
        # Setup
        audit_chain = TenantAuditChain()
        state_partition = TenantStatePartition()

        # Tenant A tries to access Tenant B data
        audit_chain.append(
            tenant_id="tenant_a",
            event_type="access_attempt",
            event_data={"target": "tenant_b"}
        )

        # Verify Tenant A cannot see Tenant B chain
        chain_a = audit_chain.get_chain("tenant_a")
        chain_b = audit_chain.get_chain("tenant_b")

        assert len(chain_a) == 1
        assert len(chain_b) == 0

        # Verify state isolation
        state_partition.update_state(
            tenant_id="tenant_a",
            state_key="secret",
            state_value="a_secret"
        )

        state_partition.update_state(
            tenant_id="tenant_b",
            state_key="secret",
            state_value="b_secret"
        )

        state_a = state_partition.get_tenant_state("tenant_a")
        state_b = state_partition.get_tenant_state("tenant_b")

        assert state_a["secret"] == "a_secret"
        assert state_b["secret"] == "b_secret"

    @pytest.mark.asyncio
    async def test_capability_escalation_prevention(self):
        """Capability escalation prevention"""
        # Setup
        runtime_api = DeterministicRuntimeAPI()

        # Register function with high privilege
        def admin_func() -> str:
            return "admin_data"

        runtime_api.register_function(
            name="admin_func",
            func=admin_func,
            required_capabilities=["admin:full"]
        )

        # Create contract with low privilege
        contract = runtime_api.create_contract(
            tenant_id="tenant_1",
            capability_set=["user:basic"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        # Try to call admin function - should fail
        with pytest.raises(PermissionError):
            await runtime_api.call(
                contract_id=contract.contract_id,
                function_name="admin_func",
                arguments={}
            )

    @pytest.mark.asyncio
    async def test_audit_tampering_detection(self):
        """Audit tampering detection"""
        # Setup
        audit_chain = TenantAuditChain()

        # Add entries
        for i in range(5):
            audit_chain.append(
                tenant_id="tenant_1",
                event_type=f"event_{i}",
                event_data={"index": i}
            )

        # Verify chain is valid
        assert audit_chain.verify_chain("tenant_1") == True

        # Get chain
        chain = audit_chain.get_chain("tenant_1")

        # Verify each entry hash is correct
        for entry in chain:
            data = {
                "entry_id": entry.entry_id,
                "tenant_id": entry.tenant_id,
                "event_type": entry.event_type,
                "event_data": entry.event_data,
                "timestamp": entry.timestamp,
                "previous_hash": entry.previous_hash,
                "protocol_version": entry.protocol_version
            }
            expected_hash = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()

            assert entry.entry_hash == expected_hash


class TestPhase61DeterminismIntegration:
    """Determinism integration tests for Phase 6.1"""

    @pytest.mark.asyncio
    async def test_multi_run_determinism(self):
        """Multi-run determinism"""
        # Setup
        runtime_api = DeterministicRuntimeAPI()

        def compute(x: int) -> int:
            return x ** 2

        runtime_api.register_function(
            name="square",
            func=compute,
            required_capabilities=[]
        )

        # Run multiple times
        results = []
        for _ in range(5):
            contract = runtime_api.create_contract(
                tenant_id="tenant_1",
                capability_set=[],
                execution_domain=ExecutionDomain.LOCAL,
                resource_limits={},
                deterministic_seed=42
            )

            result = await runtime_api.call(
                contract_id=contract.contract_id,
                function_name="square",
                arguments={"x": 7}
            )

            results.append(result)

        # All results must be identical
        for result in results[1:]:
            assert result.output == results[0].output
            assert result.result_hash == results[0].result_hash

    @pytest.mark.asyncio
    async def test_cross_node_determinism(self):
        """Cross-node determinism simulation"""
        # Simulate two nodes
        audit_chain_1 = TenantAuditChain()
        audit_chain_2 = TenantAuditChain()

        # Same operations on both
        for i in range(5):
            audit_chain_1.append(
                tenant_id="tenant_1",
                event_type=f"event_{i}",
                event_data={"index": i}
            )

            audit_chain_2.append(
                tenant_id="tenant_1",
                event_type=f"event_{i}",
                event_data={"index": i}
            )

        # Chains must be identical
        chain_1 = audit_chain_1.get_chain("tenant_1")
        chain_2 = audit_chain_2.get_chain("tenant_1")

        assert len(chain_1) == len(chain_2)

        for e1, e2 in zip(chain_1, chain_2):
            assert e1.entry_hash == e2.entry_hash
            assert e1.previous_hash == e2.previous_hash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
