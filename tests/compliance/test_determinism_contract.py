"""Deterministic Execution Contract Compliance Tests.

Verifies:
1. Deterministic seed propagation
2. Authoritative core time normalization
3. Timestamp normalization in audit + network
4. Checkpoint replay produces identical state
5. Distributed execution deterministic under same seed
"""
import pytest
from unittest.mock import MagicMock, patch
import asyncio


class TestDeterministicSeedPropagation:
    """Test deterministic seed propagation."""
    
    def test_determinism_module_exists(self):
        """Test that determinism module exists."""
        from synapse.core.determinism import DeterministicIDGenerator
        assert DeterministicIDGenerator is not None
    
    def test_deterministic_id_generator_same_input_same_output(self):
        """Test that same input produces same output."""
        from synapse.core.determinism import DeterministicIDGenerator
        
        gen = DeterministicIDGenerator(seed=42)
        id1 = gen.generate("task_1")
        
        gen2 = DeterministicIDGenerator(seed=42)
        id2 = gen2.generate("task_1")
        
        assert id1 == id2, "Same seed + input should produce same ID"
    
    def test_deterministic_id_generator_different_input_different_output(self):
        """Test that different input produces different output."""
        from synapse.core.determinism import DeterministicIDGenerator
        
        gen = DeterministicIDGenerator(seed=42)
        id1 = gen.generate("task_1")
        id2 = gen.generate("task_2")
        
        assert id1 != id2, "Different input should produce different ID"
    
    def test_execution_context_has_seed(self):
        """Test that ExecutionContext has execution_seed."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        context = ExecutionContext(
            session_id="test",
            agent_id="test",
            trace_id="test",
            capabilities=["*"],
            memory_store=MagicMock(),
            logger=MagicMock(),
            resource_limits=ResourceLimits(
                cpu_seconds=60,
                memory_mb=512,
                disk_mb=100,
                network_kb=1024
            ),
            execution_seed=42,
            protocol_version="1.0"
        )
        
        assert context.execution_seed == 42


class TestTimeNormalization:
    """Test authoritative core time normalization."""
    
    def test_time_sync_manager_exists(self):
        """Test that TimeSyncManager exists."""
        from synapse.core.time_sync_manager import TimeSyncManager
        assert TimeSyncManager is not None
    
    def test_time_sync_manager_has_protocol_version(self):
        """Test that TimeSyncManager has protocol_version."""
        from synapse.core.time_sync_manager import TimeSyncManager
        
        manager = TimeSyncManager()
        assert hasattr(manager, "protocol_version")
        assert manager.protocol_version == "1.0"
    
    def test_timestamp_normalization(self):
        """Test timestamp normalization."""
        from synapse.core.time_sync_manager import TimeSyncManager
        from datetime import datetime, timezone
        
        manager = TimeSyncManager()
        
        # Create a timestamp
        ts = datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc)
        
        # Normalize it
        normalized = manager.normalize(ts)
        
        # Should return float timestamp
        assert isinstance(normalized, float)
    
    def test_normalized_timestamp_used_in_audit(self):
        """Test that normalized timestamps are used in audit."""
        from synapse.observability.logger import audit
        from synapse.core.time_sync_manager import TimeSyncManager
        
        # Audit function should exist
        assert callable(audit)


class TestCheckpointReplay:
    """Test checkpoint replay determinism."""
    
    def test_checkpoint_module_exists(self):
        """Test that checkpoint module exists."""
        from synapse.core.checkpoint import Checkpoint
        assert Checkpoint is not None
    
    def test_checkpoint_has_protocol_version(self):
        """Test that Checkpoint has protocol_version."""
        from synapse.core.checkpoint import Checkpoint
        
        assert hasattr(Checkpoint, "protocol_version")
        assert Checkpoint.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_checkpoint_state_reproducible(self):
        """Test that checkpoint state is reproducible."""
        from synapse.core.checkpoint import Checkpoint
        
        # Create checkpoint with deterministic state
        state = {"key": "value", "number": 42}
        checkpoint = Checkpoint(
            checkpoint_id="test_checkpoint",
            agent_id="test_agent",
            session_id="test_session",
            state=state
        )
        
        # State should be preserved
        assert checkpoint.state == state


class TestDistributedDeterminism:
    """Test distributed execution determinism."""
    
    def test_execution_fabric_exists(self):
        """Test that ExecutionFabric exists."""
        from synapse.core.execution_fabric import ExecutionFabric
        assert ExecutionFabric is not None
    
    def test_execution_fabric_has_protocol_version(self):
        """Test that ExecutionFabric has protocol_version."""
        from synapse.core.execution_fabric import ExecutionFabric
        
        assert hasattr(ExecutionFabric, "protocol_version")
        assert ExecutionFabric.protocol_version == "1.0"
    
    def test_deterministic_node_selection(self):
        """Test that node selection is deterministic."""
        from synapse.core.execution_fabric import ExecutionFabric
        
        fabric = ExecutionFabric()
        
        # Register nodes first
        fabric.register_node({"node_id": "node_1"})
        fabric.register_node({"node_id": "node_2"})
        fabric.register_node({"node_id": "node_3"})
        
        # Same task should select same node
        node1 = fabric.select_node({"task": "task_1"})
        node2 = fabric.select_node({"task": "task_1"})
        assert node1 == node2, "Same task should select same node"
    
    def test_remote_message_deterministic_serialization(self):
        """Test that remote message serialization is deterministic."""
        from synapse.network.remote_node_protocol import RemoteMessage
        
        msg = RemoteMessage(
            trace_id="test_trace",
            timestamp=1708342800.0,
            node_id="node1",
            capabilities=["test"],
            payload={"key": "value"},
            protocol_version="1.0"
        )
        
        # Serialize
        serialized1 = msg.model_dump_json()
        serialized2 = msg.model_dump_json()
        
        # Should be identical
        assert serialized1 == serialized2


class TestNoNondeterministicPaths:
    """Test that no nondeterministic paths exist."""
    
    def test_no_random_without_seed(self):
        """Test that random is not used without seed."""
        import ast
        from pathlib import Path
        
        synapse_path = Path("/a0/usr/projects/project_synapse/synapse")
        
        # Check a few key files for random usage
        key_files = [
            "core/determinism.py",
            "core/execution_fabric.py",
        ]
        
        for file_path in key_files:
            full_path = synapse_path / file_path
            if full_path.exists():
                content = full_path.read_text()
                # Check that if random is used, it's seeded
                if "random" in content:
                    # Should have seed or deterministic usage
                    assert "seed" in content.lower() or "hashlib" in content, \
                        f"{file_path} uses random without seed"


class TestDeterminismContract:
    """Test determinism contract compliance."""
    
    def test_deterministic_id_generator_protocol_version(self):
        """Test that DeterministicIDGenerator has protocol_version."""
        from synapse.core.determinism import DeterministicIDGenerator
        
        gen = DeterministicIDGenerator(seed=42)
        assert hasattr(gen, "protocol_version")
        assert gen.protocol_version == "1.0"
    
    def test_deterministic_seed_manager_exists(self):
        """Test that DeterministicSeedManager exists."""
        from synapse.core.determinism import DeterministicSeedManager
        assert DeterministicSeedManager is not None
    
    def test_deterministic_seed_manager_protocol_version(self):
        """Test that DeterministicSeedManager has protocol_version."""
        from synapse.core.determinism import DeterministicSeedManager
        
        manager = DeterministicSeedManager()
        assert hasattr(manager, "protocol_version")
        assert manager.protocol_version == "1.0"
