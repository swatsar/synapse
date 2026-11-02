"""Unit tests for Learning Engine (metacognition). Phase 4 — Self-Evolution.

TDD per AGENT_ZERO_INTEGRATION.md §3.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase4
@pytest.mark.unit
class TestLearningEngineEvaluate:
    @pytest.fixture
    def memory(self):
        from synapse.memory.store import MemoryStore
        return MemoryStore(db_path=":memory:")

    @pytest.fixture
    def engine(self, memory):
        from synapse.learning.engine import LearningEngine
        return LearningEngine(memory=memory)

    @pytest.mark.asyncio
    async def test_evaluate_completed_is_success(self, engine):
        from synapse.learning.engine import SUCCESS
        result = await engine.evaluate({"status": "completed"})
        assert result == SUCCESS

    @pytest.mark.asyncio
    async def test_evaluate_error_is_failure(self, engine):
        from synapse.learning.engine import FAILURE
        result = await engine.evaluate({"status": "error", "error": "boom"})
        assert result == FAILURE

    @pytest.mark.asyncio
    async def test_evaluate_success_flag_true(self, engine):
        from synapse.learning.engine import SUCCESS
        result = await engine.evaluate({"success": True})
        assert result == SUCCESS

    @pytest.mark.asyncio
    async def test_evaluate_success_flag_false(self, engine):
        from synapse.learning.engine import FAILURE
        result = await engine.evaluate({"success": False})
        assert result == FAILURE

    @pytest.mark.asyncio
    async def test_process_runs_full_pipeline(self, engine):
        await engine.process({"status": "completed"}, task="do something", skill_name="read_file")
        # Should not raise

    @pytest.mark.asyncio
    async def test_analyze_patterns_returns_structure(self, engine):
        insights = await engine.analyze_patterns()
        assert "low_performing_skills" in insights
        assert "frequent_failure_tasks" in insights
        assert "capability_bottlenecks" in insights
        assert insights["protocol_version"] == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_optimize_prompts_returns_suggestion(self, engine):
        result = await engine.optimize_prompts("planner")
        assert "suggestion" in result
        assert result["protocol_version"] == PROTOCOL_VERSION


@pytest.mark.phase4
@pytest.mark.unit
class TestLearningEngineMetacognition:
    @pytest.fixture
    def memory(self):
        from synapse.memory.store import MemoryStore
        return MemoryStore(db_path=":memory:")

    @pytest.fixture
    def mock_developer(self):
        dev = AsyncMock()
        mock_skill = MagicMock()
        mock_skill.skill_id = "gen-001"
        mock_skill.name = "new_skill"
        dev.generate_skill = AsyncMock(return_value={"skill": mock_skill, "status": "ready"})
        return dev

    @pytest.fixture
    def engine(self, memory, mock_developer):
        from synapse.learning.engine import LearningEngine
        return LearningEngine(memory=memory, developer_agent=mock_developer)

    @pytest.mark.asyncio
    async def test_skill_deprecation_on_low_success_rate(self, engine):
        """After enough failures, skill should be tracked as low-performing."""
        for _ in range(6):
            await engine.process({"status": "error", "error": "fail"}, skill_name="bad_skill")
        insights = await engine.analyze_patterns()
        low = [s["skill"] for s in insights["low_performing_skills"]]
        assert "bad_skill" in low

    @pytest.mark.asyncio
    async def test_create_skill_triggered_after_3_failures(self, engine, mock_developer):
        """Three task failures should trigger CreateSkill."""
        task = "complex analysis task that always fails"
        for _ in range(3):
            await engine.process({"status": "error", "error": "fail"}, task=task)
        mock_developer.generate_skill.assert_called()
