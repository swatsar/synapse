"""
Phase 7.1: Additional Coverage Tests
Protocol Version: 1.0

Additional tests to achieve ≥90% coverage.
"""

import pytest
from synapse.orchestrator_control.models import (
    ExecutionRequest,
    ExecutionProvenanceRecord,
    TrustedNodeDescriptor,
    ExecutionStatus,
    ClusterMembership,
    AuditLogEntry,
    PROTOCOL_VERSION
)
from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority


class TestModelsCoverage:
    """Tests for model methods"""
    
    def test_execution_request_compute_hash(self):
        """ExecutionRequest.compute_hash() must work"""
        request = ExecutionRequest(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"test": "data"}
        )
        hash_result = request.compute_hash()
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64
    
    def test_execution_request_hash_deterministic(self):
        """ExecutionRequest hash must be deterministic"""
        request1 = ExecutionRequest(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"test": "data"}
        )
        request2 = ExecutionRequest(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"test": "data"}
        )
        assert request1.compute_hash() == request2.compute_hash()
    
    def test_execution_provenance_record_compute_hash(self):
        """ExecutionProvenanceRecord.compute_provenance_hash() must work"""
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
        hash_result = record.compute_provenance_hash()
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64
    
    def test_trusted_node_descriptor_compute_hash(self):
        """TrustedNodeDescriptor.compute_node_hash() must work"""
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        hash_result = descriptor.compute_node_hash()
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64


class TestOrchestratorControlAPICoverage:
    """Additional tests for OrchestratorControlAPI coverage"""
    
    def test_query_execution_status_not_found(self):
        """query_execution_status returns None for non-existent execution"""
        api = OrchestratorControlAPI()
        result = api.query_execution_status("non_existent")
        assert result is None
    
    def test_retrieve_execution_proof_not_found(self):
        """retrieve_execution_proof returns None for non-existent execution"""
        api = OrchestratorControlAPI()
        result = api.retrieve_execution_proof("non_existent")
        assert result is None
    
    def test_list_cluster_nodes_empty(self):
        """list_cluster_nodes returns empty list without membership authority"""
        api = OrchestratorControlAPI()
        result = api.list_cluster_nodes()
        assert result == []
    
    def test_get_cluster_root_empty(self):
        """get_cluster_root returns empty hash without membership authority"""
        api = OrchestratorControlAPI()
        result = api.get_cluster_root()
        assert result["membership_hash"] == ""
        assert result["node_count"] == 0
    
    def test_get_audit_log(self):
        """get_audit_log returns all audit entries"""
        api = OrchestratorControlAPI()
        
        # Submit an execution
        api.submit_execution_request(
            tenant_id="tenant_1",
            contract_id="contract_1",
            input_data={"test": "data"}
        )
        
        # Get audit log
        audit_log = api.get_audit_log()
        assert len(audit_log) >= 1
        assert all(isinstance(entry, AuditLogEntry) for entry in audit_log)
    
    def test_orchestrator_with_membership_authority(self):
        """OrchestratorControlAPI works with membership authority"""
        authority = ClusterMembershipAuthority()
        
        # Register a node
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        
        # Create API with membership authority
        api = OrchestratorControlAPI(membership_authority=authority)
        
        # List nodes
        nodes = api.list_cluster_nodes()
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "node_0"
        
        # Get cluster root
        root = api.get_cluster_root()
        assert root["membership_hash"] != ""
        assert root["node_count"] == 1


