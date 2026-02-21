"""
Phase 5 Control Plane Tests.
Tests for distributed orchestrator mesh, deterministic scheduling, and cluster management.
"""
import pytest
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from synapse.control_plane.cluster_manager import ClusterManager, NodeInfo, ClusterState
from synapse.control_plane.deterministic_scheduler import DeterministicScheduler, Task, ScheduledTask
from synapse.control_plane.node_registry import NodeRegistry, NodeRegistration
from synapse.control_plane.orchestrator_mesh import OrchestratorMesh, MeshState
from synapse.distributed_consensus.state_hash_consensus import StateHashConsensus, StateHash
from synapse.distributed_consensus.node_identity import NodeIdentityManager, NodeIdentity


# ============================================================================
# CLUSTER MANAGER TESTS
# ============================================================================

class TestClusterManager:
    """Tests for Cluster Manager"""
    
    @pytest.mark.asyncio
    async def test_register_node(self):
        """Test node registration"""
        manager = ClusterManager("test-cluster")
        
        node = NodeInfo(
            node_id="node1",
            public_key="pk1",
            endpoint="localhost:8080",
            capabilities=["fs:read", "fs:write"],
            registered_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        result = await manager.register_node(node)
        assert result == True
    
    @pytest.mark.asyncio
    async def test_duplicate_registration_rejected(self):
        """Test that duplicate registration is rejected"""
        manager = ClusterManager("test-cluster")
        
        node = NodeInfo(
            node_id="node1",
            public_key="pk1",
            endpoint="localhost:8080",
            capabilities=["fs:read"],
            registered_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        await manager.register_node(node)
        result = await manager.register_node(node)
        assert result == False
    
    @pytest.mark.asyncio
    async def test_unregister_node(self):
        """Test node unregistration"""
        manager = ClusterManager("test-cluster")
        
        node = NodeInfo(
            node_id="node1",
            public_key="pk1",
            endpoint="localhost:8080",
            capabilities=["fs:read"],
            registered_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        await manager.register_node(node)
        result = await manager.unregister_node("node1")
        assert result == True
    
    @pytest.mark.asyncio
    async def test_cluster_state_hash_deterministic(self):
        """Test that cluster state hash is deterministic"""
        manager = ClusterManager("test-cluster")
        
        node1 = NodeInfo(
            node_id="node1",
            public_key="pk1",
            endpoint="localhost:8080",
            capabilities=["fs:read"],
            registered_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        node2 = NodeInfo(
            node_id="node2",
            public_key="pk2",
            endpoint="localhost:8081",
            capabilities=["fs:write"],
            registered_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        await manager.register_node(node1)
        await manager.register_node(node2)
        
        state1 = await manager.get_cluster_state()
        state2 = await manager.get_cluster_state()
        
        assert state1.state_hash == state2.state_hash
    
    @pytest.mark.asyncio
    async def test_get_active_nodes(self):
        """Test getting active nodes"""
        manager = ClusterManager("test-cluster", heartbeat_timeout=30)
        
        node = NodeInfo(
            node_id="node1",
            public_key="pk1",
            endpoint="localhost:8080",
            capabilities=["fs:read"],
            registered_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        await manager.register_node(node)
        active = await manager.get_active_nodes()
        
        assert len(active) == 1
        assert active[0].node_id == "node1"


# ============================================================================
# DETERMINISTIC SCHEDULER TESTS
# ============================================================================

class TestDeterministicScheduler:
    """Tests for Deterministic Scheduler"""
    
    @pytest.mark.asyncio
    async def test_schedule_tasks_deterministic(self):
        """Test that scheduling is deterministic"""
        scheduler = DeterministicScheduler(seed=42)
        
        tasks = [
            Task(
                task_id="task1",
                required_capabilities=["fs:read"],
                priority=1,
                payload={},
                execution_seed=1
            ),
            Task(
                task_id="task2",
                required_capabilities=["fs:write"],
                priority=1,
                payload={},
                execution_seed=2
            )
        ]
        
        nodes = [
            {"node_id": "node1", "capabilities": ["fs:read", "fs:write"]},
            {"node_id": "node2", "capabilities": ["fs:read", "fs:write"]}
        ]
        
        # Schedule twice with same input
        result1 = await scheduler.schedule(tasks, nodes)
        result2 = await scheduler.schedule(tasks, nodes)
        
        # Should produce identical results
        assert len(result1) == len(result2)
        for r1, r2 in zip(result1, result2):
            assert r1.node_id == r2.node_id
            assert r1.schedule_hash == r2.schedule_hash
    
    @pytest.mark.asyncio
    async def test_capability_aware_scheduling(self):
        """Test that scheduling respects capabilities"""
        scheduler = DeterministicScheduler(seed=42)
        
        task = Task(
            task_id="task1",
            required_capabilities=["fs:write"],
            priority=1,
            payload={},
            execution_seed=1
        )
        
        nodes = [
            {"node_id": "node1", "capabilities": ["fs:read"]},  # No write capability
            {"node_id": "node2", "capabilities": ["fs:read", "fs:write"]}
        ]
        
        result = await scheduler.schedule([task], nodes)
        
        # Should only schedule to node2
        assert len(result) == 1
        assert result[0].node_id == "node2"
    
    @pytest.mark.asyncio
    async def test_no_capable_nodes(self):
        """Test handling when no nodes have required capabilities"""
        scheduler = DeterministicScheduler(seed=42)
        
        task = Task(
            task_id="task1",
            required_capabilities=["admin:all"],
            priority=1,
            payload={},
            execution_seed=1
        )
        
        nodes = [
            {"node_id": "node1", "capabilities": ["fs:read"]}
        ]
        
        result = await scheduler.schedule([task], nodes)
        
        # Should not schedule any tasks
        assert len(result) == 0


# ============================================================================
# NODE REGISTRY TESTS
# ============================================================================

class TestNodeRegistry:
    """Tests for Node Registry"""
    
    @pytest.mark.asyncio
    async def test_register_node(self):
        """Test node registration"""
        registry = NodeRegistry()
        
        registration = NodeRegistration(
            node_id="node1",
            public_key="pk1",
            certificate="cert1",
            capabilities=["fs:read"],
            registered_at=datetime.utcnow(),
            status="active"
        )
        
        result = await registry.register(registration)
        assert result == True
    
    @pytest.mark.asyncio
    async def test_registry_hash_deterministic(self):
        """Test that registry hash is deterministic"""
        registry = NodeRegistry()
        
        registration = NodeRegistration(
            node_id="node1",
            public_key="pk1",
            certificate="cert1",
            capabilities=["fs:read"],
            registered_at=datetime.utcnow(),
            status="active"
        )
        
        await registry.register(registration)
        
        hash1 = await registry.get_registry_hash()
        hash2 = await registry.get_registry_hash()
        
        assert hash1 == hash2


# ============================================================================
# ORCHESTRATOR MESH TESTS
# ============================================================================

class TestOrchestratorMesh:
    """Tests for Orchestrator Mesh"""
    
    @pytest.mark.asyncio
    async def test_join_mesh(self):
        """Test joining the mesh"""
        mesh = OrchestratorMesh("test-mesh", "node1")
        
        result = await mesh.join_mesh("node2", {"endpoint": "localhost:8080"})
        assert result == True
    
    @pytest.mark.asyncio
    async def test_mesh_state_hash(self):
        """Test mesh state hash"""
        mesh = OrchestratorMesh("test-mesh", "node1")
        
        await mesh.join_mesh("node2", {})
        
        state1 = await mesh.get_mesh_state()
        state2 = await mesh.get_mesh_state()
        
        assert state1.state_hash == state2.state_hash
    
    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        """Test broadcasting message"""
        mesh = OrchestratorMesh("test-mesh", "node1")
        
        message_id = await mesh.broadcast("test_type", {"data": "test"})
        
        assert message_id is not None
        assert len(message_id) > 0


# ============================================================================
# STATE HASH CONSENSUS TESTS
# ============================================================================

class TestStateHashConsensus:
    """Tests for State Hash Consensus"""
    
    @pytest.mark.asyncio
    async def test_consensus_all_agree(self):
        """Test consensus when all nodes agree"""
        consensus = StateHashConsensus(required_agreement=1.0)
        
        # Submit same hash from multiple nodes
        for node_id in ["node1", "node2", "node3"]:
            state_hash = StateHash(
                hash_value="abc123",
                timestamp=datetime.utcnow(),
                node_id=node_id,
                execution_id="exec1"
            )
            await consensus.submit_hash(state_hash)
        
        result = await consensus.check_consensus("exec1")
        
        assert result.agreed == True
        assert result.agreed_hash == "abc123"
        assert len(result.disagreeing_nodes) == 0
    
    @pytest.mark.asyncio
    async def test_consensus_disagreement(self):
        """Test consensus when nodes disagree"""
        consensus = StateHashConsensus(required_agreement=1.0)
        
        # Submit different hashes
        await consensus.submit_hash(StateHash(
            hash_value="hash1",
            timestamp=datetime.utcnow(),
            node_id="node1",
            execution_id="exec1"
        ))
        
        await consensus.submit_hash(StateHash(
            hash_value="hash2",
            timestamp=datetime.utcnow(),
            node_id="node2",
            execution_id="exec1"
        ))
        
        result = await consensus.check_consensus("exec1")
        
        assert result.agreed == False
    
    @pytest.mark.asyncio
    async def test_compute_state_hash_deterministic(self):
        """Test that state hash computation is deterministic"""
        consensus = StateHashConsensus()
        
        state = {"key": "value", "number": 42}
        
        hash1 = await consensus.compute_state_hash(state)
        hash2 = await consensus.compute_state_hash(state)
        
        assert hash1 == hash2


# ============================================================================
# NODE IDENTITY TESTS
# ============================================================================

class TestNodeIdentity:
    """Tests for Node Identity"""
    
    @pytest.mark.asyncio
    async def test_generate_identity(self):
        """Test identity generation"""
        manager = NodeIdentityManager()
        
        identity = await manager.generate_identity("node1")
        
        assert identity.node_id == "node1"
        assert len(identity.public_key) > 0
        assert len(identity.private_key) > 0
        assert len(identity.certificate) > 0
    
    @pytest.mark.asyncio
    async def test_verify_identity(self):
        """Test identity verification"""
        manager = NodeIdentityManager()
        
        identity = await manager.generate_identity("node1")
        result = await manager.verify_identity(identity)
        
        assert result == True
    
    @pytest.mark.asyncio
    async def test_revoke_identity(self):
        """Test identity revocation"""
        manager = NodeIdentityManager()
        
        identity = await manager.generate_identity("node1")
        result = await manager.revoke_identity("node1")
        
        assert result == True
        
        # Should fail verification after revocation
        result = await manager.verify_identity(identity)
        assert result == False


# ============================================================================
# SECURITY TESTS
# ============================================================================

class TestControlPlaneSecurity:
    """Security tests for Control Plane"""
    
    @pytest.mark.asyncio
    async def test_node_identity_spoofing_blocked(self):
        """Test that identity spoofing is blocked"""
        manager = NodeIdentityManager()
        
        # Generate legitimate identity
        identity = await manager.generate_identity("node1")
        
        # Create spoofed identity with same ID but different key
        spoofed = NodeIdentity(
            node_id="node1",
            public_key="fake_key",
            private_key="fake_private",
            certificate="fake_cert",
            created_at=datetime.utcnow(),
            expires_at=None
        )
        
        result = await manager.verify_identity(spoofed)
        assert result == False
    
    @pytest.mark.asyncio
    async def test_unauthorized_node_rejected(self):
        """Test that unauthorized nodes are rejected"""
        registry = NodeRegistry()
        
        # Try to register with invalid data
        registration = NodeRegistration(
            node_id="",  # Empty ID
            public_key="pk1",
            certificate="cert1",
            capabilities=["fs:read"],
            registered_at=datetime.utcnow(),
            status="active"
        )
        
        result = await registry.register(registration)
        assert result == False


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestControlPlaneIntegration:
    """Integration tests for Control Plane"""
    
    @pytest.mark.asyncio
    async def test_full_orchestration_flow(self):
        """Test full orchestration flow"""
        # 1. Create cluster manager
        cluster = ClusterManager("test-cluster")
        
        # 2. Register nodes
        node1 = NodeInfo(
            node_id="node1",
            public_key="pk1",
            endpoint="localhost:8080",
            capabilities=["fs:read", "fs:write"],
            registered_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        node2 = NodeInfo(
            node_id="node2",
            public_key="pk2",
            endpoint="localhost:8081",
            capabilities=["fs:read", "fs:write"],
            registered_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        await cluster.register_node(node1)
        await cluster.register_node(node2)
        
        # 3. Get cluster state
        state = await cluster.get_cluster_state()
        assert len(state.nodes) == 2
        
        # 4. Schedule tasks
        scheduler = DeterministicScheduler(seed=42)
        
        tasks = [
            Task(
                task_id="task1",
                required_capabilities=["fs:read"],
                priority=1,
                payload={},
                execution_seed=1
            )
        ]
        
        nodes = [
            {"node_id": "node1", "capabilities": ["fs:read", "fs:write"]},
            {"node_id": "node2", "capabilities": ["fs:read", "fs:write"]}
        ]
        
        scheduled = await scheduler.schedule(tasks, nodes)
        assert len(scheduled) == 1
    
    @pytest.mark.asyncio
    async def test_multi_node_identical_result(self):
        """Test that multiple nodes produce identical results"""
        consensus = StateHashConsensus(required_agreement=1.0)
        
        # Simulate same execution on multiple nodes
        state = {"result": "success", "value": 42}
        
        hash_value = await consensus.compute_state_hash(state)
        
        # Submit from multiple nodes
        for node_id in ["node1", "node2", "node3"]:
            await consensus.submit_hash(StateHash(
                hash_value=hash_value,
                timestamp=datetime.utcnow(),
                node_id=node_id,
                execution_id="exec1"
            ))
        
        result = await consensus.check_consensus("exec1")
        
        assert result.agreed == True
        assert result.agreed_hash == hash_value


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
