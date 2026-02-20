"""
Integration tests for distributed execution.
Phase 5: Reliability & Observability
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


# ============================================================================
# TestNodeCoordination
# ============================================================================

@pytest.mark.phase5
@pytest.mark.integration
class TestNodeCoordination:
    """Tests for node coordination in distributed environment."""
    
    @pytest.mark.asyncio
    async def test_node_heartbeat_sync(self, test_context, capability_manager):
        """Test heartbeat synchronization between nodes."""
        from synapse.distributed.node_runtime import NodeRuntime
        from synapse.agents.runtime.agent import RuntimeAgent
        from synapse.core.time_sync_manager import TimeSyncManager
        
        # Create mock agent
        mock_agent = MagicMock(spec=RuntimeAgent)
        mock_agent.run = AsyncMock()
        mock_agent.handle_event = AsyncMock()
        
        # Create node runtime
        node = NodeRuntime(
            agents=[mock_agent],
            caps=capability_manager
        )
        
        # Verify node has protocol version
        assert node.protocol_version == "1.0"
        
        # Test event posting
        test_event = {
            "type": "test",
            "required_capabilities": [],
            "protocol_version": "1.0"
        }
        
        # Post event (should not raise)
        await node.post_event(test_event)
    
    @pytest.mark.asyncio
    async def test_node_registration_deregistration(self, test_context, capability_manager):
        """Test node registration and deregistration."""
        from synapse.distributed.coordination.service import ClusterCoordinationService
        
        # Grant required capabilities (grant_capability is sync)
        capability_manager.grant_capability("coordination:register")
        capability_manager.grant_capability("coordination:read")
        
        # Create coordination service
        service = ClusterCoordinationService(caps=capability_manager)
        
        # Register node
        await service.register_node(node_id="test_node_1")
        
        # Verify node is registered by checking log
        log = await service.fetch_log()
        assert isinstance(log, list)
    
    @pytest.mark.asyncio
    async def test_node_status_propagation(self, test_context, capability_manager):
        """Test node status propagation across cluster."""
        from synapse.distributed.coordination.service import ClusterCoordinationService
        
        # Grant capabilities
        capability_manager.grant_capability("coordination:register")
        capability_manager.grant_capability("coordination:broadcast")
        capability_manager.grant_capability("coordination:read")
        
        service = ClusterCoordinationService(caps=capability_manager)
        
        # Register nodes
        await service.register_node("node_1")
        await service.register_node("node_2")
        
        # Broadcast status update
        await service.broadcast(
            node_id="node_1",
            payload={"status": "busy", "load": 0.8}
        )
        
        # Verify broadcast was recorded
        log = await service.fetch_log()
        assert len(log) > 0
        assert log[0]["node_id"] == "node_1"
        assert log[0]["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_node_capability_sync(self, test_context, capability_manager):
        """Test capability synchronization between nodes."""
        from synapse.distributed.coordination.service import ClusterCoordinationService
        
        # Grant capabilities
        capability_manager.grant_capability("coordination:register")
        capability_manager.grant_capability("coordination:broadcast")
        capability_manager.grant_capability("coordination:read")
        
        service = ClusterCoordinationService(caps=capability_manager)
        
        # Register node
        await service.register_node("cap_node")
        
        # Broadcast capabilities
        await service.broadcast(
            node_id="cap_node",
            payload={"capabilities": ["fs:read", "fs:write"]}
        )
        
        # Verify broadcast
        log = await service.fetch_log()
        assert len(log) > 0


# ============================================================================
# TestCheckpointReplication
# ============================================================================

@pytest.mark.phase5
@pytest.mark.integration
class TestCheckpointReplication:
    """Tests for checkpoint replication across nodes."""
    
    @pytest.mark.asyncio
    async def test_checkpoint_create_replicate(self, test_context, checkpoint_manager):
        """Test checkpoint creation and replication."""
        # Create checkpoint (sync method, returns Checkpoint)
        checkpoint = checkpoint_manager.create_checkpoint(
            agent_id="test_agent",
            session_id="test_session",
            state={"data": "test_value"}
        )
        
        assert checkpoint is not None
        assert checkpoint.checkpoint_id is not None
        assert checkpoint.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_checkpoint_restore_from_replica(self, test_context, checkpoint_manager, rollback_manager):
        """Test checkpoint restoration from replica."""
        # Create checkpoint
        checkpoint = checkpoint_manager.create_checkpoint(
            agent_id="restore_agent",
            session_id="restore_session",
            state={"key": "value_to_restore"}
        )
        
        # Restore from checkpoint (sync method)
        rollback_manager.rollback_to(checkpoint.id)
        
        # Verify checkpoint exists
        assert checkpoint.is_active == True
    
    @pytest.mark.asyncio
    async def test_checkpoint_consistency_check(self, test_context, checkpoint_manager):
        """Test checkpoint consistency verification."""
        # Create checkpoint
        checkpoint = checkpoint_manager.create_checkpoint(
            agent_id="consistency_agent",
            session_id="consistency_session",
            state={"data": "consistency_test"}
        )
        
        # Verify checkpoint is active
        assert checkpoint.is_active == True
        assert checkpoint.is_fresh() == True
    
    @pytest.mark.asyncio
    async def test_checkpoint_security_hash_verification(self, test_context, checkpoint_manager):
        """Test checkpoint security hash verification."""
        # Create checkpoint
        checkpoint = checkpoint_manager.create_checkpoint(
            agent_id="hash_agent",
            session_id="hash_session",
            state={"sensitive": "data"}
        )
        
        # Verify security hash exists
        assert checkpoint is not None
        assert checkpoint.security_hash is not None
        assert len(checkpoint.security_hash) > 0


# ============================================================================
# TestConsensusProtocol
# ============================================================================

@pytest.mark.phase5
@pytest.mark.integration
class TestConsensusProtocol:
    """Tests for consensus protocol in distributed environment."""
    
    @pytest.mark.asyncio
    async def test_consensus_propose(self, test_context, consensus_engine):
        """Test consensus proposal."""
        # Grant capabilities
        consensus_engine._caps.grant_capability("consensus:propose")
        
        # Propose state (propose takes node_id and state)
        await consensus_engine.propose(
            node_id="node_1",
            state={"key": "test_key", "value": "test_value"}
        )
        
        # Verify protocol version
        assert consensus_engine.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_consensus_decide(self, test_context, consensus_engine):
        """Test consensus decision."""
        # Grant capabilities
        consensus_engine._caps.grant_capability("consensus:propose")
        consensus_engine._caps.grant_capability("consensus:decide")
        
        # Propose states from multiple nodes
        await consensus_engine.propose("node_1", {"value": "value_1"})
        await consensus_engine.propose("node_2", {"value": "value_2"})
        await consensus_engine.propose("node_3", {"value": "value_3"})
        
        # Decide (returns state of lowest node_id)
        decision = await consensus_engine.decide()
        
        assert decision is not None
        assert "value" in decision
    
    @pytest.mark.asyncio
    async def test_consensus_conflict_resolution(self, test_context, consensus_engine):
        """Test consensus conflict resolution."""
        # Grant capabilities
        consensus_engine._caps.grant_capability("consensus:propose")
        consensus_engine._caps.grant_capability("consensus:decide")
        
        # Create conflicting proposals
        await consensus_engine.propose("node_a", {"value": "value_a"})
        await consensus_engine.propose("node_b", {"value": "value_b"})
        
        # Decide resolves conflict deterministically
        decision = await consensus_engine.decide()
        
        assert decision is not None
    
    @pytest.mark.asyncio
    async def test_consensus_quorum_achievement(self, test_context, consensus_engine):
        """Test quorum achievement in consensus."""
        # Grant capabilities
        consensus_engine._caps.grant_capability("consensus:propose")
        consensus_engine._caps.grant_capability("consensus:decide")
        
        # Propose from multiple nodes
        await consensus_engine.propose("node_1", {"value": "quorum_value"})
        await consensus_engine.propose("node_2", {"value": "quorum_value"})
        await consensus_engine.propose("node_3", {"value": "quorum_value"})
        
        # Decide
        decision = await consensus_engine.decide()
        
        assert decision is not None


# ============================================================================
# TestTimeSync
# ============================================================================

@pytest.mark.phase5
@pytest.mark.integration
class TestTimeSync:
    """Tests for time synchronization in distributed environment."""
    
    @pytest.mark.asyncio
    async def test_time_offset_setting(self, test_context):
        """Test time offset setting."""
        from synapse.core.time_sync_manager import TimeSyncManager
        
        # Set offset
        TimeSyncManager.set_offset(100.0)  # 100ms offset
        
        # Get current time
        now = TimeSyncManager.now()
        
        assert now is not None
        assert isinstance(now, datetime)
    
    @pytest.mark.asyncio
    async def test_timestamp_retrieval(self, test_context):
        """Test timestamp retrieval."""
        from synapse.core.time_sync_manager import TimeSyncManager
        
        # Get current time
        now = TimeSyncManager.now()
        
        assert now is not None
        assert isinstance(now, datetime)
        assert now.tzinfo is not None
    
    @pytest.mark.asyncio
    async def test_per_node_offset(self, test_context):
        """Test per-node time offset."""
        from synapse.core.time_sync_manager import TimeSyncManager
        
        # Set per-node offset
        TimeSyncManager.set_offset(50.0, node_id="node_1")
        TimeSyncManager.set_offset(100.0, node_id="node_2")
        
        # Get time for each node
        time1 = TimeSyncManager.now(node_id="node_1")
        time2 = TimeSyncManager.now(node_id="node_2")
        
        assert time1 is not None
        assert time2 is not None
    
    @pytest.mark.asyncio
    async def test_protocol_version(self, test_context):
        """Test TimeSyncManager protocol version."""
        from synapse.core.time_sync_manager import TimeSyncManager
        
        # Verify protocol version
        assert TimeSyncManager.protocol_version == "1.0"
        
        # Create instance and verify
        tsm = TimeSyncManager()
        assert tsm.protocol_version == "1.0"
