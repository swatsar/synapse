"""Golden Master Tests for critical LLM workflows.

Protocol Version: 1.0
TDD Specification: v1.2 FINAL

Tests the STRUCTURE of outputs, not exact text, so LLM variations are tolerated.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase4
@pytest.mark.unit
class TestDeveloperAgentGolden:
    """Golden master tests for DeveloperAgent output structure."""

    @pytest.fixture
    def mock_llm(self):
        provider = AsyncMock()
        provider.generate = AsyncMock(return_value={
            "content": "result = {'answer': 'done', 'status': 'ok'}",
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 50, "completion_tokens": 20},
        })
        return provider

    @pytest.fixture
    def developer(self, mock_llm):
        from synapse.agents.developer import DeveloperAgent
        return DeveloperAgent(llm_provider=mock_llm)

    @pytest.mark.asyncio
    async def test_generate_skill_structure(self, developer):
        """Golden: generate_skill() returns correct structure."""
        result = await developer.generate_skill("read a text file and return its content")
        assert isinstance(result, dict)
        assert "skill" in result
        assert "status" in result
        assert result.get("protocol_version") == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_generated_skill_has_required_fields(self, developer):
        """Golden: GeneratedSkill has all required fields."""
        result = await developer.generate_skill("process JSON data")
        skill = result["skill"]
        assert skill.skill_id
        assert skill.name
        assert skill.code
        assert skill.tests
        assert isinstance(skill.required_capabilities, list)
        assert isinstance(skill.risk_level, int)
        assert 1 <= skill.risk_level <= 5
        assert skill.protocol_version == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_generated_code_is_valid_python(self, developer):
        """Golden: generated code is syntactically valid Python."""
        import ast
        result = await developer.generate_skill("fetch data from a URL")
        skill = result["skill"]
        ast.parse(skill.code)  # Raises SyntaxError if invalid

    @pytest.mark.asyncio
    async def test_ast_scan_blocks_dangerous_code(self, developer):
        """Golden: AST scan blocks dangerous patterns."""
        issues = developer._ast_security_scan("import os\nos.system('rm -rf /')")
        assert len(issues) > 0
        assert any("os" in i for i in issues)

    @pytest.mark.asyncio
    async def test_ast_scan_allows_safe_code(self, developer):
        """Golden: AST scan passes safe code."""
        safe_code = "from pathlib import Path\nresult = Path('.').exists()"
        issues = developer._ast_security_scan(safe_code)
        assert len(issues) == 0


@pytest.mark.phase3
@pytest.mark.unit
class TestPlannerAgentGolden:
    """Golden master tests for PlannerAgent output structure."""

    @pytest.fixture
    def mock_llm(self):
        provider = AsyncMock()
        provider.generate = AsyncMock(return_value={
            "content": '{"steps": [{"step_id": "step_1", "action": "Read file", "skill": "read_file", "params": {}, "required_capabilities": ["fs:read"], "risk_level": 1}], "risk_level": 1, "reasoning": "Simple read"}',
            "model": "gpt-4o-mini",
            "usage": {},
        })
        return provider

    @pytest.fixture
    def planner(self, mock_llm):
        from synapse.agents.planner import PlannerAgent
        return PlannerAgent(llm_provider=mock_llm)

    @pytest.mark.asyncio
    async def test_plan_has_required_fields(self, planner):
        """Golden: ActionPlan has required structure."""
        plan = await planner.create_plan("Read a configuration file")
        assert plan.plan_id
        assert plan.task
        assert isinstance(plan.steps, list)
        assert len(plan.steps) >= 1
        assert isinstance(plan.risk_level, int)
        assert isinstance(plan.required_capabilities, list)
        assert plan.protocol_version == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_step_has_required_fields(self, planner):
        """Golden: each ActionStep has all required fields."""
        plan = await planner.create_plan("Search for information online")
        for step in plan.steps:
            assert step.step_id
            assert step.action
            assert step.skill
            assert isinstance(step.params, dict)
            assert isinstance(step.required_capabilities, list)
            assert 1 <= step.risk_level <= 5


@pytest.mark.phase4
@pytest.mark.unit
class TestCriticAgentGolden:
    """Golden master tests for CriticAgent evaluation structure."""

    @pytest.fixture
    def mock_llm(self):
        provider = AsyncMock()
        provider.generate = AsyncMock(return_value={
            "content": '{"success": true, "score": 0.9, "feedback": "Good result", "recommendations": [], "knowledge_gaps": [], "should_create_skill": false, "suggested_skill_task": ""}',
            "model": "gpt-4o-mini",
            "usage": {},
        })
        return provider

    @pytest.fixture
    def critic(self, mock_llm):
        from synapse.agents.critic import CriticAgent
        return CriticAgent(llm_provider=mock_llm)

    @pytest.mark.asyncio
    async def test_evaluation_has_required_fields(self, critic):
        """Golden: evaluation result has required structure."""
        result = await critic.evaluate({"status": "completed", "result": "done"}, task="test task")
        assert "success" in result
        assert "score" in result
        assert "feedback" in result
        assert "recommendations" in result
        assert "knowledge_gaps" in result
        assert "should_create_skill" in result
        assert result.get("protocol_version") == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_score_is_normalized(self, critic):
        """Golden: score is between 0 and 1."""
        result = await critic.evaluate({"status": "error", "error": "fail"}, task="test")
        assert 0.0 <= result["score"] <= 1.0
