"""
Unit tests for orchestrator_control module.
Tests models, cluster membership authority, execution provenance registry, and control API.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
import hashlib
import json

# Import modules under test
from synapse.orchestrator_control.models import (
    ExecutionRequest,
    ExecutionProvenanceRecord,
    TrustedNodeDescriptor,
    ExecutionStatus,
    ClusterMembership,
    AuditLogEntry,
    PROTOCOL_VERSION
)
from synapse.orchestrator_control.cluster_membership_authority import (
    ClusterMembershipAuthority,
    MembershipState
)
from synapse.orchestrator_control.execution_provenance_registry import (
    ExecutionProvenanceRegistry,
    ProvenanceChain
)
from synapse.orchestrator_control.orchestrator_control_api import (
    OrchestratorControlAPI,
    ExecutionResult
)


# ============================================================================
# Tests for models.py
# ============================================================================

class TestExecutionRequest:
    """Tests for ExecutionRequest dataclass."""
    
    def test_create_execution_request(self):
        """Test creating an execution request."""
        request = ExecutionRequest(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        assert request.tenant_id == "tenant_123"
        assert request.contract_id == "contract_456"
        assert request.input_data == {"key": "value"}
        assert request.protocol_version == PROTOCOL_VERSION
    
    def test_compute_hash_deterministic(self):
        """Test that hash computation is deterministic."""
        request1 = ExecutionRequest(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        request2 = ExecutionRequest(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        hash1 = request1.compute_hash()
        hash2 = request2.compute_hash()
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length
    
    def test_compute_hash_different_inputs(self):
        """Test that different inputs produce different hashes."""
        request1 = ExecutionRequest(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value1"}
        )
        
        request2 = ExecutionRequest(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value2"}
        )
        
        assert request1.compute_hash() != request2.compute_hash()
    
    def test_compute_hash_different_tenant(self):
        """Test that different tenants produce different hashes."""
        request1 = ExecutionRequest(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        request2 = ExecutionRequest(
            tenant_id="tenant_789",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        assert request1.compute_hash() != request2.compute_hash()


class TestExecutionProvenanceRecord:
    """Tests for ExecutionProvenanceRecord dataclass."""
    
    def test_create_provenance_record(self):
        """Test creating a provenance record."""
        record = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_0",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_456",
            timestamp="2026-02-19T12:00:00"
        )
        
        assert record.execution_id == "exec_001"
        assert record.tenant_id == "tenant_123"
        assert record.protocol_version == PROTOCOL_VERSION
    
    def test_compute_provenance_hash_deterministic(self):
        """Test that provenance hash computation is deterministic."""
        record1 = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_0",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_456",
            timestamp="2026-02-19T12:00:00"
        )
        
        record2 = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_0",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_456",
            timestamp="2026-02-19T12:00:00"
        )
        
        assert record1.compute_provenance_hash() == record2.compute_provenance_hash()


class TestTrustedNodeDescriptor:
    """Tests for TrustedNodeDescriptor dataclass."""
    
    def test_create_node_descriptor(self):
        """Test creating a node descriptor."""
        descriptor = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc123",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        assert descriptor.node_id == "node_001"
        assert descriptor.node_name == "Worker Node 1"
        assert descriptor.trust_level == 5
        assert descriptor.protocol_version == PROTOCOL_VERSION
    
    def test_compute_node_hash_deterministic(self):
        """Test that node hash computation is deterministic."""
        descriptor1 = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc123",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        descriptor2 = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc123",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        assert descriptor1.compute_node_hash() == descriptor2.compute_node_hash()


class TestExecutionStatus:
    """Tests for ExecutionStatus dataclass."""
    
    def test_create_pending_status(self):
        """Test creating a pending execution status."""
        status = ExecutionStatus(
            execution_id="exec_001",
            status="pending",
            tenant_id="tenant_123",
            contract_id="contract_456"
        )
        
        assert status.status == "pending"
        assert status.node_id is None
        assert status.started_at is None
    
    def test_create_completed_status(self):
        """Test creating a completed execution status."""
        status = ExecutionStatus(
            execution_id="exec_001",
            status="completed",
            tenant_id="tenant_123",
            contract_id="contract_456",
            node_id="node_0",
            started_at="2026-02-19T12:00:00",
            completed_at="2026-02-19T12:01:00"
        )
        
        assert status.status == "completed"
        assert status.node_id == "node_0"
        assert status.completed_at == "2026-02-19T12:01:00"
    
    def test_create_failed_status(self):
        """Test creating a failed execution status."""
        status = ExecutionStatus(
            execution_id="exec_001",
            status="failed",
            tenant_id="tenant_123",
            contract_id="contract_456",
            error="Connection timeout"
        )
        
        assert status.status == "failed"
        assert status.error == "Connection timeout"


class TestClusterMembership:
    """Tests for ClusterMembership dataclass."""
    
    def test_create_cluster_membership(self):
        """Test creating cluster membership."""
        membership = ClusterMembership(
            membership_hash="hash_abc123",
            nodes=["node_0", "node_1", "node_2"],
            quorum_count=3,
            timestamp="2026-02-19T12:00:00"
        )
        
        assert len(membership.nodes) == 3
        assert membership.quorum_count == 3
        assert membership.protocol_version == PROTOCOL_VERSION


class TestAuditLogEntry:
    """Tests for AuditLogEntry dataclass."""
    
    def test_create_audit_log_entry(self):
        """Test creating an audit log entry."""
        entry = AuditLogEntry(
            audit_id="audit_001",
            operation="submit_execution",
            tenant_id="tenant_123",
            execution_id="exec_001",
            timestamp="2026-02-19T12:00:00",
            details={"contract_id": "contract_456"}
        )
        
        assert entry.audit_id == "audit_001"
        assert entry.operation == "submit_execution"
        assert entry.details == {"contract_id": "contract_456"}
    
    def test_create_audit_log_entry_no_details(self):
        """Test creating an audit log entry without details."""
        entry = AuditLogEntry(
            audit_id="audit_002",
            operation="query_status",
            tenant_id="system",
            execution_id=None,
            timestamp="2026-02-19T12:00:00"
        )
        
        assert entry.details == {}
        assert entry.execution_id is None


# ============================================================================
# Tests for cluster_membership_authority.py
# ============================================================================

class TestClusterMembershipAuthority:
    """Tests for ClusterMembershipAuthority class."""
    
    def test_init_default_quorum(self):
        """Test initialization with default quorum threshold."""
        authority = ClusterMembershipAuthority()
        
        assert authority.get_quorum_threshold() == 2
        assert authority.get_quorum_count() == 0
    
    def test_init_custom_quorum(self):
        """Test initialization with custom quorum threshold."""
        authority = ClusterMembershipAuthority(quorum_threshold=5)
        
        assert authority.get_quorum_threshold() == 5
    
    def test_register_trusted_node(self):
        """Test registering a trusted node."""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        node_id = authority.register_trusted_node(descriptor)
        
        assert node_id == "node_001"
        assert authority.verify_membership("node_001") is True
        assert authority.get_quorum_count() == 1
    
    def test_register_multiple_nodes(self):
        """Test registering multiple nodes."""
        authority = ClusterMembershipAuthority()
        
        for i in range(5):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i:03d}",
                node_name=f"Worker Node {i}",
                public_key=f"pub_key_{i}",
                trust_level=i + 1,
                registered_at="2026-02-19T12:00:00"
            )
            authority.register_trusted_node(descriptor)
        
        assert authority.get_quorum_count() == 5
        
        for i in range(5):
            assert authority.verify_membership(f"node_{i:03d}") is True
    
    def test_unregister_node(self):
        """Test unregistering a node."""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        authority.register_trusted_node(descriptor)
        assert authority.verify_membership("node_001") is True
        
        result = authority.unregister_node("node_001")
        
        assert result is True
        assert authority.verify_membership("node_001") is False
        assert authority.get_quorum_count() == 0
    
    def test_unregister_nonexistent_node(self):
        """Test unregistering a node that doesn't exist."""
        authority = ClusterMembershipAuthority()
        
        result = authority.unregister_node("nonexistent_node")
        
        assert result is False
    
    def test_compute_membership_hash_deterministic(self):
        """Test that membership hash is deterministic."""
        authority1 = ClusterMembershipAuthority()
        authority2 = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        authority1.register_trusted_node(descriptor)
        authority2.register_trusted_node(descriptor)
        
        assert authority1.compute_membership_hash() == authority2.compute_membership_hash()
    
    def test_compute_membership_hash_changes(self):
        """Test that membership hash changes when nodes are added."""
        authority = ClusterMembershipAuthority()
        
        descriptor1 = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        authority.register_trusted_node(descriptor1)
        hash1 = authority.compute_membership_hash()
        
        descriptor2 = TrustedNodeDescriptor(
            node_id="node_002",
            node_name="Worker Node 2",
            public_key="pub_key_def",
            trust_level=3,
            registered_at="2026-02-19T12:00:00"
        )
        
        authority.register_trusted_node(descriptor2)
        hash2 = authority.compute_membership_hash()
        
        assert hash1 != hash2
    
    def test_get_node(self):
        """Test getting a node descriptor."""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        authority.register_trusted_node(descriptor)
        
        retrieved = authority.get_node("node_001")
        
        assert retrieved is not None
        assert retrieved.node_id == "node_001"
        assert retrieved.node_name == "Worker Node 1"
    
    def test_get_nonexistent_node(self):
        """Test getting a node that doesn't exist."""
        authority = ClusterMembershipAuthority()
        
        retrieved = authority.get_node("nonexistent_node")
        
        assert retrieved is None
    
    def test_list_nodes(self):
        """Test listing all nodes."""
        authority = ClusterMembershipAuthority()
        
        for i in range(3):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i:03d}",
                node_name=f"Worker Node {i}",
                public_key=f"pub_key_{i}",
                trust_level=i + 1,
                registered_at="2026-02-19T12:00:00"
            )
            authority.register_trusted_node(descriptor)
        
        nodes = authority.list_nodes()
        
        assert len(nodes) == 3
        assert nodes[0]["node_id"] == "node_000"
        assert nodes[1]["node_id"] == "node_001"
        assert nodes[2]["node_id"] == "node_002"
    
    def test_get_membership_state(self):
        """Test getting membership state."""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        authority.register_trusted_node(descriptor)
        
        state = authority.get_membership_state()
        
        assert isinstance(state, MembershipState)
        assert len(state.nodes) == 1
        assert state.quorum_count == 1
        assert state.membership_hash is not None
    
    def test_validate_quorum_met(self):
        """Test quorum validation when quorum is met."""
        authority = ClusterMembershipAuthority(quorum_threshold=2)
        
        for i in range(3):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i:03d}",
                node_name=f"Worker Node {i}",
                public_key=f"pub_key_{i}",
                trust_level=i + 1,
                registered_at="2026-02-19T12:00:00"
            )
            authority.register_trusted_node(descriptor)
        
        assert authority.validate_quorum() is True
    
    def test_validate_quorum_not_met(self):
        """Test quorum validation when quorum is not met."""
        authority = ClusterMembershipAuthority(quorum_threshold=5)
        
        for i in range(2):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i:03d}",
                node_name=f"Worker Node {i}",
                public_key=f"pub_key_{i}",
                trust_level=i + 1,
                registered_at="2026-02-19T12:00:00"
            )
            authority.register_trusted_node(descriptor)
        
        assert authority.validate_quorum() is False
    
    def test_compute_cluster_identity_hash(self):
        """Test computing cluster identity hash."""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        authority.register_trusted_node(descriptor)
        
        identity_hash = authority.compute_cluster_identity_hash()
        
        assert len(identity_hash) == 64  # SHA-256 hex length
    
    def test_verify_membership_integrity_valid(self):
        """Test verifying membership integrity with valid data."""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        authority.register_trusted_node(descriptor)
        
        assert authority.verify_membership_integrity() is True
    
    def test_get_nodes_by_trust_level(self):
        """Test getting nodes by trust level."""
        authority = ClusterMembershipAuthority()
        
        # Register nodes with unique IDs but varying trust levels
        for i, trust_level in enumerate([1, 3, 5, 3, 1]):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i:03d}",
                node_name=f"Worker Node {i}",
                public_key=f"pub_key_{i}",
                trust_level=trust_level,
                registered_at="2026-02-19T12:00:00"
            )
            authority.register_trusted_node(descriptor)
        
        level_3_nodes = authority.get_nodes_by_trust_level(3)
        level_1_nodes = authority.get_nodes_by_trust_level(1)
        level_5_nodes = authority.get_nodes_by_trust_level(5)
        
        assert len(level_3_nodes) == 2  # node_001 and node_003
        assert len(level_1_nodes) == 2  # node_000 and node_004
        assert len(level_5_nodes) == 1  # node_002
    
    def test_get_trusted_nodes(self):
        """Test getting all trusted node IDs."""
        authority = ClusterMembershipAuthority()
        
        for i in range(3):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i:03d}",
                node_name=f"Worker Node {i}",
                public_key=f"pub_key_{i}",
                trust_level=i + 1,
                registered_at="2026-02-19T12:00:00"
            )
            authority.register_trusted_node(descriptor)
        
        trusted_nodes = authority.get_trusted_nodes()
        
        assert len(trusted_nodes) == 3
        assert set(trusted_nodes) == {"node_000", "node_001", "node_002"}


