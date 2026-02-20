"""Tests for learning engine."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestLearningEngine:
    """Test learning engine."""

    @pytest.fixture
    def memory_store(self):
        """Create a memory store for testing."""
        from synapse.memory.store import MemoryStore
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = MemoryStore(db_path=db_path)
            yield store

    @pytest.mark.asyncio
    async def test_learning_engine_creation(self, memory_store):
        """Test learning engine creation."""
        from synapse.learning.engine import LearningEngine
        engine = LearningEngine(memory_store)
        assert engine is not None

    @pytest.mark.asyncio
    async def test_learning_engine_evaluate_success(self, memory_store):
        """Test learning engine evaluate success."""
        from synapse.learning.engine import LearningEngine, SUCCESS
        engine = LearningEngine(memory_store)
        result = await engine.evaluate({"success": True})
        assert result == SUCCESS

    @pytest.mark.asyncio
    async def test_learning_engine_evaluate_failure(self, memory_store):
        """Test learning engine evaluate failure."""
        from synapse.learning.engine import LearningEngine, FAILURE
        engine = LearningEngine(memory_store)
        result = await engine.evaluate({"success": False})
        assert result == FAILURE

    @pytest.mark.asyncio
    async def test_learning_engine_feedback(self, memory_store):
        """Test learning engine feedback."""
        from synapse.learning.engine import LearningEngine, SUCCESS
        engine = LearningEngine(memory_store)
        await engine.feedback({"success": True}, SUCCESS)
