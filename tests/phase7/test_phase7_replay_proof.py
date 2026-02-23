"""
Phase 7: Replay Proof Tests
Protocol Version: 1.0

Tests for:
- Cross-node replay determinism
- Cluster audit proof
- Distributed execution verification
"""

import pytest
import hashlib
import json
from typing import Dict, List


class TestCrossNodeReplay:
    """Tests for cross-node replay determinism"""
    
    def test_replay_produces_identical_schedule_hash(self):
        """Replay must produce identical schedule hash"""
        from synapse.cluster_orchestration.cluster_scheduler import ClusterScheduler, ClusterSchedule
        
        # Original execution
        scheduler1 = ClusterScheduler()
        schedule1 = ClusterSchedule(
            schedule_id="schedule_1",
            tenant_id="tenant_1",
            node_assignments={"node_0": ["task_1"], "node_1": ["task_2"]},
            execution_seed=42,
            created_at="2026-02-23T00:00:00Z"
        )
        hash1 = scheduler1.compute_cluster_schedule_hash(schedule1)
        
        # Replay execution
        scheduler2 = ClusterScheduler()
        schedule2 = ClusterSchedule(
            schedule_id="schedule_1",
            tenant_id="tenant_1",
            node_assignments={"node_0": ["task_1"], "node_1": ["task_2"]},
            execution_seed=42,
            created_at="2026-02-23T00:00:00Z"
        )
        hash2 = scheduler2.compute_cluster_schedule_hash(schedule2)
        
        assert hash1 == hash2, "Replay must produce identical schedule hash"
    
    def test_replay_produces_identical_cluster_root(self):
        """Replay must produce identical cluster audit root"""
        from synapse.cluster_orchestration.federated_audit_coordinator import FederatedAuditCoordinator
        
        # Original execution
        coord1 = FederatedAuditCoordinator()
        coord1.collect_node_root("node_0", "root_aaa111")
        coord1.collect_node_root("node_1", "root_bbb222")
        coord1.collect_node_root("node_2", "root_ccc333")
        root1 = coord1.compute_cluster_root()
        
        # Replay execution
        coord2 = FederatedAuditCoordinator()
        coord2.collect_node_root("node_0", "root_aaa111")
        coord2.collect_node_root("node_1", "root_bbb222")
        coord2.collect_node_root("node_2", "root_ccc333")
        root2 = coord2.compute_cluster_root()
        
        assert root1 == root2, "Replay must produce identical cluster root"
    
    def test_replay_produces_identical_node_assignment(self):
        """Replay must produce identical node assignment"""
        from synapse.cluster_orchestration.distributed_execution_domain import DistributedExecutionDomain, NodeDescriptor
        
        # Original execution
        domain1 = DistributedExecutionDomain()
        for i in range(3):
            domain1.register_node(NodeDescriptor(
                node_id=f"node_{i}",
                node_name=f"Node {i}",
                capabilities=["fs:read"],
                resource_limits={"cpu_seconds": 100},
                endpoint=f"http://localhost:800{i}"
            ))
        assignment1 = domain1.assign_execution("tenant_1", "contract_1")
        
        # Replay execution
        domain2 = DistributedExecutionDomain()
        for i in range(3):
            domain2.register_node(NodeDescriptor(
                node_id=f"node_{i}",
                node_name=f"Node {i}",
                capabilities=["fs:read"],
                resource_limits={"cpu_seconds": 100},
                endpoint=f"http://localhost:800{i}"
            ))
        assignment2 = domain2.assign_execution("tenant_1", "contract_1")
        
        assert assignment1 == assignment2, "Replay must produce identical node assignment"


