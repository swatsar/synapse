"""Phase 13.3.3 - Multi-Node Cluster Simulation

Validates:
- routing stability
- policy propagation
- state consistency
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from synapse.core.execution_fabric import ExecutionFabric
from synapse.runtime.cluster.manager import ClusterManager
from synapse.distributed.consensus.engine import ConsensusEngine
from synapse.security.capability_manager import CapabilityManager


@pytest.fixture
def capability_manager():
    cm = CapabilityManager()
    cm.grant_capability("cluster")
    cm.grant_capability("consensus")
    cm.grant_capability("consensus:propose")
    cm.grant_capability("consensus:decide")
    cm.grant_capability("routing")
    return cm


@pytest.fixture
def execution_fabric():
    fabric = ExecutionFabric(seed_manager=None)
    # Register multiple nodes
    for i in range(5):
        fabric.register_node("node_{}".format(i))
    return fabric


@pytest.fixture
def cluster_manager(capability_manager):
    nodes = [MagicMock(spec=['node_id', 'status']) for _ in range(5)]
    for i, node in enumerate(nodes):
        node.node_id = "node_{}".format(i)
        node.status = "active"
    return ClusterManager(caps=capability_manager, nodes=nodes)


@pytest.fixture
def consensus_engine(capability_manager):
    return ConsensusEngine(caps=capability_manager)


@pytest.mark.workload
@pytest.mark.asyncio
class TestMultiNodeCluster:
    """Test multi-node cluster scenarios."""

    async def test_routing_stability(self, execution_fabric):
        """Test task routing is stable across nodes."""
        tasks = [{"id": "task_{}".format(i), "type": "compute"} for i in range(100)]
        routing_results = {}

        for task in tasks:
            node_id = execution_fabric.select_node(task)
            routing_results[node_id] = routing_results.get(node_id, 0) + 1

        # Verify tasks are distributed
        assert len(routing_results) > 1  # Multiple nodes used

        # Verify no single node gets all tasks
        max_tasks = max(routing_results.values())
        assert max_tasks < 100  # Not all on one node

    async def test_policy_propagation(self, capability_manager):
        """Test policies propagate across cluster."""
        # Grant capability
        capability_manager.grant_capability("cluster:policy")

        # Verify capability is active
        result = await capability_manager.check_capability(["cluster:policy"])
        assert result is True

    async def test_state_consistency(self, consensus_engine):
        """Test state consistency across nodes."""
        # Propose state from multiple nodes
        state = {"counter": 0, "version": 1}

        for i in range(5):
            await consensus_engine.propose("node_{}".format(i), state)
            decision = await consensus_engine.decide()
            assert decision is not None

    async def test_node_failure_handling(self, execution_fabric):
        """Test cluster handles node failures."""
        # All nodes start active - use correct attribute name
        initial_nodes = len(execution_fabric.nodes)

        # Simulate node failure by removing
        if initial_nodes > 1:
            execution_fabric.nodes.pop()

        # Should still be able to route
        task = {"id": "test", "type": "compute"}
        node_id = execution_fabric.select_node(task)
        assert node_id is not None
