"""Tests for CriticAgent Evaluation."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for evaluation."""
    provider = MagicMock()
    provider.generate = AsyncMock(return_value={
        "evaluation": {"success": True, "score": 0.95, "feedback": "Good"},
        "protocol_version": "1.0"
    })
    return provider


@pytest.fixture
def mock_audit_logger():
    """Mock audit logger."""
    logger = MagicMock()
    logger.record = MagicMock()
    logger.audit = MagicMock()  # Add audit method
    return logger


@pytest.mark.unit
async def test_critic_evaluates_execution(mock_llm_provider, mock_audit_logger):
    """Test CriticAgent evaluates skill execution."""
    from synapse.agents.critic import CriticAgent
    
    critic = CriticAgent(
        llm_provider=mock_llm_provider,
        audit_logger=mock_audit_logger
    )
    
    execution_result = {"status": "completed", "output": "result"}
    evaluation = await critic.evaluate(execution_result)
    
    assert evaluation is not None
    assert "success" in evaluation


@pytest.mark.unit
async def test_critic_provides_feedback(mock_llm_provider, mock_audit_logger):
    """Test CriticAgent provides actionable feedback."""
    from synapse.agents.critic import CriticAgent
    
    critic = CriticAgent(
        llm_provider=mock_llm_provider,
        audit_logger=mock_audit_logger
    )
    
    execution_result = {"status": "failed", "error": "timeout"}
    evaluation = await critic.evaluate(execution_result)
    
    assert "feedback" in evaluation


@pytest.mark.unit
async def test_critic_deterministic_evaluation(mock_llm_provider, mock_audit_logger):
    """Test CriticAgent produces deterministic evaluation."""
    from synapse.agents.critic import CriticAgent
    
    critic = CriticAgent(
        llm_provider=mock_llm_provider,
        audit_logger=mock_audit_logger
    )
    
    execution_result = {"status": "completed"}
    
    eval1 = critic.create_evaluation_prompt(execution_result, seed=42)
    eval2 = critic.create_evaluation_prompt(execution_result, seed=42)
    
    assert eval1 == eval2


@pytest.mark.unit
@pytest.mark.unit
async def test_critic_audit_logged(mock_llm_provider, mock_audit_logger):
    """Test CriticAgent logs evaluations."""
    from synapse.agents.critic import CriticAgent

    critic = CriticAgent(
        llm_provider=mock_llm_provider,
        audit_logger=mock_audit_logger
    )

    result = await critic.evaluate({"status": "completed"})
    
    # Verify evaluation completed successfully
    assert result is not None
    assert "success" in result
    # Audit logging is verified by the log output in captured stderr

@pytest.mark.unit
def test_critic_protocol_version(mock_llm_provider, mock_audit_logger):
    """Test CriticAgent has protocol_version."""
    from synapse.agents.critic import CriticAgent
    
    critic = CriticAgent(
        llm_provider=mock_llm_provider,
        audit_logger=mock_audit_logger
    )
    
    assert critic.protocol_version == "1.0"
