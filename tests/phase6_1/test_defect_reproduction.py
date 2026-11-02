"""
Defect Reproduction Tests for Phase 6.1
TDD Step 1: Write failing tests that reproduce defects
"""

import pytest
from synapse.control_plane.tenant_quota_registry import TenantQuotaRegistry
from synapse.runtime_api.deterministic_runtime_api import (
    DeterministicRuntimeAPI,
    ExecutionContract,
    ExecutionDomain
)


class TestTenantQuotaRegistryAPIDefect:
    """Defect: API mismatch - tests expect register_tenant but class has register_quota"""
    
    def test_register_tenant_method_exists(self):
        """register_tenant method must exist"""
        registry = TenantQuotaRegistry()
        assert hasattr(registry, 'register_tenant'), \
            "TenantQuotaRegistry must have register_tenant method"
    
    def test_register_tenant_accepts_tenant_id_and_quotas(self):
        """register_tenant must accept tenant_id and quotas"""
        registry = TenantQuotaRegistry()
        result = registry.register_tenant(
            tenant_id="test_tenant",
            quotas={"cpu_seconds": 100, "memory_mb": 512}
        )
        assert result is True or result.get("success") is True
    
    def test_get_quota_method_exists(self):
        """get_quota method must exist"""
        registry = TenantQuotaRegistry()
        assert hasattr(registry, 'get_quota'), \
            "TenantQuotaRegistry must have get_quota method"
    
    def test_enforce_quota_method_exists(self):
        """enforce_quota method must exist"""
        registry = TenantQuotaRegistry()
        assert hasattr(registry, 'enforce_quota'), \
            "TenantQuotaRegistry must have enforce_quota method"


class TestDeterministicRuntimeAPIContractDefect:
    """Defect: Contract validation failing with 'invalid' error"""
    
    def test_create_contract_returns_valid_contract(self):
        """create_contract must return a valid contract"""
        api = DeterministicRuntimeAPI()
        contract = api.create_contract(
            tenant_id="test_tenant",
            capability_set=["fs:read"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={"memory_mb": 256},
            deterministic_seed=42
        )
        assert contract is not None
        assert contract.validate() is True, \
            f"Contract {contract.contract_id} must be valid"
    
    def test_contract_hash_is_deterministic(self):
        """Contract hash must be deterministic across runs"""
        api = DeterministicRuntimeAPI()
        
        # Create same contract twice
        contract1 = api.create_contract(
            tenant_id="test_tenant",
            capability_set=["fs:read"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={"memory_mb": 256},
            deterministic_seed=42
        )
        
        contract2 = api.create_contract(
            tenant_id="test_tenant",
            capability_set=["fs:read"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={"memory_mb": 256},
            deterministic_seed=42
        )
        
        assert contract1.contract_hash == contract2.contract_hash, \
            "Identical inputs must produce identical contract hashes"


class TestDeterminismInvariantDefect:
    """Defect: Determinism invariant violations"""
    
    def test_tenant_schedule_hash_deterministic(self):
        """Tenant schedule hash must be deterministic"""
        from synapse.control_plane.tenant_scheduler import TenantScheduler
        
        scheduler = TenantScheduler()
        
        # Same input must produce same hash
        hash1 = scheduler.compute_schedule_hash(
            tenant_id="tenant_a",
            task_id="task_1",
            seed=42
        )
        
        hash2 = scheduler.compute_schedule_hash(
            tenant_id="tenant_a",
            task_id="task_1",
            seed=42
        )
        
        assert hash1 == hash2, \
            f"Schedule hash must be deterministic: {hash1} != {hash2}"


class TestIntegrationDefect:
    """Defect: Integration failures in multi-tenant execution"""
    
    def test_full_tenant_workflow_minimal(self):
        """Minimal tenant workflow must work"""
        registry = TenantQuotaRegistry()
        
        # Register tenant
        result = registry.register_tenant(
            tenant_id="tenant_test",
            quotas={"cpu_seconds": 100, "memory_mb": 512}
        )
        assert result is True or result.get("success") is True
        
        # Get quota
        quota = registry.get_quota("tenant_test")
        assert quota is not None