class TestExecutionProvenanceRegistryCoverage:
    """Additional tests for ExecutionProvenanceRegistry coverage"""
    
    def test_get_provenance_chain(self):
        """get_provenance_chain returns chain"""
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
        chain = registry.get_provenance_chain("exec_1")
        
        assert chain is not None
        assert chain.execution_id == "exec_1"
        assert len(chain.records) == 1
    
    def test_get_audit_root(self):
        """get_audit_root returns audit root"""
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
        audit_root = registry.get_audit_root("exec_1")
        
        assert audit_root == "ghi789"
    
    def test_list_executions(self):
        """list_executions returns all execution IDs"""
        registry = ExecutionProvenanceRegistry()
        
        for i in range(3):
            record = ExecutionProvenanceRecord(
                execution_id=f"exec_{i}",
                tenant_id="tenant_1",
                contract_hash="abc123",
                node_id="node_0",
                cluster_schedule_hash="def456",
                audit_root="ghi789",
                execution_proof="proof_1",
                timestamp="2026-02-23T00:00:00Z"
            )
            registry.record_execution_provenance(record)
        
        executions = registry.list_executions()
        assert len(executions) == 3
    
    def test_get_executions_by_tenant(self):
        """get_executions_by_tenant returns executions for tenant"""
        registry = ExecutionProvenanceRegistry()
        
        for i in range(3):
            record = ExecutionProvenanceRecord(
                execution_id=f"exec_{i}",
                tenant_id=f"tenant_{i % 2}",
                contract_hash="abc123",
                node_id="node_0",
                cluster_schedule_hash="def456",
                audit_root="ghi789",
                execution_proof="proof_1",
                timestamp="2026-02-23T00:00:00Z"
            )
            registry.record_execution_provenance(record)
        
        tenant_0_executions = registry.get_executions_by_tenant("tenant_0")
        assert len(tenant_0_executions) == 2  # exec_0, exec_2
    
    def test_get_executions_by_node(self):
        """get_executions_by_node returns executions for node"""
        registry = ExecutionProvenanceRegistry()
        
        for i in range(3):
            record = ExecutionProvenanceRecord(
                execution_id=f"exec_{i}",
                tenant_id="tenant_1",
                contract_hash="abc123",
                node_id=f"node_{i % 2}",
                cluster_schedule_hash="def456",
                audit_root="ghi789",
                execution_proof="proof_1",
                timestamp="2026-02-23T00:00:00Z"
            )
            registry.record_execution_provenance(record)
        
        node_0_executions = registry.get_executions_by_node("node_0")
        assert len(node_0_executions) == 2  # exec_0, exec_2
    
    def test_compute_registry_hash(self):
        """compute_registry_hash returns deterministic hash"""
        registry1 = ExecutionProvenanceRegistry()
        registry2 = ExecutionProvenanceRegistry()
        
        for i in range(3):
            record = ExecutionProvenanceRecord(
                execution_id=f"exec_{i}",
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
        
        hash1 = registry1.compute_registry_hash()
        hash2 = registry2.compute_registry_hash()
        
        assert hash1 == hash2


class TestClusterMembershipAuthorityCoverage:
    """Additional tests for ClusterMembershipAuthority coverage"""
    
    def test_unregister_node(self):
        """unregister_node removes node"""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        
        # Unregister
        result = authority.unregister_node("node_0")
        assert result == True
        assert not authority.verify_membership("node_0")
    
    def test_unregister_non_existent_node(self):
        """unregister_node returns False for non-existent node"""
        authority = ClusterMembershipAuthority()
        result = authority.unregister_node("non_existent")
        assert result == False
    
    def test_get_node(self):
        """get_node returns node descriptor"""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        
        node = authority.get_node("node_0")
        assert node is not None
        assert node.node_id == "node_0"
    
    def test_get_membership_state(self):
        """get_membership_state returns current state"""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        
        state = authority.get_membership_state()
        assert state.membership_hash != ""
        assert len(state.nodes) == 1
    
    def test_validate_quorum(self):
        """validate_quorum checks quorum threshold"""
        authority = ClusterMembershipAuthority(quorum_threshold=2)
        
        # No nodes - no quorum
        assert not authority.validate_quorum()
        
        # One node - no quorum
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        assert not authority.validate_quorum()
        
        # Two nodes - quorum reached
        descriptor2 = TrustedNodeDescriptor(
            node_id="node_1",
            node_name="Node 1",
            public_key="pubkey_def456",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor2)
        assert authority.validate_quorum()
    
    def test_get_quorum_count(self):
        """get_quorum_count returns current count"""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        
        assert authority.get_quorum_count() == 1
    
    def test_compute_cluster_identity_hash(self):
        """compute_cluster_identity_hash returns deterministic hash"""
        authority1 = ClusterMembershipAuthority()
        authority2 = ClusterMembershipAuthority()
        
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
        
        hash1 = authority1.compute_cluster_identity_hash()
        hash2 = authority2.compute_cluster_identity_hash()
        
        assert hash1 == hash2
    
    def test_verify_membership_integrity(self):
        """verify_membership_integrity checks integrity"""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_0",
            node_name="Node 0",
            public_key="pubkey_abc123",
            trust_level=1,
            registered_at="2026-02-23T00:00:00Z"
        )
        authority.register_trusted_node(descriptor)
        
        assert authority.verify_membership_integrity()
    
    def test_get_nodes_by_trust_level(self):
        """get_nodes_by_trust_level filters by trust level"""
        authority = ClusterMembershipAuthority()
        
        for i in range(3):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i}",
                node_name=f"Node {i}",
                public_key=f"pubkey_{i}",
                trust_level=i % 2 + 1,
                registered_at="2026-02-23T00:00:00Z"
            )
            authority.register_trusted_node(descriptor)
        
        level_1_nodes = authority.get_nodes_by_trust_level(1)
        assert len(level_1_nodes) == 2  # node_0, node_2
    
    def test_get_trusted_nodes(self):
        """get_trusted_nodes returns all node IDs"""
        authority = ClusterMembershipAuthority()
        
        for i in range(3):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i}",
                node_name=f"Node {i}",
                public_key=f"pubkey_{i}",
                trust_level=1,
                registered_at="2026-02-23T00:00:00Z"
            )
            authority.register_trusted_node(descriptor)
        
        nodes = authority.get_trusted_nodes()
        assert len(nodes) == 3
