"""Tests for consensus engine."""
import pytest
from unittest.mock import MagicMock


class TestConsensusEngine:
    """Test consensus engine."""

    @pytest.fixture
    def consensus_engine(self):
        """Create a consensus engine for testing."""
        from synapse.distributed.consensus.engine import ConsensusEngine
        from synapse.security.capability_manager import CapabilityManager

        caps = CapabilityManager()
        caps.grant_capability("consensus:propose")
        caps.grant_capability("consensus:decide")

        return ConsensusEngine(caps=caps)

    def test_consensus_engine_creation(self, consensus_engine):
        """Test consensus engine creation."""
        assert consensus_engine is not None

    @pytest.mark.asyncio
    async def test_propose(self, consensus_engine):
        """Test proposing a state."""
        await consensus_engine.propose("node1", {"test": "data"})
        assert "node1" in consensus_engine._states

    @pytest.mark.asyncio
    async def test_decide(self, consensus_engine):
        """Test deciding on a state."""
        await consensus_engine.propose("node1", {"test": "data1"})
        await consensus_engine.propose("node2", {"test": "data2"})
        state = await consensus_engine.decide()
        # Should return the state of the node with the smallest id
        assert state == {"test": "data1"}
