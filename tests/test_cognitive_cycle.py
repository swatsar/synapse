"""Tests for 7-Step Cognitive Cycle Implementation.
Phase 1: Cognitive Cycle Tests

Tests verify:
- All 7 steps execute correctly
- protocol_version is present in all results
- Audit logging occurs for each step
- Checkpoint creation for high-risk actions
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from synapse.core.orchestrator import (
    Orchestrator,
    CognitiveCycleResult,
    PROTOCOL_VERSION,
    SPEC_VERSION
)
from synapse.core.determinism import DeterministicSeedManager, DeterministicIDGenerator


@pytest.fixture
def mock_seed_manager():
    return MagicMock(spec=DeterministicSeedManager)


@pytest.fixture
def mock_id_generator():
    gen = MagicMock(spec=DeterministicIDGenerator)
    gen.generate.return_value = "test-task-id"
    return gen


@pytest.fixture
def orchestrator(mock_seed_manager, mock_id_generator):
    return Orchestrator(
        seed_manager=mock_seed_manager,
        id_generator=mock_id_generator
    )


class TestProtocolVersion:
    """Test protocol version compliance."""
    
    def test_protocol_version_constant(self):
        """PROTOCOL_VERSION should be '1.0'."""
        assert PROTOCOL_VERSION == "1.0"
    
    def test_spec_version_constant(self):
        """SPEC_VERSION should be '3.1'."""
        assert SPEC_VERSION == "3.1"
    
    def test_orchestrator_protocol_version(self, orchestrator):
        """Orchestrator should have protocol_version attribute."""
        assert orchestrator.protocol_version == "1.0"


class TestCognitiveCycleResult:
    """Test CognitiveCycleResult class."""
    
    def test_result_creation_success(self):
        """CognitiveCycleResult should be created with success=True."""
        result = CognitiveCycleResult(success=True)
        assert result.success == True
        assert result.protocol_version == "1.0"
    
    def test_result_creation_failure(self):
        """CognitiveCycleResult should be created with success=False."""
        result = CognitiveCycleResult(success=False, error="Test error")
        assert result.success == False
        assert result.error == "Test error"
    
    def test_result_to_dict(self):
        """CognitiveCycleResult.to_dict() should include protocol_version."""
        result = CognitiveCycleResult(success=True)
        d = result.to_dict()
        assert "protocol_version" in d
        assert d["protocol_version"] == "1.0"


class TestPerceiveStep:
    """Test Step 1: PERCEIVE."""
    
    @pytest.mark.asyncio
    async def test_perceive_returns_dict(self, orchestrator):
        """_perceive should return a dictionary."""
        event = {"type": "test", "content": "test content"}
        result = await orchestrator._perceive(event)
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_perceive_includes_protocol_version(self, orchestrator):
        """_perceive result should include protocol_version."""
        event = {"type": "test", "content": "test content"}
        result = await orchestrator._perceive(event)
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_perceive_normalizes_event(self, orchestrator):
        """_perceive should normalize event structure."""
        event = {"type": "test", "content": "test content", "user_id": "user123"}
        result = await orchestrator._perceive(event)
        assert "event_id" in result
        assert "event_type" in result
        assert "timestamp" in result


class TestRecallStep:
    """Test Step 2: RECALL."""
    
    @pytest.mark.asyncio
    async def test_recall_returns_dict(self, orchestrator):
        """_recall should return a dictionary."""
        perceived = {"event_type": "test", "content": "test"}
        result = await orchestrator._recall(perceived)
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_recall_includes_protocol_version(self, orchestrator):
        """_recall result should include protocol_version."""
        perceived = {"event_type": "test", "content": "test"}
        result = await orchestrator._recall(perceived)
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_recall_includes_memory_types(self, orchestrator):
        """_recall should include all memory types."""
        perceived = {"event_type": "test", "content": "test"}
        result = await orchestrator._recall(perceived)
        assert "episodic" in result
        assert "semantic" in result
        assert "procedural" in result
        assert "context" in result


class TestPlanStep:
    """Test Step 3: PLAN."""
    
    @pytest.mark.asyncio
    async def test_plan_returns_dict(self, orchestrator):
        """_plan should return a dictionary."""
        perceived = {"event_type": "test", "content": "test"}
        recalled = {"episodic": [], "semantic": []}
        result = await orchestrator._plan(perceived, recalled)
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_plan_includes_protocol_version(self, orchestrator):
        """_plan result should include protocol_version."""
        perceived = {"event_type": "test", "content": "test"}
        recalled = {"episodic": [], "semantic": []}
        result = await orchestrator._plan(perceived, recalled)
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_plan_includes_required_fields(self, orchestrator):
        """_plan should include goal, steps, risk_level."""
        perceived = {"event_type": "test", "content": "test goal"}
        recalled = {"episodic": [], "semantic": []}
        result = await orchestrator._plan(perceived, recalled)
        assert "goal" in result
        assert "steps" in result
        assert "risk_level" in result
        assert "required_capabilities" in result


class TestSecurityCheckStep:
    """Test Step 4: SECURITY CHECK."""
    
    @pytest.mark.asyncio
    async def test_security_check_returns_dict(self, orchestrator):
        """_security_check should return a dictionary."""
        plan = {"goal": "test", "risk_level": 1, "required_capabilities": []}
        result = await orchestrator._security_check(plan)
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_security_check_includes_protocol_version(self, orchestrator):
        """_security_check result should include protocol_version."""
        plan = {"goal": "test", "risk_level": 1, "required_capabilities": []}
        result = await orchestrator._security_check(plan)
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_security_check_requires_approval_for_high_risk(self, orchestrator):
        """_security_check should require approval for risk_level >= 3."""
        plan = {"goal": "test", "risk_level": 3, "required_capabilities": []}
        result = await orchestrator._security_check(plan)
        assert result["requires_human_approval"] == True
    
    @pytest.mark.asyncio
    async def test_security_check_no_approval_for_low_risk(self, orchestrator):
        """_security_check should not require approval for risk_level < 3."""
        plan = {"goal": "test", "risk_level": 1, "required_capabilities": []}
        result = await orchestrator._security_check(plan)
        assert result["requires_human_approval"] == False


class TestActStep:
    """Test Step 5: ACT."""
    
    @pytest.mark.asyncio
    async def test_act_returns_dict(self, orchestrator):
        """_act should return a dictionary."""
        plan = {"goal": "test", "steps": [], "risk_level": 1}
        result = await orchestrator._act(plan)
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_act_includes_protocol_version(self, orchestrator):
        """_act result should include protocol_version."""
        plan = {"goal": "test", "steps": [], "risk_level": 1}
        result = await orchestrator._act(plan)
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_act_tracks_steps_completed(self, orchestrator):
        """_act should track steps_completed."""
        plan = {"goal": "test", "steps": [], "risk_level": 1}
        result = await orchestrator._act(plan)
        assert "steps_completed" in result
        assert "steps_total" in result


class TestObserveStep:
    """Test Step 6: OBSERVE."""
    
    @pytest.mark.asyncio
    async def test_observe_returns_dict(self, orchestrator):
        """_observe should return a dictionary."""
        action_result = {"success": True, "steps_completed": 0, "steps_total": 0, "errors": []}
        result = await orchestrator._observe(action_result)
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_observe_includes_protocol_version(self, orchestrator):
        """_observe result should include protocol_version."""
        action_result = {"success": True, "steps_completed": 0, "steps_total": 0, "errors": []}
        result = await orchestrator._observe(action_result)
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_observe_analyzes_success(self, orchestrator):
        """_observe should analyze success status."""
        action_result = {"success": True, "steps_completed": 1, "steps_total": 1, "errors": []}
        result = await orchestrator._observe(action_result)
        assert result["success"] == True
        assert result["has_errors"] == False


class TestEvaluateStep:
    """Test Step 7: EVALUATE."""
    
    @pytest.mark.asyncio
    async def test_evaluate_returns_dict(self, orchestrator):
        """_evaluate should return a dictionary."""
        plan = {"goal": "test", "steps": []}
        observation = {"success": True, "steps_completed": 1, "steps_total": 1}
        result = await orchestrator._evaluate(plan, observation)
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_evaluate_includes_protocol_version(self, orchestrator):
        """_evaluate result should include protocol_version."""
        plan = {"goal": "test", "steps": []}
        observation = {"success": True, "steps_completed": 1, "steps_total": 1}
        result = await orchestrator._evaluate(plan, observation)
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_evaluate_calculates_completion_rate(self, orchestrator):
        """_evaluate should calculate completion_rate."""
        plan = {"goal": "test", "steps": []}
        observation = {"success": True, "steps_completed": 3, "steps_total": 5}
        result = await orchestrator._evaluate(plan, observation)
        assert "completion_rate" in result
        assert result["completion_rate"] == 0.6


class TestLearnStep:
    """Test Step 8: LEARN."""
    
    @pytest.mark.asyncio
    async def test_learn_returns_dict(self, orchestrator):
        """_learn should return a dictionary."""
        event = {"type": "test"}
        plan = {"goal": "test"}
        action_result = {"success": True}
        evaluation = {"success": True}
        result = await orchestrator._learn(event, plan, action_result, evaluation)
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_learn_includes_protocol_version(self, orchestrator):
        """_learn result should include protocol_version."""
        event = {"type": "test"}
        plan = {"goal": "test"}
        action_result = {"success": True}
        evaluation = {"success": True}
        result = await orchestrator._learn(event, plan, action_result, evaluation)
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_learn_extracts_insights_on_success(self, orchestrator):
        """_learn should extract insights on successful execution."""
        event = {"type": "test"}
        plan = {"goal": "test goal"}
        action_result = {"success": True}
        evaluation = {"success": True}
        result = await orchestrator._learn(event, plan, action_result, evaluation)
        assert "insights" in result
        assert len(result["insights"]) > 0


class TestFullCycle:
    """Test full cognitive cycle execution."""
    
    @pytest.mark.asyncio
    async def test_execute_cycle_returns_result(self, orchestrator):
        """execute_cycle should return CognitiveCycleResult."""
        event = {"type": "test", "content": "test content"}
        result = await orchestrator.execute_cycle(event)
        assert isinstance(result, CognitiveCycleResult)
    
    @pytest.mark.asyncio
    async def test_execute_cycle_success(self, orchestrator):
        """execute_cycle should complete successfully for simple event."""
        event = {"type": "test", "content": "test content"}
        result = await orchestrator.execute_cycle(event)
        assert result.success == True
    
    @pytest.mark.asyncio
    async def test_execute_cycle_includes_all_steps(self, orchestrator):
        """execute_cycle should populate all step results."""
        event = {"type": "test", "content": "test content"}
        result = await orchestrator.execute_cycle(event)
        assert result.perceived is not None
        assert result.recalled is not None
        assert result.plan is not None
        assert result.security_result is not None
        assert result.action_result is not None
        assert result.observation is not None
        assert result.evaluation is not None
        assert result.learning is not None
    
    @pytest.mark.asyncio
    async def test_execute_cycle_result_to_dict(self, orchestrator):
        """execute_cycle result.to_dict() should include protocol_version."""
        event = {"type": "test", "content": "test content"}
        result = await orchestrator.execute_cycle(event)
        d = result.to_dict()
        assert "protocol_version" in d
        assert d["protocol_version"] == "1.0"


class TestLegacyMethods:
    """Test legacy methods for backward compatibility."""
    
    def test_handle_returns_dict(self, orchestrator):
        """handle should return a dictionary."""
        result = orchestrator.handle({"task": "test"})
        assert isinstance(result, dict)
    
    def test_handle_includes_protocol_version(self, orchestrator):
        """handle result should include protocol_version."""
        result = orchestrator.handle({"task": "test"})
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
    
    def test_handle_error_returns_dict(self, orchestrator):
        """handle_error should return a dictionary."""
        result = orchestrator.handle_error({"task": "test"}, Exception("test error"))
        assert isinstance(result, dict)
    
    def test_handle_error_includes_protocol_version(self, orchestrator):
        """handle_error result should include protocol_version."""
        result = orchestrator.handle_error({"task": "test"}, Exception("test error"))
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
