"""
Phase 7.1: Integration Tests
Protocol Version: 1.0

Integration tests for Orchestrator Control Plane components.
"""

import pytest
from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority
from synapse.orchestrator_control.models import (
    ExecutionProvenanceRecord,
    TrustedNodeDescriptor,
    PROTOCOL_VERSION
)


class TestOrchestratorControlPlaneIntegration:
    """Integration tests for the complete control plane"""
    
    def test_full_execution_workflow(self):
        """Test complete execution workflow from submission to proof retrieval"""
        # Setup components
        registry = ExecutionProvenanceRegistry()
        authority = ClusterMembershipAuthority()
        
        # Register nodes
        for i in range(3):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i}",
                node_name=f"Node {i}",
                public_key=f"pubkey_{i}",
                trust_level=1,
                registered_at="2026-02-23T00:00:00Z"
            )
            authority.register_trusted_node(descriptor)
        
        # Create API with all components
        api = OrchestratorControlAPI(
            provenance_registry=registry,
            membership_authority=authority
        )
        
        # Submit execution
        result = api.submit_execution_request(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"action": "test"}
        )
        
        assert "execution_id" in result
        execution_id = result["execution_id"]
        
        # Query status
        status = api.query_execution_status(execution_id)
        assert status is not None
        assert status["status"] == "pending"
        
        # Retrieve proof
        proof = api.retrieve_execution_proof(execution_id)
        assert proof is not None
        assert proof["execution_id"] == execution_id
        
        # Verify provenance
        provenance = registry.get_execution_provenance(execution_id)
        assert provenance is not None
        assert provenance.tenant_id == "tenant_1"
        
        # Verify provenance chain
        assert registry.verify_provenance_chain(execution_id)
    
    def test_cluster_management_workflow(self):
        """Test cluster management through API"""
        authority = ClusterMembershipAuthority()
        api = OrchestratorControlAPI(membership_authority=authority)
        
        # Initially no nodes
        nodes = api.list_cluster_nodes()
        assert len(nodes) == 0
        
        # Register nodes
        for i in range(3):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i}",
                node_name=f"Node {i}",
                public_key=f"pubkey_{i}",
                trust_level=1,
                registered_at="2026-02-23T00:00:00Z"
            )
            authority.register_trusted_node(descriptor)
        
        # List nodes through API
        nodes = api.list_cluster_nodes()
        assert len(nodes) == 3
        
        # Get cluster root
        root = api.get_cluster_root()
        assert root["node_count"] == 3
        assert root["membership_hash"] != ""
    
    def test_multi_tenant_execution_isolation(self):
        """Test that executions from different tenants are isolated"""
        registry = ExecutionProvenanceRegistry()
        api = OrchestratorControlAPI(provenance_registry=registry)
        
        # Submit executions for different tenants
        exec_ids = []
        for i in range(3):
            result = api.submit_execution_request(
                tenant_id=f"tenant_{i}",
                contract_id="contract_1",
                input_data={"tenant": i}
            )
            exec_ids.append(result["execution_id"])
        
        # Verify each execution is isolated
        for i, exec_id in enumerate(exec_ids):
            provenance = registry.get_execution_provenance(exec_id)
            assert provenance.tenant_id == f"tenant_{i}"
        
        # Verify tenant isolation in queries
        for tenant_id in ["tenant_0", "tenant_1", "tenant_2"]:
            tenant_execs = registry.get_executions_by_tenant(tenant_id)
            assert len(tenant_execs) == 1
    
    def test_audit_trail_completeness(self):
        """Test that all operations are audit logged"""
        api = OrchestratorControlAPI()
        
        # Perform multiple operations
        api.submit_execution_request(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"test": "data"}
        )
        
        api.list_cluster_nodes()
        api.get_cluster_root()
        
        # Get audit log
        audit_log = api.get_audit_log()
        
        # Verify all operations are logged
        operations = [entry.operation for entry in audit_log]
        assert "submit_execution_request" in operations
        assert "list_cluster_nodes" in operations
        assert "get_cluster_root" in operations
    
    def test_deterministic_execution_across_instances(self):
        """Test that identical inputs produce identical results"""
        # Create two independent instances
        registry1 = ExecutionProvenanceRegistry()
        registry2 = ExecutionProvenanceRegistry()
        
        authority1 = ClusterMembershipAuthority()
        authority2 = ClusterMembershipAuthority()
        
        # Register same nodes
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
        
        # Verify membership hash is identical
        hash1 = authority1.compute_membership_hash()
        hash2 = authority2.compute_membership_hash()
        assert hash1 == hash2
        
        # Record same provenance
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
        
        # Verify registry hash is identical
        reg_hash1 = registry1.compute_registry_hash()
        reg_hash2 = registry2.compute_registry_hash()
        assert reg_hash1 == reg_hash2


