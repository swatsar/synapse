"""Tests for distributed policy engine."""
import pytest
from unittest.mock import MagicMock


class TestDistributedPolicyEngine:
    """Test distributed policy engine."""

    @pytest.fixture
    def distributed_policy_engine(self):
        """Create a distributed policy engine for testing."""
        from synapse.policy.distributed.engine import DistributedPolicyEngine
        from synapse.security.capability_manager import CapabilityManager

        caps = CapabilityManager()
        caps.grant_capability("policy:federate")

        return DistributedPolicyEngine(caps=caps)

    def test_distributed_policy_engine_creation(self, distributed_policy_engine):
        """Test distributed policy engine creation."""
        assert distributed_policy_engine is not None

    def test_protocol_version(self, distributed_policy_engine):
        """Test protocol version."""
        assert distributed_policy_engine.protocol_version == "1.0"
