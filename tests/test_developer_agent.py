"""Tests for DeveloperAgent Code Generation."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for code generation."""
    provider = MagicMock()
    provider.generate = AsyncMock(return_value={
        "code": "class NewSkill:\n    def execute(self): pass",
        "protocol_version": "1.0"
    })
    provider.is_active = True
    provider.priority = 1
    return provider


@pytest.fixture
def mock_skill_registry():
    """Mock skill registry."""
    registry = MagicMock()
    registry.register = AsyncMock(return_value=True)
    registry.validate = MagicMock(return_value={"valid": True})
    return registry


@pytest.fixture
def mock_policy_engine():
    """Mock policy engine."""
    engine = MagicMock()
    engine.check_permission = AsyncMock(return_value=True)
    engine.check = AsyncMock(return_value={"allowed": True, "reason": "OK"})
    return engine


@pytest.fixture
def mock_audit_logger():
    """Mock audit logger."""
    from unittest.mock import MagicMock
    logger = MagicMock()
    logger.audit = MagicMock()
    return logger

@pytest.mark.unit
@pytest.mark.asyncio
async def test_developer_generates_skill_code(mock_llm_provider, mock_skill_registry, mock_policy_engine):
    """Test DeveloperAgent generates valid skill code."""
    from synapse.agents.developer import DeveloperAgent
    
    developer = DeveloperAgent(
        llm_provider=mock_llm_provider,
        skill_registry=mock_skill_registry,
        policy_engine=mock_policy_engine
    )
    
    result = await developer.generate_skill("Create a file reader skill")
    
    assert result is not None
    assert "code" in result
    assert "class" in result["code"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_developer_skill_has_protocol_version(mock_llm_provider, mock_skill_registry, mock_policy_engine):
    """Test generated skill has protocol_version."""
    from synapse.agents.developer import DeveloperAgent
    
    developer = DeveloperAgent(
        llm_provider=mock_llm_provider,
        skill_registry=mock_skill_registry,
        policy_engine=mock_policy_engine
    )
    
    result = await developer.generate_skill("Create a skill")
    
    assert "protocol_version" in result
    assert result["protocol_version"] == "1.0"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_developer_registers_skill(mock_llm_provider, mock_skill_registry, mock_policy_engine):
    """Test DeveloperAgent registers generated skill."""
    from synapse.agents.developer import DeveloperAgent
    
    developer = DeveloperAgent(
        llm_provider=mock_llm_provider,
        skill_registry=mock_skill_registry,
        policy_engine=mock_policy_engine
    )
    
    await developer.create_and_register("Create a skill")
    
    mock_skill_registry.register.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_developer_deterministic_output(mock_llm_provider, mock_skill_registry, mock_policy_engine):
    """Test DeveloperAgent produces deterministic output."""
    from synapse.agents.developer import DeveloperAgent
    
    developer = DeveloperAgent(
        llm_provider=mock_llm_provider,
        skill_registry=mock_skill_registry,
        policy_engine=mock_policy_engine
    )
    
    result1 = developer.create_prompt("test task", seed=42)
    result2 = developer.create_prompt("test task", seed=42)
    
    assert result1 == result2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_developer_policy_check(mock_llm_provider, mock_skill_registry, mock_policy_engine):
    """Test DeveloperAgent checks policy before registration."""
    from synapse.agents.developer import DeveloperAgent
    
    developer = DeveloperAgent(
        llm_provider=mock_llm_provider,
        skill_registry=mock_skill_registry,
        policy_engine=mock_policy_engine
    )
    
    await developer.create_and_register("Create a skill")
    
    mock_policy_engine.check.assert_called()