# ============================================================================
# Tests for execution_provenance_registry.py
# ============================================================================

class TestExecutionProvenanceRegistry:
    """Tests for ExecutionProvenanceRegistry class."""
    
    def test_init(self):
        """Test initialization of registry."""
        registry = ExecutionProvenanceRegistry()
        
        assert registry.list_executions() == []
    
    def test_record_execution_provenance(self):
        """Test recording execution provenance."""
        registry = ExecutionProvenanceRegistry()
        
        record = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_0",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_456",
            timestamp="2026-02-19T12:00:00"
        )
        
        exec_id = registry.record_execution_provenance(record)
        
        assert exec_id == "exec_001"
        assert "exec_001" in registry.list_executions()
    
    def test_get_execution_provenance(self):
        """Test getting execution provenance."""
        registry = ExecutionProvenanceRegistry()
        
        record = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_0",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_456",
            timestamp="2026-02-19T12:00:00"
        )
        
        registry.record_execution_provenance(record)
        
        retrieved = registry.get_execution_provenance("exec_001")
        
        assert retrieved is not None
        assert retrieved.execution_id == "exec_001"
        assert retrieved.tenant_id == "tenant_123"
    
    def test_get_nonexistent_execution_provenance(self):
        """Test getting provenance for nonexistent execution."""
        registry = ExecutionProvenanceRegistry()
        
        retrieved = registry.get_execution_provenance("nonexistent")
        
        assert retrieved is None
    
    def test_verify_provenance_chain_valid(self):
        """Test verifying a valid provenance chain."""
        registry = ExecutionProvenanceRegistry()
        
        record = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_0",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_456",
            timestamp="2026-02-19T12:00:00"
        )
        
        registry.record_execution_provenance(record)
        
        assert registry.verify_provenance_chain("exec_001") is True
    
    def test_verify_provenance_chain_invalid(self):
        """Test verifying an invalid provenance chain."""
        registry = ExecutionProvenanceRegistry()
        
        assert registry.verify_provenance_chain("nonexistent") is False
    
    def test_get_provenance_chain(self):
        """Test getting full provenance chain."""
        registry = ExecutionProvenanceRegistry()
        
        record = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_0",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_456",
            timestamp="2026-02-19T12:00:00"
        )
        
        registry.record_execution_provenance(record)
        
        chain = registry.get_provenance_chain("exec_001")
        
        assert chain is not None
        assert isinstance(chain, ProvenanceChain)
        assert len(chain.records) == 1
    
    def test_get_audit_root(self):
        """Test getting audit root."""
        registry = ExecutionProvenanceRegistry()
        
        record = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_0",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_456",
            timestamp="2026-02-19T12:00:00"
        )
        
        registry.record_execution_provenance(record)
        
        audit_root = registry.get_audit_root("exec_001")
        
        assert audit_root == "audit_root_123"
    
    def test_get_executions_by_tenant(self):
        """Test getting executions by tenant."""
        registry = ExecutionProvenanceRegistry()
        
        for i in range(5):
            tenant_id = f"tenant_{i % 2}"  # Alternating tenants
            record = ExecutionProvenanceRecord(
                execution_id=f"exec_{i:03d}",
                tenant_id=tenant_id,
                contract_hash=f"hash_{i}",
                node_id="node_0",
                cluster_schedule_hash=f"schedule_{i}",
                audit_root=f"audit_{i}",
                execution_proof=f"proof_{i}",
                timestamp="2026-02-19T12:00:00"
            )
            registry.record_execution_provenance(record)
        
        tenant_0_execs = registry.get_executions_by_tenant("tenant_0")
        tenant_1_execs = registry.get_executions_by_tenant("tenant_1")
        
        assert len(tenant_0_execs) == 3  # exec_000, exec_002, exec_004
        assert len(tenant_1_execs) == 2  # exec_001, exec_003
    
    def test_get_executions_by_node(self):
        """Test getting executions by node."""
        registry = ExecutionProvenanceRegistry()
        
        for i in range(5):
            record = ExecutionProvenanceRecord(
                execution_id=f"exec_{i:03d}",
                tenant_id="tenant_123",
                contract_hash=f"hash_{i}",
                node_id=f"node_{i % 2}",  # Alternating nodes
                cluster_schedule_hash=f"schedule_{i}",
                audit_root=f"audit_{i}",
                execution_proof=f"proof_{i}",
                timestamp="2026-02-19T12:00:00"
            )
            registry.record_execution_provenance(record)
        
        node_0_execs = registry.get_executions_by_node("node_0")
        node_1_execs = registry.get_executions_by_node("node_1")
        
        assert len(node_0_execs) == 3  # exec_000, exec_002, exec_004
        assert len(node_1_execs) == 2  # exec_001, exec_003
    
    def test_compute_registry_hash(self):
        """Test computing registry hash."""
        registry = ExecutionProvenanceRegistry()
        
        record = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_0",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_456",
            timestamp="2026-02-19T12:00:00"
        )
        
        registry.record_execution_provenance(record)
        
        registry_hash = registry.compute_registry_hash()
        
        assert len(registry_hash) == 64  # SHA-256 hex length
    
    def test_multiple_records_same_execution(self):
        """Test recording multiple records for same execution."""
        registry = ExecutionProvenanceRegistry()
        
        record1 = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_0",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_456",
            timestamp="2026-02-19T12:00:00"
        )
        
        record2 = ExecutionProvenanceRecord(
            execution_id="exec_001",
            tenant_id="tenant_123",
            contract_hash="hash_abc",
            node_id="node_1",
            cluster_schedule_hash="schedule_xyz",
            audit_root="audit_root_123",
            execution_proof="proof_789",
            timestamp="2026-02-19T12:01:00"
        )
        
        registry.record_execution_provenance(record1)
        registry.record_execution_provenance(record2)
        
        chain = registry.get_provenance_chain("exec_001")
        
        assert chain is not None
        assert len(chain.records) == 2


