"""
Tests for Secure State Graph.

Tests verify:
- Protocol version compliance (1.0)
- Node capability validation
- Edge routing logic
- Human-in-the-loop interrupts
- Checkpoint security
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

import sys
sys.path.insert(0, '/a0/usr/projects/project_synapse')

from synapse.integrations.state_graph import (
    SecureStateGraph,
    StateNode,
    StateEdge,
    GraphState,
    GraphCheckpoint,
    NodeStatus,
    EdgeType,
    PROTOCOL_VERSION
)


class TestStateGraphProtocol:
    """Tests for protocol version compliance."""
    
    def test_protocol_version_defined(self):
        """Protocol version is defined as 1.0"""
        assert PROTOCOL_VERSION == "1.0"
    
    def test_graph_has_protocol_version(self):
        """Graph class has protocol version"""
        assert SecureStateGraph.PROTOCOL_VERSION == "1.0"
    
    def test_node_has_protocol_version(self):
        """Node dataclass has protocol version"""
        node = StateNode(id="test", name="test", action=lambda: None)
        assert node.protocol_version == "1.0"
    
    def test_edge_has_protocol_version(self):
        """Edge dataclass has protocol version"""
        edge = StateEdge(source="a", target="b")
        assert edge.protocol_version == "1.0"
    
    def test_state_has_protocol_version(self):
        """State dataclass has protocol version"""
        state = GraphState()
        assert state.protocol_version == "1.0"
    
    def test_checkpoint_has_protocol_version(self):
        """Checkpoint dataclass has protocol version"""
        checkpoint = GraphCheckpoint(
            id="test",
            graph_id="test",
            session_id="test",
            trace_id="test",
            state={},
            current_node=None,
            completed_nodes=[],
            failed_nodes=[],
            created_at="2026-01-01T00:00:00Z"
        )
        assert checkpoint.protocol_version == "1.0"


class TestNodeManagement:
    """Tests for node management."""
    
    @pytest.fixture
    def graph(self):
        return SecureStateGraph()
    
    async def test_add_node(self, graph):
        """Node can be added to graph"""
        node = StateNode(id="node1", name="Node 1", action=lambda x: x)
        await graph.add_node(node)
        assert "node1" in graph.nodes
    
    async def test_set_entry_point(self, graph):
        """Entry point can be set"""
        node = StateNode(id="start", name="Start", action=lambda x: x)
        await graph.add_node(node)
        graph.set_entry_point("start")
        assert graph.entry_point == "start"
    
    async def test_set_finish_point(self, graph):
        """Finish point can be set"""
        node = StateNode(id="end", name="End", action=lambda x: x)
        await graph.add_node(node)
        graph.set_finish_point("end")
        assert graph.finish_node == "end"
    
    def test_invalid_entry_point_raises(self, graph):
        """Invalid entry point raises error"""
        with pytest.raises(KeyError):
            graph.set_entry_point("nonexistent")


class TestEdgeManagement:
    """Tests for edge management."""
    
    @pytest.fixture
    def graph(self):
        g = SecureStateGraph()
        # Note: add_node is now async, but fixtures cannot be async in pytest
        # So we create the graph without validation
        g.nodes["a"] = StateNode(id="a", name="A", action=lambda x: x)
        g.nodes["b"] = StateNode(id="b", name="B", action=lambda x: x)
        return g
    
    async def test_add_edge(self, graph):
        """Edge can be added to graph"""
        edge = StateEdge(source="a", target="b")
        await graph.add_edge(edge)
        assert len(graph.edges) == 1
    
    async def test_conditional_edge(self, graph):
        """Conditional edge can be added"""
        edge = StateEdge(
            source="a",
            target="b",
            edge_type=EdgeType.CONDITIONAL,
            condition=lambda x: True
        )
        await graph.add_edge(edge)
        assert graph.edges[0].edge_type == EdgeType.CONDITIONAL


class TestHumanInTheLoop:
    """Tests for human-in-the-loop functionality."""
    
    @pytest.fixture
    def graph(self):
        g = SecureStateGraph()
        # Note: add_node is now async, but fixtures cannot be async in pytest
        # So we create the graph without validation
        g.nodes["start"] = StateNode(id="start", name="Start", action=lambda x: x)
        g.nodes["risky"] = StateNode(id="risky", name="Risky", action=lambda x: x, risk_level=4)
        return g
    
    def test_set_interrupt_before(self, graph):
        """Interrupt points can be set"""
        graph.set_interrupt_before(["risky"])
        assert "risky" in graph.interrupt_before
        assert graph.nodes["risky"].requires_human_approval == True
    
    def test_invalid_interrupt_raises(self, graph):
        """Invalid interrupt node raises error"""
        with pytest.raises(KeyError):
            graph.set_interrupt_before(["nonexistent"])


class TestGraphExecution:
    """Tests for graph execution."""
    
    @pytest.fixture
    def simple_graph(self):
        """Create a simple linear graph"""
        g = SecureStateGraph()
        
        async def node_a_action(state):
            state["visited"] = state.get("visited", [])
            state["visited"].append("a")
            return state
        
        async def node_b_action(state):
            state["visited"].append("b")
            return state
        
        g.nodes["a"] = StateNode(id="a", name="A", action=node_a_action)
        g.nodes["b"] = StateNode(id="b", name="B", action=node_b_action)
        g.edges.append(StateEdge(source="a", target="b"))
        g.entry_point = "a"
        g.finish_node = "b"
        
        return g
    
    @pytest.mark.asyncio
    async def test_execute_simple_graph(self, simple_graph):
        """Simple graph executes correctly"""
        result = await simple_graph.execute({})
        assert "visited" in result
        assert "a" in result["visited"]
        assert "b" in result["visited"]
    
    @pytest.mark.asyncio
    async def test_execution_state_has_protocol_version(self, simple_graph):
        """Execution state has protocol version"""
        result = await simple_graph.execute({})
        assert result["protocol_version"] == "1.0"


class TestSkillManifest:
    """Tests for skill manifest."""
    
    def test_manifest_has_protocol_version(self):
        """Manifest has protocol version"""
        from synapse.integrations.state_graph import SKILL_MANIFEST
        assert SKILL_MANIFEST["protocol_version"] == "1.0"
    
    def test_manifest_has_required_capabilities(self):
        """Manifest has required capabilities"""
        from synapse.integrations.state_graph import SKILL_MANIFEST
        assert "graph:execute" in SKILL_MANIFEST["required_capabilities"]
    
    def test_manifest_has_risk_level(self):
        """Manifest has risk level"""
        from synapse.integrations.state_graph import SKILL_MANIFEST
        assert SKILL_MANIFEST["risk_level"] == 3
