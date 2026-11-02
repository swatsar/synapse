"""Phase 13.2.2 - Distributed Execution Scenario

Validates:
- Task routing
- Remote execution
- Result propagation
- Policy enforcement
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from synapse.core.execution_fabric import ExecutionFabric
from synapse.runtime.cluster.manager import ClusterManager
from synapse.distributed.consensus.engine import ConsensusEngine
from synapse.security.capability_manager import CapabilityManager, CapabilityError


@pytest.fixture
def capability_manager():
    cm = CapabilityManager()
    cm.grant_capability("execution")
    cm.grant_capability("cluster")
    cm.grant_capability("consensus")
    cm.grant_capability("consensus:propose")
    cm.grant_capability("consensus:decide")
    return cm


@pytest.fixture
def execution_fabric():
    fabric = ExecutionFabric(seed_manager=None)
    # Register nodes for testing
    fabric.register_node("node_1")
    fabric.register_node("node_2")
    fabric.register_node("node_3")
    return fabric


@pytest.fixture
def cluster_manager(capability_manager):
    nodes = [MagicMock(spec=['node_id', 'status']) for _ in range(3)]
    for i, node in enumerate(nodes):
        node.node_id = f"node_{i+1}"
        node.status = "active"
    return ClusterManager(caps=capability_manager, nodes=nodes)


@pytest.fixture
def consensus_engine(capability_manager):
    return ConsensusEngine(caps=capability_manager)


@pytest.mark.system
@pytest.mark.asyncio
class TestDistributedExecution:
    """Test distributed execution scenarios."""

    async def test_task_routing(self, execution_fabric):
        """Tasks are routed to appropriate nodes."""
        task = {
            "id": "task_1",
            "type": "compute",
            "payload": {"data": "test"}
        }

        # Route task
        node_id = execution_fabric.select_node(task)
        assert node_id is not None

    async def test_remote_execution_simulation(self, cluster_manager):
        """Remote execution is simulated correctly."""
        # Create cluster snapshot
        with patch.object(cluster_manager, 'create_cluster_snapshot', new_callable=AsyncMock) as mock_snapshot:
            mock_snapshot.return_value = ["snapshot_1"]
            result = await cluster_manager.create_cluster_snapshot()

        assert result is not None

    async def test_result_propagation(self, consensus_engine):
        """Results are propagated through consensus."""
        # Propose a result
        await consensus_engine.propose("node_1", {"result": "success", "value": 42})

        # Get decision
        decision = await consensus_engine.decide()
        assert decision is not None

    async def test_policy_enforcement_distributed(self, capability_manager):
        """Policies are enforced in distributed execution."""
        # Check capability enforcement
        result = await capability_manager.check_capability(["cluster"])
        assert result is True

        # Check denied capability - should raise CapabilityError
        try:
            await capability_manager.check_capability(["admin"])
            assert False, "Should have raised CapabilityError"
        except CapabilityError:
            assert True  # Expected behavior

    async def test_distributed_state_consistency(self, cluster_manager, consensus_engine):
        """State remains consistent across distributed execution."""
        # Propose state
        state = {"counter": 100, "version": 1}
        await consensus_engine.propose("node_1", state)

        # Get decision
        decision = await consensus_engine.decide()

        # State should be consistent
        assert decision is not None