# ============================================================================
# Tests for orchestrator_control_api.py
# ============================================================================

class TestOrchestratorControlAPI:
    """Tests for OrchestratorControlAPI class."""
    
    def test_init(self):
        """Test initialization of API."""
        api = OrchestratorControlAPI()
        
        assert api.get_audit_log() == []
    
    def test_submit_execution_request_success(self):
        """Test successful execution request submission."""
        api = OrchestratorControlAPI()
        
        result = api.submit_execution_request(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        assert "execution_id" in result
        assert result["status"] == "pending"
        assert "audit_id" in result
        assert "timestamp" in result
        assert result["protocol_version"] == PROTOCOL_VERSION
    
    def test_submit_execution_request_no_contract(self):
        """Test execution request without contract raises error."""
        api = OrchestratorControlAPI()
        
        with pytest.raises(ValueError, match="Runtime contract is required"):
            api.submit_execution_request(
                tenant_id="tenant_123",
                contract_id=None,
                input_data={"key": "value"}
            )
    
    def test_query_execution_status_exists(self):
        """Test querying status of existing execution."""
        api = OrchestratorControlAPI()
        
        submit_result = api.submit_execution_request(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        status = api.query_execution_status(submit_result["execution_id"])
        
        assert status is not None
        assert status["execution_id"] == submit_result["execution_id"]
        assert status["status"] == "pending"
        assert status["tenant_id"] == "tenant_123"
    
    def test_query_execution_status_not_found(self):
        """Test querying status of nonexistent execution."""
        api = OrchestratorControlAPI()
        
        status = api.query_execution_status("nonexistent_id")
        
        assert status is None
    
    def test_retrieve_execution_proof_exists(self):
        """Test retrieving proof of existing execution."""
        api = OrchestratorControlAPI()
        
        submit_result = api.submit_execution_request(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        proof = api.retrieve_execution_proof(submit_result["execution_id"])
        
        assert proof is not None
        assert proof["execution_id"] == submit_result["execution_id"]
        assert "input_hash" in proof
    
    def test_retrieve_execution_proof_not_found(self):
        """Test retrieving proof of nonexistent execution."""
        api = OrchestratorControlAPI()
        
        proof = api.retrieve_execution_proof("nonexistent_id")
        
        assert proof is None
    
    def test_list_cluster_nodes_empty(self):
        """Test listing cluster nodes when empty."""
        api = OrchestratorControlAPI()
        
        nodes = api.list_cluster_nodes()
        
        assert nodes == []
    
    def test_list_cluster_nodes_with_authority(self):
        """Test listing cluster nodes with membership authority."""
        authority = ClusterMembershipAuthority()
        
        descriptor = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        
        authority.register_trusted_node(descriptor)
        
        api = OrchestratorControlAPI(membership_authority=authority)
        
        nodes = api.list_cluster_nodes()
        
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "node_001"
    
    def test_get_cluster_root_empty(self):
        """Test getting cluster root when empty."""
        api = OrchestratorControlAPI()
        
        root = api.get_cluster_root()
        
        assert root["membership_hash"] == ""
        assert root["node_count"] == 0
        assert root["protocol_version"] == PROTOCOL_VERSION
    
    def test_get_cluster_root_with_authority(self):
        """Test getting cluster root with membership authority."""
        authority = ClusterMembershipAuthority()
        
        for i in range(3):
            descriptor = TrustedNodeDescriptor(
                node_id=f"node_{i:03d}",
                node_name=f"Worker Node {i}",
                public_key=f"pub_key_{i}",
                trust_level=i + 1,
                registered_at="2026-02-19T12:00:00"
            )
            authority.register_trusted_node(descriptor)
        
        api = OrchestratorControlAPI(membership_authority=authority)
        
        root = api.get_cluster_root()
        
        assert root["membership_hash"] != ""
        assert root["node_count"] == 3
        assert root["protocol_version"] == PROTOCOL_VERSION
    
    def test_audit_log_entries_created(self):
        """Test that audit log entries are created for operations."""
        api = OrchestratorControlAPI()
        
        api.submit_execution_request(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        api.query_execution_status("exec_001")
        
        api.list_cluster_nodes()
        
        audit_log = api.get_audit_log()
        
        assert len(audit_log) == 3
        assert audit_log[0].operation == "submit_execution_request"
        assert audit_log[1].operation == "query_execution_status"
        assert audit_log[2].operation == "list_cluster_nodes"
    
    def test_full_integration_with_provenance(self):
        """Test full integration with provenance registry."""
        provenance_registry = ExecutionProvenanceRegistry()
        authority = ClusterMembershipAuthority()
        
        # Register a node
        descriptor = TrustedNodeDescriptor(
            node_id="node_001",
            node_name="Worker Node 1",
            public_key="pub_key_abc",
            trust_level=5,
            registered_at="2026-02-19T12:00:00"
        )
        authority.register_trusted_node(descriptor)
        
        # Create API with dependencies
        api = OrchestratorControlAPI(
            provenance_registry=provenance_registry,
            membership_authority=authority
        )
        
        # Submit execution
        result = api.submit_execution_request(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        # Verify provenance was recorded
        provenance = provenance_registry.get_execution_provenance(result["execution_id"])
        
        assert provenance is not None
        assert provenance.tenant_id == "tenant_123"
        
        # Verify cluster nodes are accessible
        nodes = api.list_cluster_nodes()
        assert len(nodes) == 1
    
    def test_deterministic_execution_id_generation(self):
        """Test that execution ID generation uses deterministic components."""
        api = OrchestratorControlAPI()
        
        # Note: execution_id includes timestamp, so won't be identical
        # but should have consistent format
        result1 = api.submit_execution_request(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        result2 = api.submit_execution_request(
            tenant_id="tenant_123",
            contract_id="contract_456",
            input_data={"key": "value"}
        )
        
        # Both should have valid execution IDs
        assert len(result1["execution_id"]) == 16
        assert len(result2["execution_id"]) == 16
    
    def test_input_hash_computation(self):
        """Test that input hash is computed correctly."""
        api = OrchestratorControlAPI()
        
        input_data = {"key": "value", "number": 42}
        
        expected_hash = hashlib.sha256(
            json.dumps(input_data, sort_keys=True).encode()
        ).hexdigest()
        
        computed_hash = api._compute_input_hash(input_data)
        
        assert computed_hash == expected_hash
    
    def test_contract_hash_computation(self):
        """Test that contract hash is computed correctly."""
        api = OrchestratorControlAPI()
        
        contract_id = "contract_456"
        
        expected_hash = hashlib.sha256(contract_id.encode()).hexdigest()
        
        computed_hash = api._compute_contract_hash(contract_id)
        
        assert computed_hash == expected_hash
