"""Unit tests for Planner Agent. Phase 3 — LangGraph patterns.

TDD per LANGGRAPH_INTEGRATION.md §1 + AGENT_ZERO_INTEGRATION.md §6.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase3
@pytest.mark.unit
class TestActionStep:
    def test_action_step_to_dict(self):
        from synapse.agents.planner import ActionStep
        step = ActionStep(step_id="s1", action="Read file", skill="read_file",
                          params={"path": "test.txt"}, required_capabilities=["fs:read"], risk_level=1)
        d = step.to_dict()
        assert d["step_id"] == "s1"
        assert d["skill"] == "read_file"
        assert d["protocol_version"] == PROTOCOL_VERSION

    def test_risk_level_bounds(self):
        from synapse.agents.planner import ActionStep
        step = ActionStep(step_id="s1", action="test", skill="test", risk_level=3)
        assert 1 <= step.risk_level <= 5


@pytest.mark.phase3
@pytest.mark.unit
class TestActionPlan:
    def test_action_plan_to_dict(self):
        from synapse.agents.planner import ActionPlan, ActionStep
        plan = ActionPlan(
            plan_id="p1",
            task="Do something",
            steps=[ActionStep(step_id="s1", action="act", skill="sk", risk_level=1)],
        )
        d = plan.to_dict()
        assert d["plan_id"] == "p1"
        assert len(d["steps"]) == 1
        assert d["protocol_version"] == PROTOCOL_VERSION


@pytest.mark.phase3
@pytest.mark.unit
class TestPlannerAgentHeuristic:
    @pytest.fixture
    def planner(self):
        from synapse.agents.planner import PlannerAgent
        return PlannerAgent()

    @pytest.mark.asyncio
    async def test_plan_created_successfully(self, planner):
        plan = await planner.create_plan("Read a file and return its content")
        assert plan.plan_id
        assert len(plan.steps) >= 1
        assert plan.protocol_version == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_plan_for_http_task_has_net_cap(self, planner):
        plan = await planner.create_plan("Fetch data from a web API endpoint")
        all_caps = [c for s in plan.steps for c in s.required_capabilities]
        assert any("net:http" in c for c in all_caps)

    @pytest.mark.asyncio
    async def test_plan_for_file_task_has_fs_cap(self, planner):
        plan = await planner.create_plan("Read the configuration file")
        all_caps = [c for s in plan.steps for c in s.required_capabilities]
        assert any("fs:read" in c for c in all_caps)

    @pytest.mark.asyncio
    async def test_plan_risk_level_is_max_of_steps(self, planner):
        plan = await planner.create_plan("execute a command and read file")
        step_risks = [s.risk_level for s in plan.steps]
        assert plan.risk_level == max(step_risks)

    @pytest.mark.asyncio
    async def test_plan_has_at_least_one_step(self, planner):
        plan = await planner.create_plan("do something unspecific")
        assert len(plan.steps) >= 1


@pytest.mark.phase3
@pytest.mark.unit
class TestPlannerAgentWithLLM:
    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value={
            "content": '{"steps": [{"step_id": "s1", "action": "Search web", "skill": "web_search", "params": {"query": "test"}, "required_capabilities": ["net:http"], "risk_level": 2}], "risk_level": 2, "reasoning": "web search"}',
            "usage": {}
        })
        return llm

    @pytest.fixture
    def planner(self, mock_llm):
        from synapse.agents.planner import PlannerAgent
        return PlannerAgent(llm_provider=mock_llm)

    @pytest.mark.asyncio
    async def test_planner_uses_llm_output(self, planner):
        plan = await planner.create_plan("Search for information about AI")
        assert any(s.skill == "web_search" for s in plan.steps)
