"""Tests for PolicyEngine with full coverage."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestPolicyEngineFull:
    """Test PolicyEngine with full coverage."""
    
    @pytest.fixture
    def policy_engine(self):
        """Create a PolicyEngine."""
        from synapse.policy.engine import PolicyEngine
        from synapse.security.capability_manager import CapabilityManager
        
        caps = CapabilityManager()
        caps.grant_capability("test:cap")
        
        return PolicyEngine(capability_manager=caps)
    
    @pytest.fixture
    def skill_manifest(self):
        """Create a SkillManifest."""
        from synapse.core.models import SkillManifest
        
        return SkillManifest(
            name="test_skill",
            version="1.0.0",
            description="Test skill",
            author="test",
            inputs={},
            outputs={},
            required_capabilities=["test:cap"],
            risk_level=1
        )
    
    def test_policy_engine_creation(self, policy_engine):
        """Test PolicyEngine creation."""
        assert policy_engine is not None
        assert policy_engine.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_evaluate_low_risk(self, policy_engine, skill_manifest):
        """Test evaluate with low risk skill."""
        result = await policy_engine.evaluate(skill_manifest)
        
        assert result == True
    
    @pytest.mark.asyncio
    async def test_add_rule(self, policy_engine, skill_manifest):
        """Test add_rule."""
        # Add a custom rule that always passes
        policy_engine.add_rule(lambda manifest: True)
        
        result = await policy_engine.evaluate(skill_manifest)
        assert result == True
    
    @pytest.mark.asyncio
    async def test_add_rule_rejects(self, policy_engine, skill_manifest):
        """Test add_rule that rejects."""
        # Add a custom rule that always rejects
        policy_engine.add_rule(lambda manifest: False)
        
        result = await policy_engine.evaluate(skill_manifest)
        assert result == False
    
    @pytest.mark.asyncio
    async def test_add_multiple_rules(self, policy_engine, skill_manifest):
        """Test add_rule with multiple rules."""
        # Add multiple custom rules
        policy_engine.add_rule(lambda manifest: True)
        policy_engine.add_rule(lambda manifest: True)
        policy_engine.add_rule(lambda manifest: True)
        
        result = await policy_engine.evaluate(skill_manifest)
        assert result == True
    
    @pytest.mark.asyncio
    async def test_add_rule_then_reject(self, policy_engine, skill_manifest):
        """Test add_rule with pass then reject."""
        # Add a pass rule then a reject rule
        policy_engine.add_rule(lambda manifest: True)
        policy_engine.add_rule(lambda manifest: False)
        
        result = await policy_engine.evaluate(skill_manifest)
        assert result == False
    
    def test_default_rules_registered(self, policy_engine):
        """Test that default rules are registered."""
        assert len(policy_engine._rules) > 0