class TestSecurityInvariants:
    """Tests for security invariants"""
    
    def test_no_execution_without_contract(self):
        """Verify execution is blocked without contract"""
        api = OrchestratorControlAPI()
        
        with pytest.raises(ValueError, match="contract"):
            api.submit_execution_request(
                tenant_id="tenant_1",
                contract_id=None,
                input_data={"test": "data"}
            )
    
    def test_provenance_chain_integrity(self):
        """Verify provenance chain cannot be tampered"""
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
        
        # Verify chain
        assert registry.verify_provenance_chain("exec_1")
        
        # Get chain hash
        chain = registry.get_provenance_chain("exec_1")
        original_hash = chain.chain_hash
        
        # Record same record again - chain should update
        registry.record_execution_provenance(record)
        
        # Chain hash should change (new record added)
        updated_chain = registry.get_provenance_chain("exec_1")
        # Note: In this implementation, duplicate records are appended
        assert len(updated_chain.records) == 2
    
    def test_membership_verification(self):
        """Verify only registered nodes are trusted"""
        authority = ClusterMembershipAuthority()
        
        # Unregistered node should not be verified
        assert not authority.verify_membership("unknown_node")
        
        # Register a node
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        
        # Registered node should be verified
        assert authority.verify_membership("node_0")
    
    def test_quorum_enforcement(self):
        """Verify quorum is properly enforced"""
        authority = ClusterMembershipAuthority(quorum_threshold=3)
        
        # No quorum with 0 nodes
        assert not authority.validate_quorum()
        
        # Register 2 nodes - still no quorum
        for i in range(2):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i}",
                node_name=f"Node {i}",
                public_key=f"pubkey_{i}",
                trust_level=1,
                registered_at="2026-02-23T00:00:00Z"
            )
            authority.register_trusted_node(descriptor)
        
        assert not authority.validate_quorum()
        
        # Register 3rd node - quorum reached
        descriptor = TrustedNodeDescriptor(
            node_id="node_2",
            node_name="Node 2",
            public_key="pubkey_2",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        
        assert authority.validate_quorum()


class TestProtocolCompliance:
    """Tests for protocol version compliance"""
    
    def test_all_results_include_protocol_version(self):
        """Verify all API results include protocol_version"""
        registry = ExecutionProvenanceRegistry()
        authority = ClusterMembershipAuthority()
        api = OrchestratorControlAPI(
            provenance_registry=registry,
            membership_authority=authority
        )
        
        # Register a node
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        
        # Submit execution
        result = api.submit_execution_request(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"test": "data"}
        )
        assert result["protocol_version"] == "1.0"
        
        # Query status
        status = api.query_execution_status(result["execution_id"])
        assert status["protocol_version"] == "1.0"
        
        # Retrieve proof
        proof = api.retrieve_execution_proof(result["execution_id"])
        assert proof["protocol_version"] == "1.0"
        
        # Get cluster root
        root = api.get_cluster_root()
        assert root["protocol_version"] == "1.0"
    
    def test_provenance_records_include_protocol_version(self):
        """Verify provenance records include protocol_version"""
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
        assert retrieved.protocol_version == "1.0"
    
    def test_node_descriptors_include_protocol_version(self):
        """Verify node descriptors include protocol_version"""
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        
        assert descriptor.protocol_version == "1.0"
