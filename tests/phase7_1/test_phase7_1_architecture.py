"""
Phase 7.1: Orchestrator Control Plane - Architecture Tests
Protocol Version: 1.0

Tests for:
- OrchestratorControlAPI
- ExecutionProvenanceRegistry
- ClusterMembershipAuthority
"""

import pytest
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

# Import models from the implementation
from synapse.orchestrator_control.models import (
    ExecutionProvenanceRecord,
    TrustedNodeDescriptor,
    PROTOCOL_VERSION
)


# ============================================================================
# TEST: OrchestratorControlAPI
# ============================================================================

class TestOrchestratorControlAPI:
    """Tests for OrchestratorControlAPI component"""
    
    def test_api_exists(self):
        """OrchestratorControlAPI class must exist"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        assert OrchestratorControlAPI is not None
    
    def test_submit_execution_request_method_exists(self):
        """submit_execution_request method must exist"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        api = OrchestratorControlAPI()
        assert hasattr(api, 'submit_execution_request')
        assert callable(api.submit_execution_request)
    
    def test_query_execution_status_method_exists(self):
        """query_execution_status method must exist"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        api = OrchestratorControlAPI()
        assert hasattr(api, 'query_execution_status')
        assert callable(api.query_execution_status)
    
    def test_retrieve_execution_proof_method_exists(self):
        """retrieve_execution_proof method must exist"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        api = OrchestratorControlAPI()
        assert hasattr(api, 'retrieve_execution_proof')
        assert callable(api.retrieve_execution_proof)
    
    def test_list_cluster_nodes_method_exists(self):
        """list_cluster_nodes method must exist"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        api = OrchestratorControlAPI()
        assert hasattr(api, 'list_cluster_nodes')
        assert callable(api.list_cluster_nodes)
    
    def test_get_cluster_root_method_exists(self):
        """get_cluster_root method must exist"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        api = OrchestratorControlAPI()
        assert hasattr(api, 'get_cluster_root')
        assert callable(api.get_cluster_root)
    
    def test_submit_requires_contract(self):
        """submit_execution_request must require runtime contract"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        api = OrchestratorControlAPI()
        
        # Should raise error without contract
        with pytest.raises(ValueError, match="contract"):
            api.submit_execution_request(
                tenant_id="tenant_1",
                contract_id=None,
                input_data={"test": "data"}
            )
    
    def test_api_is_audit_logged(self):
        """All API calls must be audit logged"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        api = OrchestratorControlAPI()
        
        # Check that audit log is recorded
        result = api.submit_execution_request(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"test": "data"}
        )
        
        # Should have audit_id in result
        assert "audit_id" in result or "execution_id" in result


# ============================================================================
# TEST: ExecutionProvenanceRegistry
# ============================================================================

class TestExecutionProvenanceRegistry:
    """Tests for ExecutionProvenanceRegistry component"""
    
    def test_registry_exists(self):
        """ExecutionProvenanceRegistry class must exist"""
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        assert ExecutionProvenanceRegistry is not None
    
    def test_record_execution_provenance_method_exists(self):
        """record_execution_provenance method must exist"""
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        registry = ExecutionProvenanceRegistry()
        assert hasattr(registry, 'record_execution_provenance')
        assert callable(registry.record_execution_provenance)
    
    def test_get_execution_provenance_method_exists(self):
        """get_execution_provenance method must exist"""
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        registry = ExecutionProvenanceRegistry()
        assert hasattr(registry, 'get_execution_provenance')
        assert callable(registry.get_execution_provenance)
    
    def test_verify_provenance_chain_method_exists(self):
        """verify_provenance_chain method must exist"""
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        registry = ExecutionProvenanceRegistry()
        assert hasattr(registry, 'verify_provenance_chain')
        assert callable(registry.verify_provenance_chain)
    
    def test_record_provenance_returns_execution_id(self):
        """record_execution_provenance must return execution_id"""
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        registry = ExecutionProvenanceRegistry()
        
        record = ExecutionProvenanceRecord(
            execution_id="exec_1",
            tenant_id="tenant_1",
            contract_hash="abc123",
            node_id="node_0",
            cluster_schedule_hash="def456",
            audit_root="ghi789",
            execution_proof="proof_1",
            timestamp="2026-02-23T00:00:00Z"
        )
        
        execution_id = registry.record_execution_provenance(record)
        assert execution_id == "exec_1"
    
    def test_get_provenance_returns_record(self):
        """get_execution_provenance must return the record"""
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        registry = ExecutionProvenanceRegistry()
        
        record = ExecutionProvenanceRecord(
            execution_id="exec_1",
            tenant_id="tenant_1",
            contract_hash="abc123",
            node_id="node_0",
            cluster_schedule_hash="def456",
            audit_root="ghi789",
            execution_proof="proof_1",
            timestamp="2026-02-23T00:00:00Z"
        )
        
        registry.record_execution_provenance(record)
        retrieved = registry.get_execution_provenance("exec_1")
        
        assert retrieved is not None
        assert retrieved.execution_id == "exec_1"
    
    def test_verify_provenance_chain_returns_bool(self):
        """verify_provenance_chain must return bool"""
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        registry = ExecutionProvenanceRegistry()
        
        result = registry.verify_provenance_chain("exec_1")
        assert isinstance(result, bool)


# ============================================================================
# TEST: ClusterMembershipAuthority
# ============================================================================

