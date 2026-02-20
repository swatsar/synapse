"""Tests for critical modules with low coverage."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

PROTOCOL_VERSION: str = "1.0"


# Test synapse/llm/failure_strategy.py
class TestLLMFailureStrategy:
    """Tests for LLM failure strategy."""
    
    def test_import_failure_strategy(self):
        """Test importing failure strategy module."""
        from synapse.llm.failure_strategy import LLMFailureStrategy, ModelConfig, LLMPriority
        assert LLMFailureStrategy is not None
        assert ModelConfig is not None
        assert LLMPriority is not None
    
    def test_failure_strategy_init(self):
        """Test failure strategy initialization."""
        from synapse.llm.failure_strategy import LLMFailureStrategy, ModelConfig, LLMPriority
        models = [
            ModelConfig(provider="openai", model="gpt-4", priority=LLMPriority.PRIMARY),
            ModelConfig(provider="anthropic", model="claude-3", priority=LLMPriority.FALLBACK_1)
        ]
        strategy = LLMFailureStrategy(models=models)
        assert strategy is not None
    
    def test_failure_strategy_get_model(self):
        """Test getting available model."""
        from synapse.llm.failure_strategy import LLMFailureStrategy, ModelConfig, LLMPriority
        models = [
            ModelConfig(provider="openai", model="gpt-4", priority=LLMPriority.PRIMARY),
        ]
        strategy = LLMFailureStrategy(models=models)
        model = strategy.get_available_model()
        assert model is not None
    
    def test_model_config_protocol_version(self):
        """Test ModelConfig has protocol_version."""
        from synapse.llm.failure_strategy import ModelConfig, LLMPriority
        config = ModelConfig(provider="openai", model="gpt-4", priority=LLMPriority.PRIMARY)
        assert config.protocol_version == "1.0"
    
    def test_llm_priority_values(self):
        """Test LLMPriority enum values."""
        from synapse.llm.failure_strategy import LLMPriority
        assert LLMPriority.PRIMARY == 1
        assert LLMPriority.FALLBACK_1 == 2
        assert LLMPriority.FALLBACK_2 == 3
        assert LLMPriority.SAFE == 4


# Test synapse/security/safety_layer.py
class TestSafetyLayer:
    """Tests for safety layer."""
    
    def test_import_safety_layer(self):
        """Test importing safety layer module."""
        from synapse.security.safety_layer import SafetyLayer
        assert SafetyLayer is not None
    
    def test_safety_layer_init(self):
        """Test safety layer initialization."""
        from synapse.security.safety_layer import SafetyLayer
        layer = SafetyLayer()
        assert layer is not None


# Test synapse/agents/planner.py
class TestPlannerAgent:
    """Tests for planner agent."""
    
    def test_import_planner(self):
        """Test importing planner module."""
        from synapse.agents.planner import PlannerAgent
        assert PlannerAgent is not None
    
    def test_planner_init(self):
        """Test planner initialization."""
        from synapse.agents.planner import PlannerAgent
        planner = PlannerAgent()
        assert planner is not None


# Test synapse/agents/guardian.py
class TestGuardianAgent:
    """Tests for guardian agent."""
    
    def test_import_guardian(self):
        """Test importing guardian module."""
        from synapse.agents.guardian import GuardianAgent
        assert GuardianAgent is not None
    
    def test_guardian_init(self):
        """Test guardian initialization."""
        from synapse.agents.guardian import GuardianAgent
        guardian = GuardianAgent()
        assert guardian is not None


# Test synapse/agents/forecaster.py
class TestForecasterAgent:
    """Tests for forecaster agent."""
    
    def test_import_forecaster(self):
        """Test importing forecaster module."""
        from synapse.agents.forecaster import ForecasterAgent
        assert ForecasterAgent is not None
    
    def test_forecaster_init(self):
        """Test forecaster initialization."""
        from synapse.agents.forecaster import ForecasterAgent
        forecaster = ForecasterAgent()
        assert forecaster is not None


# Test synapse/core/environment.py
class TestEnvironmentAdapter:
    """Tests for environment module."""
    
    def test_import_environment_types(self):
        """Test importing environment types."""
        from synapse.core.environment import OSType, EnvironmentAdapter
        assert OSType is not None
        assert EnvironmentAdapter is not None
    
    def test_get_environment_adapter(self):
        """Test getting environment adapter."""
        from synapse.core.environment import get_environment_adapter
        adapter = get_environment_adapter()
        assert adapter is not None


# Test synapse/agents/supervisor/agent.py
class TestSupervisorAgent:
    """Tests for supervisor agent."""
    
    def test_import_supervisor(self):
        """Test importing supervisor module."""
        from synapse.agents.supervisor.agent import SupervisorAgent
        assert SupervisorAgent is not None
    
    def test_supervisor_init(self):
        """Test supervisor initialization with required args."""
        from synapse.agents.supervisor.agent import SupervisorAgent
        orchestrator = MagicMock()
        policy = MagicMock()
        learner = MagicMock()
        registry = MagicMock()
        
        supervisor = SupervisorAgent(
            orchestrator=orchestrator,
            policy=policy,
            learner=learner,
            registry=registry
        )
        assert supervisor is not None
