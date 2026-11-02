"""Tests for ProactivePolicyManager with full coverage."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestProactivePolicyManagerFull:
    """Test ProactivePolicyManager with full coverage."""
    
    @pytest.fixture
    def policy_manager(self):
        """Create a ProactivePolicyManager."""
        from synapse.policy.proactive.manager import ProactivePolicyManager
        from synapse.security.capability_manager import CapabilityManager
        
        caps = CapabilityManager()
        caps.grant_capability("proactive:optimize")
        caps.grant_capability("proactive:scale")
        caps.grant_capability("proactive:migrate")
        
        return ProactivePolicyManager(capability_manager=caps)
    
    @pytest.fixture
    def policy_manager_with_approval(self):
        """Create a ProactivePolicyManager with human approval."""
        from synapse.policy.proactive.manager import ProactivePolicyManager
        from synapse.security.capability_manager import CapabilityManager
        
        caps = CapabilityManager()
        caps.grant_capability("proactive:optimize")
        
        human_approval = AsyncMock()
        human_approval.request_approval = AsyncMock(return_value=MagicMock(approved=True))
        human_approval.pending_approvals = {}
        human_approval.denied_approvals = set()
        
        return ProactivePolicyManager(
            capability_manager=caps,
            human_approval=human_approval
        )
    
    def test_evaluate_condition_greater_than_or_equal(self, policy_manager):
        """Test _evaluate_condition with >= operator."""
        # Test >= operator - should pass
        assert policy_manager._evaluate_condition({"cpu_usage": ">=80"}, {"cpu_usage": 90}) == True
        assert policy_manager._evaluate_condition({"cpu_usage": ">=80"}, {"cpu_usage": 80}) == True
        assert policy_manager._evaluate_condition({"cpu_usage": ">=80"}, {"cpu_usage": 70}) == False
    
    def test_evaluate_condition_less_than_or_equal(self, policy_manager):
        """Test _evaluate_condition with <= operator."""
        # Test <= operator
        assert policy_manager._evaluate_condition({"cpu_usage": "<=80"}, {"cpu_usage": 70}) == True
        assert policy_manager._evaluate_condition({"cpu_usage": "<=80"}, {"cpu_usage": 80}) == True
        assert policy_manager._evaluate_condition({"cpu_usage": "<=80"}, {"cpu_usage": 90}) == False
    
    def test_evaluate_condition_greater_than(self, policy_manager):
        """Test _evaluate_condition with > operator."""
        # Test > operator
        assert policy_manager._evaluate_condition({"cpu_usage": ">80"}, {"cpu_usage": 90}) == True
        assert policy_manager._evaluate_condition({"cpu_usage": ">80"}, {"cpu_usage": 80}) == False
        assert policy_manager._evaluate_condition({"cpu_usage": ">80"}, {"cpu_usage": 70}) == False
    
    def test_evaluate_condition_less_than(self, policy_manager):
        """Test _evaluate_condition with < operator."""
        # Test < operator
        assert policy_manager._evaluate_condition({"cpu_usage": "<80"}, {"cpu_usage": 70}) == True
        assert policy_manager._evaluate_condition({"cpu_usage": "<80"}, {"cpu_usage": 80}) == False
        assert policy_manager._evaluate_condition({"cpu_usage": "<80"}, {"cpu_usage": 90}) == False
    
    def test_evaluate_condition_direct_comparison(self, policy_manager):
        """Test _evaluate_condition with direct comparison."""
        # Test direct comparison
        assert policy_manager._evaluate_condition({"status": "active"}, {"status": "active"}) == True
        assert policy_manager._evaluate_condition({"status": "active"}, {"status": "inactive"}) == False
    
    def test_evaluate_condition_missing_metric(self, policy_manager):
        """Test _evaluate_condition with missing metric."""
        # Missing metric defaults to 0
        assert policy_manager._evaluate_condition({"cpu_usage": ">50"}, {}) == False
        assert policy_manager._evaluate_condition({"cpu_usage": "<50"}, {}) == True
    
    @pytest.mark.asyncio
    async def test_evaluate_and_act_with_metrics(self, policy_manager):
        """Test evaluate_and_act with metrics."""
        result = await policy_manager.evaluate_and_act(
            metrics={"cpu_usage": 95}
        )
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_create_rule(self, policy_manager):
        """Test create_rule method."""
        from synapse.policy.proactive.manager import ProactiveRule
        
        rule = ProactiveRule(
            name="high_cpu",
            condition={"cpu_usage": ">80"},
            action="optimize",
            risk_level=2
        )
        
        result = await policy_manager.create_rule(rule)
        assert result is not None
        assert result.success == True
    
    @pytest.mark.asyncio
    async def test_predict_violation(self, policy_manager):
        """Test predict_violation method."""
        result = await policy_manager.predict_violation(
            action_context={"cpu_usage": 95}
        )
        
        assert result is not None
        assert "violation_risk" in result
    
    @pytest.mark.asyncio
    async def test_evaluate_action(self, policy_manager):
        """Test evaluate_action method."""
        result = await policy_manager.evaluate_action(
            action_context={"action_type": "optimize", "target": "node_1"}
        )
        
        assert result is not None
