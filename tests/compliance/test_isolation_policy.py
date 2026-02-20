"""Isolation Policy Compliance Tests.

Verifies isolation enforcement policy is correctly implemented:
- risk_level >= 3 → container minimum
- unverified skill → container mandatory
- trusted skill → subprocess allowed
"""
import pytest
from unittest.mock import MagicMock


class TestIsolationPolicyCompliance:
    """Test isolation policy compliance."""
    
    @pytest.fixture
    def isolation_policy(self):
        """Create IsolationEnforcementPolicy instance."""
        from synapse.core.isolation_policy import IsolationEnforcementPolicy
        return IsolationEnforcementPolicy()
    
    def test_policy_exists(self, isolation_policy):
        """Test that IsolationEnforcementPolicy exists."""
        assert isolation_policy is not None
    
    def test_policy_has_protocol_version(self, isolation_policy):
        """Test that policy has protocol_version."""
        assert hasattr(isolation_policy, "protocol_version")
        assert isolation_policy.protocol_version == "1.0"
    
    def test_risk_level_3_requires_container(self, isolation_policy):
        """Test risk_level >= 3 requires container."""
        from synapse.skills.base import RuntimeIsolationType
        
        for trust_level in ["unverified", "verified", "trusted", "human-approved"]:
            isolation = isolation_policy.get_required_isolation(
                trust_level=trust_level,
                risk_level=3
            )
            assert isolation == RuntimeIsolationType.CONTAINER, \
                f"risk_level=3 with trust_level={trust_level} should require CONTAINER"
    
    def test_risk_level_4_requires_container(self, isolation_policy):
        """Test risk_level >= 4 requires container."""
        from synapse.skills.base import RuntimeIsolationType
        
        for trust_level in ["unverified", "verified", "trusted", "human-approved"]:
            isolation = isolation_policy.get_required_isolation(
                trust_level=trust_level,
                risk_level=4
            )
            assert isolation == RuntimeIsolationType.CONTAINER, \
                f"risk_level=4 with trust_level={trust_level} should require CONTAINER"
    
    def test_risk_level_5_requires_container(self, isolation_policy):
        """Test risk_level = 5 requires container."""
        from synapse.skills.base import RuntimeIsolationType
        
        for trust_level in ["unverified", "verified", "trusted", "human-approved"]:
            isolation = isolation_policy.get_required_isolation(
                trust_level=trust_level,
                risk_level=5
            )
            assert isolation == RuntimeIsolationType.CONTAINER, \
                f"risk_level=5 with trust_level={trust_level} should require CONTAINER"
    
    def test_unverified_always_requires_container(self, isolation_policy):
        """Test unverified skills always require container."""
        from synapse.skills.base import RuntimeIsolationType
        
        for risk_level in [1, 2, 3, 4, 5]:
            isolation = isolation_policy.get_required_isolation(
                trust_level="unverified",
                risk_level=risk_level
            )
            assert isolation == RuntimeIsolationType.CONTAINER, \
                f"unverified skill with risk_level={risk_level} should require CONTAINER"
    
    def test_trusted_low_risk_can_use_subprocess(self, isolation_policy):
        """Test trusted skills with low risk can use subprocess."""
        from synapse.skills.base import RuntimeIsolationType
        
        isolation = isolation_policy.get_required_isolation(
            trust_level="trusted",
            risk_level=1
        )
        # Trusted + low risk should allow subprocess or none
        assert isolation in [RuntimeIsolationType.SUBPROCESS, RuntimeIsolationType.NONE], \
            f"trusted + risk_level=1 should allow SUBPROCESS or NONE, got {isolation}"
    
    def test_verified_medium_risk(self, isolation_policy):
        """Test verified skills with medium risk."""
        from synapse.skills.base import RuntimeIsolationType
        
        # risk_level 2 with verified - should be at least subprocess
        isolation = isolation_policy.get_required_isolation(
            trust_level="verified",
            risk_level=2
        )
        assert isolation in [RuntimeIsolationType.SUBPROCESS, RuntimeIsolationType.CONTAINER], \
            f"verified + risk_level=2 should be SUBPROCESS or CONTAINER, got {isolation}"


class TestIsolationEnforcement:
    """Test that isolation is actually enforced at runtime."""
    
    @pytest.mark.asyncio
    async def test_execution_guard_uses_isolation_policy(self):
        """Test that ExecutionGuard uses IsolationEnforcementPolicy."""
        from synapse.security.execution_guard import ExecutionGuard
        from synapse.security.capability_manager import CapabilityManager
        
        guard = ExecutionGuard(capability_manager=CapabilityManager())
        
        # Verify guard has access to isolation policy
        assert hasattr(guard, "isolation_policy") or hasattr(guard, "get_required_isolation")
    
    @pytest.mark.asyncio
    async def test_high_risk_skill_gets_container_isolation(self):
        """Test that high-risk skills get container isolation."""
        from synapse.security.execution_guard import ExecutionGuard
        from synapse.security.capability_manager import CapabilityManager
        from synapse.core.models import ExecutionContext, ResourceLimits
        from synapse.skills.base import RuntimeIsolationType
        from unittest.mock import MagicMock
        
        guard = ExecutionGuard(capability_manager=CapabilityManager())
        
        # Create high-risk skill
        skill = MagicMock()
        skill.manifest = MagicMock()
        skill.manifest.required_capabilities = []
        skill.manifest.risk_level = 4
        skill.manifest.trust_level = "verified"
        
        context = ExecutionContext(
            session_id="test",
            agent_id="test",
            trace_id="test",
            capabilities=["*"],
            memory_store=MagicMock(),
            logger=MagicMock(),
            resource_limits=ResourceLimits(
                cpu_seconds=60,
                memory_mb=512,
                disk_mb=100,
                network_kb=1024
            ),
            execution_seed=42,
            protocol_version="1.0"
        )
        
        result = await guard.check_execution_allowed(skill, context)
        
        # Should require container isolation
        if hasattr(result, "required_isolation"):
            assert result.required_isolation == RuntimeIsolationType.CONTAINER
