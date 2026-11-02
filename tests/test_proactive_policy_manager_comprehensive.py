"""Comprehensive tests for proactive policy manager."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestProactivePolicyManagerComprehensive:
    """Test proactive policy manager comprehensively."""
    
    @pytest.fixture
    def policy_manager(self):
        """Create a proactive policy manager for testing."""
        from synapse.policy.proactive.manager import ProactivePolicyManager
        
        return ProactivePolicyManager()
    
    def test_policy_manager_creation(self, policy_manager):
        """Test policy manager creation."""
        assert policy_manager is not None
    
    def test_protocol_version(self, policy_manager):
        """Test protocol version."""
        assert policy_manager.PROTOCOL_VERSION == "1.0"
    
    @pytest.mark.asyncio
    async def test_create_rule(self, policy_manager):
        """Test creating a rule."""
        from synapse.policy.proactive.manager import ProactiveRule
        
        rule = ProactiveRule(
            name="test_rule",
            condition={"type": "test"},
            action={"type": "alert"},
            risk_level=1
        )
        
        result = await policy_manager.create_rule(rule)
        
        assert result.success == True
        assert result.rule_id is not None
    
    @pytest.mark.asyncio
    async def test_get_rule(self, policy_manager):
        """Test getting a rule."""
        from synapse.policy.proactive.manager import ProactiveRule
        
        rule = ProactiveRule(
            name="test_rule",
            condition={"type": "test"},
            action={"type": "alert"},
            risk_level=1
        )
        
        result = await policy_manager.create_rule(rule)
        
        retrieved = policy_manager._rules.get(result.rule_id)
        
        assert retrieved is not None
        assert retrieved.name == "test_rule"
    
    def test_generate_rule_id(self, policy_manager):
        """Test generating rule ID."""
        from synapse.policy.proactive.manager import ProactiveRule
        
        rule = ProactiveRule(
            name="test_rule",
            condition={"type": "test"},
            action={"type": "alert"},
            risk_level=1
        )
        
        rule_id = policy_manager._generate_rule_id(rule)
        
        assert rule_id is not None
        assert len(rule_id) == 36  # UUID format