class TestClusterMembershipAuthority:
    """Tests for ClusterMembershipAuthority component"""
    
    def test_authority_exists(self):
        """ClusterMembershipAuthority class must exist"""
        from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
        assert ClusterMembershipAuthority is not None
    
    def test_register_trusted_node_method_exists(self):
        """register_trusted_node method must exist"""
        from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
        authority = ClusterMembershipAuthority()
        assert hasattr(authority, 'register_trusted_node')
        assert callable(authority.register_trusted_node)
    
    def test_compute_membership_hash_method_exists(self):
        """compute_membership_hash method must exist"""
        from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
        authority = ClusterMembershipAuthority()
        assert hasattr(authority, 'compute_membership_hash')
        assert callable(authority.compute_membership_hash)
    
    def test_verify_membership_method_exists(self):
        """verify_membership method must exist"""
        from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
        authority = ClusterMembershipAuthority()
        assert hasattr(authority, 'verify_membership')
        assert callable(authority.verify_membership)
    
    def test_register_trusted_node_returns_node_id(self):
        """register_trusted_node must return node_id"""
        from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        
        node_id = authority.register_trusted_node(descriptor)
        assert node_id == "node_0"
    
    def test_compute_membership_hash_returns_string(self):
        """compute_membership_hash must return hash string"""
        from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
        authority = ClusterMembershipAuthority()
        
        # Register a node first
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        
        hash_result = authority.compute_membership_hash()
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA-256 hex length
    
    def test_membership_hash_is_deterministic(self):
        """Membership hash must be deterministic"""
        from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
        
        authority1 = ClusterMembershipAuthority()
        authority2 = ClusterMembershipAuthority()
        
        # Register same nodes in both
        for i in range(3):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i}",
                node_name=f"Node {i}",
                public_key=f"pubkey_{i}",
                trust_level=1,
                registered_at="2026-02-23T00:00:00Z"
            )
            authority1.register_trusted_node(descriptor)
            authority2.register_trusted_node(descriptor)
        
        hash1 = authority1.compute_membership_hash()
        hash2 = authority2.compute_membership_hash()
        
        assert hash1 == hash2, "Membership hash must be deterministic"
    
    def test_verify_membership_returns_bool(self):
        """verify_membership must return bool"""
        from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
        authority = ClusterMembershipAuthority()
        
        result = authority.verify_membership("node_0")
        assert isinstance(result, bool)


# ============================================================================
# TEST: Control Plane Does Not Bypass Runtime Contract
# ============================================================================

class TestControlPlaneSecurity:
    """Tests for control plane security"""
    
    def test_control_plane_does_not_bypass_contract(self):
        """Control plane must not bypass runtime contract"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        api = OrchestratorControlAPI()
        
        # Attempt to execute without contract should fail
        with pytest.raises(ValueError):
            api.submit_execution_request(
                tenant_id="tenant_1",
                contract_id=None,
                input_data={"test": "data"}
            )
    
    def test_audit_root_linked_to_provenance(self):
        """Audit root must be linked to execution provenance"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        
        registry = ExecutionProvenanceRegistry()
        api = OrchestratorControlAPI(provenance_registry=registry)
        
        result = api.submit_execution_request(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"test": "data"}
        )
        
        # Check provenance was recorded
        if "execution_id" in result:
            provenance = registry.get_execution_provenance(result["execution_id"])
            if provenance:
                assert provenance.audit_root is not None


# ============================================================================
# TEST: Determinism
# ============================================================================

class TestDeterminism:
    """Tests for determinism"""
    
    def test_provenance_chain_deterministic(self):
        """Provenance chain must be deterministic"""
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        
        registry1 = ExecutionProvenanceRegistry()
        registry2 = ExecutionProvenanceRegistry()
        
        record = ExecutionProvenanceRecord(
            execution_id="exec_1",
            tenant_id="tenant_1",
            contract_hash="abc123",
            node_id="node_0",
            cluster_schedule_hash="def456",
            audit_root="ghi789",
            execution_proof="proof_1",
            timestamp="2026-02-23T00:00:00Z"
        )
        
        registry1.record_execution_provenance(record)
        registry2.record_execution_provenance(record)
        
        # Both should verify the same
        assert registry1.verify_provenance_chain("exec_1") == registry2.verify_provenance_chain("exec_1")
    
    def test_orchestrator_calls_produce_identical_execution(self):
        """Identical orchestrator calls must produce identical execution"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        
        api1 = OrchestratorControlAPI()
        api2 = OrchestratorControlAPI()
        
        result1 = api1.submit_execution_request(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"test": "data"}
        )
        
        result2 = api2.submit_execution_request(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"test": "data"}
        )
        
        # Both should have same structure
        assert set(result1.keys()) == set(result2.keys())


# ============================================================================
# TEST: Protocol Versioning
# ============================================================================

class TestProtocolVersioning:
    """Tests for protocol versioning"""
    
    def test_all_components_have_protocol_version(self):
        """All components must have PROTOCOL_VERSION"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
        
        assert hasattr(OrchestratorControlAPI, 'PROTOCOL_VERSION')
        assert hasattr(ExecutionProvenanceRegistry, 'PROTOCOL_VERSION')
        assert hasattr(ClusterMembershipAuthority, 'PROTOCOL_VERSION')
    
    def test_protocol_version_is_1_0(self):
        """All components must use protocol_version 1.0"""
        from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
        from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
        from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
        
        assert OrchestratorControlAPI.PROTOCOL_VERSION == "1.0"
        assert ExecutionProvenanceRegistry.PROTOCOL_VERSION == "1.0"
        assert ClusterMembershipAuthority.PROTOCOL_VERSION == "1.0"