class TestClusterAuditProof:
    """Tests for cluster audit proof"""
    
    def test_cluster_root_is_sha256(self):
        """Cluster root must be valid SHA-256 hash"""
        from synapse.cluster_orchestration.federated_audit_coordinator import FederatedAuditCoordinator
        
        coord = FederatedAuditCoordinator()
        coord.collect_node_root("node_0", "a" * 64)
        coord.collect_node_root("node_1", "b" * 64)
        
        root = coord.compute_cluster_root()
        
        assert len(root) == 64, "Cluster root must be 64 characters"
        try:
            int(root, 16)
        except ValueError:
            pytest.fail("Cluster root must be valid hex string")
    
    def test_cluster_root_changes_with_different_inputs(self):
        """Cluster root must change with different node roots"""
        from synapse.cluster_orchestration.federated_audit_coordinator import FederatedAuditCoordinator
        
        coord1 = FederatedAuditCoordinator()
        coord1.collect_node_root("node_0", "a" * 64)
        root1 = coord1.compute_cluster_root()
        
        coord2 = FederatedAuditCoordinator()
        coord2.collect_node_root("node_0", "b" * 64)
        root2 = coord2.compute_cluster_root()
        
        assert root1 != root2, "Different inputs must produce different cluster root"
    
    def test_cluster_integrity_verification(self):
        """Cluster integrity verification must work"""
        from synapse.cluster_orchestration.federated_audit_coordinator import FederatedAuditCoordinator
        
        coord = FederatedAuditCoordinator()
        coord.collect_node_root("node_0", "a" * 64)
        coord.collect_node_root("node_1", "b" * 64)
        
        assert coord.verify_cluster_integrity() == True
    
    def test_federated_root_creation(self):
        """Federated root creation must work"""
        from synapse.cluster_orchestration.federated_audit_coordinator import FederatedAuditCoordinator
        
        coord = FederatedAuditCoordinator()
        coord.collect_node_root("node_0", "a" * 64)
        coord.collect_node_root("node_1", "b" * 64)
        
        fed_root = coord.create_federated_root()
        
        assert fed_root.aggregation_id is not None
        assert fed_root.global_root is not None
        assert len(fed_root.node_roots) == 2
        assert fed_root.protocol_version == "1.0"


class TestDistributedExecutionVerification:
    """Tests for distributed execution verification"""
    
    @pytest.mark.asyncio
    async def test_execution_proof_verification(self):
        """Execution proof verification must work"""
        from synapse.cluster_orchestration.orchestrator_runtime_bridge import OrchestratorRuntimeBridge, ExecutionProof
        
        bridge = OrchestratorRuntimeBridge()
        
        # Execute
        result = await bridge.execute_distributed("contract_1", {"data": "test"})
        
        # Verify
        proof = ExecutionProof(
            proof_id="proof_1",
            node_id="node_0",
            contract_id="contract_1",
            execution_hash=result.execution_hash,
            audit_root=bridge._compute_audit_root(result.execution_hash),
            timestamp="2026-02-23T00:00:00Z"
        )
        
        assert bridge.verify_remote_execution(proof) == True
    
    @pytest.mark.asyncio
    async def test_execution_is_deterministic(self):
        """Distributed execution must be deterministic"""
        from synapse.cluster_orchestration.orchestrator_runtime_bridge import OrchestratorRuntimeBridge
        
        bridge1 = OrchestratorRuntimeBridge()
        bridge2 = OrchestratorRuntimeBridge()
        
        result1 = await bridge1.execute_distributed("contract_1", {"data": "test"})
        result2 = await bridge2.execute_distributed("contract_1", {"data": "test"})
        
        assert result1.execution_hash == result2.execution_hash


class TestDeterminismProof:
    """Tests for determinism proof"""
    
    def test_all_components_produce_deterministic_hashes(self):
        """All components must produce deterministic hashes"""
        from synapse.cluster_orchestration.cluster_scheduler import ClusterScheduler, ClusterSchedule
        from synapse.cluster_orchestration.federated_audit_coordinator import FederatedAuditCoordinator
        from synapse.cluster_orchestration.distributed_execution_domain import DistributedExecutionDomain, NodeDescriptor
        
        # Run 10 times and verify all hashes are identical
        schedule_hashes = []
        cluster_roots = []
        domain_hashes = []
        
        for _ in range(10):
            # Schedule hash
            scheduler = ClusterScheduler()
            schedule = ClusterSchedule(
                schedule_id="schedule_1",
                tenant_id="tenant_1",
                node_assignments={"node_0": ["task_1"]},
                execution_seed=42,
                created_at="2026-02-23T00:00:00Z"
            )
            schedule_hashes.append(scheduler.compute_cluster_schedule_hash(schedule))
            
            # Cluster root
            coord = FederatedAuditCoordinator()
            coord.collect_node_root("node_0", "a" * 64)
            coord.collect_node_root("node_1", "b" * 64)
            cluster_roots.append(coord.compute_cluster_root())
            
            # Domain hash
            domain = DistributedExecutionDomain()
            for i in range(3):
                domain.register_node(NodeDescriptor(
                    node_id=f"node_{i}",
                    node_name=f"Node {i}",
                    capabilities=["fs:read"],
                    resource_limits={"cpu_seconds": 100},
                    endpoint=f"http://localhost:800{i}"
                ))
            domain_hashes.append(domain.compute_domain_hash())
        
        # All hashes must be identical
        assert len(set(schedule_hashes)) == 1, "Schedule hashes must be identical"
        assert len(set(cluster_roots)) == 1, "Cluster roots must be identical"
        assert len(set(domain_hashes)) == 1, "Domain hashes must be identical"
