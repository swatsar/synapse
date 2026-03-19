"""Unit tests for Critic Agent. Phase 4 — Self-Evolution.

TDD per AGENT_ZERO_INTEGRATION.md §3.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase4
@pytest.mark.unit
class TestEvaluationResult:
    def test_eval_result_structure(self):
        from synapse.agents.critic import EvaluationResult
        er = EvaluationResult(success=True, score=0.9, feedback="Good job")
        assert er.protocol_version == PROTOCOL_VERSION
        d = er.to_dict()
        assert "success" in d
        assert "score" in d
        assert "feedback" in d
        assert "knowledge_gaps" in d
        assert "should_create_skill" in d


@pytest.mark.phase4
@pytest.mark.unit
class TestCriticAgentHeuristic:
    @pytest.fixture
    def critic(self):
        from synapse.agents.critic import CriticAgent
        return CriticAgent()

    @pytest.mark.asyncio
    async def test_completed_result_is_success(self, critic):
        result = await critic.evaluate({"status": "completed", "result": "done"}, task="test")
        assert result["success"] is True
        assert result["score"] == 1.0

    @pytest.mark.asyncio
    async def test_error_result_is_failure(self, critic):
        result = await critic.evaluate({"status": "error", "error": "Connection refused"}, task="fetch URL")
        assert result["success"] is False
        assert result["score"] < 0.5

    @pytest.mark.asyncio
    async def test_permission_error_triggers_gap(self, critic):
        result = await critic.evaluate({"status": "error", "error": "permission denied"}, task="read file")
        assert len(result["knowledge_gaps"]) > 0

    @pytest.mark.asyncio
    async def test_should_create_skill_on_gap(self, critic):
        result = await critic.evaluate(
            {"status": "error", "error": "Module not found: numpy"},
            task="perform matrix calculations"
        )
        assert result["should_create_skill"] is True

    @pytest.mark.asyncio
    async def test_score_normalized_0_to_1(self, critic):
        for status in ["completed", "error", "unknown"]:
            result = await critic.evaluate({"status": status}, task="test")
            assert 0.0 <= result["score"] <= 1.0

    @pytest.mark.asyncio
    async def test_protocol_version_in_result(self, critic):
        result = await critic.evaluate({"status": "completed"}, task="test")
        assert result["protocol_version"] == PROTOCOL_VERSION


@pytest.mark.phase4
@pytest.mark.unit
class TestCriticAgentWithLLM:
    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value={
            "content": '{"success": false, "score": 0.2, "feedback": "Failed to read file", "recommendations": ["check permissions"], "knowledge_gaps": ["fs:read capability needed"], "should_create_skill": true, "suggested_skill_task": "secure file reader"}',
            "usage": {}
        })
        return llm

    @pytest.fixture
    def critic(self, mock_llm):
        from synapse.agents.critic import CriticAgent
        return CriticAgent(llm_provider=mock_llm)

    @pytest.mark.asyncio
    async def test_llm_evaluation_used_when_available(self, critic):
        result = await critic.evaluate(
            {"status": "error", "error": "cannot read"},
            task="read config file"
        )
        assert result["should_create_skill"] is True
        assert len(result["knowledge_gaps"]) > 0
