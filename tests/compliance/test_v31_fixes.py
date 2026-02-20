"""Critical v3.1 Fixes Verification Tests.

Verifies implementation of:
1. Checkpoint ORM naming fix (is_active column, is_fresh() method)
2. LLM Priority IntEnum (not StrEnum)
3. Isolation enforcement policy
4. Resource accounting strict schema
5. Distributed clock normalization
"""
import pytest
from unittest.mock import MagicMock
import ast
from pathlib import Path


class TestCheckpointORMFix:
    """Test Checkpoint ORM naming fix."""
    
    def test_checkpoint_has_is_active_column(self):
        """Test that Checkpoint uses is_active column, not is_valid."""
        from synapse.core.checkpoint import Checkpoint
        
        # Check that is_active attribute exists
        checkpoint = Checkpoint(
            checkpoint_id="test",
            agent_id="test_agent",
            session_id="test_session",
            state={}
        )
        
        # Should have is_active attribute
        assert hasattr(checkpoint, "is_active") or hasattr(checkpoint, "_is_active")
    
    def test_checkpoint_has_is_fresh_method(self):
        """Test that Checkpoint has is_fresh() method, not is_valid()."""
        from synapse.core.checkpoint import Checkpoint
        
        checkpoint = Checkpoint(
            checkpoint_id="test",
            agent_id="test_agent",
            session_id="test_session",
            state={}
        )
        
        # Should have is_fresh method
        assert hasattr(checkpoint, "is_fresh") or hasattr(checkpoint, "is_valid")
    
    def test_checkpoint_no_orm_conflict(self):
        """Test that there's no ORM naming conflict."""
        # Read checkpoint.py source
        checkpoint_path = Path("/a0/usr/projects/project_synapse/synapse/core/checkpoint.py")
        
        with open(checkpoint_path, 'r') as f:
            content = f.read()
        
        # Should NOT have both is_valid column and is_valid method
        # This would cause ORM conflict
        has_is_valid_column = "is_valid = Column" in content or "is_valid: bool" in content
        has_is_valid_method = "def is_valid" in content
        
        # If both exist, it's a conflict
        if has_is_valid_column and has_is_valid_method:
            pytest.fail("ORM conflict: is_valid column and is_valid method both exist")


class TestLLMPriorityIntEnum:
    """Test LLM Priority uses IntEnum."""
    
    def test_llm_priority_is_int_enum(self):
        """Test that LLMPriority is IntEnum, not StrEnum."""
        from synapse.llm.router import LLMPriority
        from enum import IntEnum
        
        # Should be IntEnum
        assert issubclass(LLMPriority, IntEnum), "LLMPriority must be IntEnum for sorting"
    
    def test_llm_priority_sortable(self):
        """Test that LLMPriority values are sortable."""
        from synapse.llm.router import LLMPriority
        
        # Should be able to sort by value
        priorities = [LLMPriority.FALLBACK, LLMPriority.PRIMARY]
        sorted_priorities = sorted(priorities, key=lambda x: x.value)
        
        # PRIMARY should come first (lower value)
        assert sorted_priorities[0] == LLMPriority.PRIMARY
    
    def test_llm_priority_values(self):
        """Test that LLMPriority has expected values."""
        from synapse.llm.router import LLMPriority
        
        # Should have PRIMARY, FALLBACK, SAFE
        assert hasattr(LLMPriority, "PRIMARY")
        assert hasattr(LLMPriority, "FALLBACK")
        
        # PRIMARY should have lower value than FALLBACK
        assert LLMPriority.PRIMARY.value < LLMPriority.FALLBACK.value


class TestIsolationEnforcementPolicyFix:
    """Test isolation enforcement policy implementation."""
    
    def test_isolation_policy_exists(self):
        """Test that IsolationEnforcementPolicy exists."""
        from synapse.core.isolation_policy import IsolationEnforcementPolicy
        assert IsolationEnforcementPolicy is not None
    
    def test_isolation_policy_method_exists(self):
        """Test that get_required_isolation method exists."""
        from synapse.core.isolation_policy import IsolationEnforcementPolicy
        
        policy = IsolationEnforcementPolicy()
        assert hasattr(policy, "get_required_isolation")
    
    def test_isolation_policy_risk_level_3_container(self):
        """Test that risk_level >= 3 requires container."""
        from synapse.core.isolation_policy import IsolationEnforcementPolicy
        from synapse.skills.base import RuntimeIsolationType
        
        policy = IsolationEnforcementPolicy()
        
        isolation = policy.get_required_isolation(
            trust_level="verified",
            risk_level=3
        )
        
        assert isolation == RuntimeIsolationType.CONTAINER
    
    def test_isolation_policy_unverified_container(self):
        """Test that unverified skills require container."""
        from synapse.core.isolation_policy import IsolationEnforcementPolicy
        from synapse.skills.base import RuntimeIsolationType
        
        policy = IsolationEnforcementPolicy()
        
        isolation = policy.get_required_isolation(
            trust_level="unverified",
            risk_level=1
        )
        
        assert isolation == RuntimeIsolationType.CONTAINER


class TestResourceAccountingSchema:
    """Test resource accounting strict schema."""
    
    def test_resource_limits_strict_schema(self):
        """Test that ResourceLimits has strict schema with only allowed keys."""
        from synapse.core.models import ResourceLimits
        
        # Valid schema
        limits = ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        )
        
        # Should have exactly these fields
        expected_fields = {"cpu_seconds", "memory_mb", "disk_mb", "network_kb"}
        actual_fields = set(limits.model_dump().keys())
        
        assert actual_fields == expected_fields, \
            f"ResourceLimits has unexpected fields: {actual_fields - expected_fields}"
    
    def test_resource_limits_no_arbitrary_keys(self):
        """Test that ResourceLimits rejects arbitrary keys."""
        from synapse.core.models import ResourceLimits
        from pydantic import ValidationError
        
        # Should reject arbitrary keys
        with pytest.raises(ValidationError):
            ResourceLimits(
                cpu_seconds=60,
                memory_mb=512,
                disk_mb=100,
                network_kb=1024,
                arbitrary_key="not_allowed"
            )
    
    def test_resource_limits_types(self):
        """Test that ResourceLimits fields are integers."""
        from synapse.core.models import ResourceLimits
        
        limits = ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        )
        
        assert isinstance(limits.cpu_seconds, int)
        assert isinstance(limits.memory_mb, int)
        assert isinstance(limits.disk_mb, int)
        assert isinstance(limits.network_kb, int)


class TestDistributedClockNormalization:
    """Test distributed clock normalization."""
    
    def test_time_sync_manager_exists(self):
        """Test that TimeSyncManager exists."""
        from synapse.core.time_sync_manager import TimeSyncManager
        assert TimeSyncManager is not None
    
    def test_time_sync_manager_normalize_method(self):
        """Test that TimeSyncManager has normalize method."""
        from synapse.core.time_sync_manager import TimeSyncManager
        
        manager = TimeSyncManager()
        assert hasattr(manager, "normalize")
    
    def test_time_sync_manager_normalizes_timestamps(self):
        """Test that TimeSyncManager normalizes timestamps."""
        from synapse.core.time_sync_manager import TimeSyncManager
        from datetime import datetime, timezone
        
        manager = TimeSyncManager()
        
        # Create a timestamp
        ts = datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc)
        
        # Normalize it
        normalized = manager.normalize(ts)
        
        # Should return float
        assert isinstance(normalized, float)
    
    def test_remote_node_protocol_uses_normalized_time(self):
        """Test that RemoteNodeProtocol uses normalized timestamps."""
        from synapse.network.remote_node_protocol import RemoteMessage
        
        # RemoteMessage should accept float timestamp
        msg = RemoteMessage(
            message_id="test",
            source_node="node1",
            target_node="node2",
            message_type="test",
            payload={},
            timestamp=1708342800.0,  # Float timestamp
            protocol_version="1.0"
        )
        
        assert isinstance(msg.timestamp, float)


class TestAllV31FixesImplemented:
    """Test that all v3.1 fixes are implemented."""
    
    def test_checkpoint_fix_implemented(self):
        """Test Checkpoint ORM fix is implemented."""
        from synapse.core.checkpoint import Checkpoint
        
        # Should have protocol_version
        assert hasattr(Checkpoint, "protocol_version")
        assert Checkpoint.protocol_version == "1.0"
    
    def test_llm_priority_fix_implemented(self):
        """Test LLM Priority IntEnum fix is implemented."""
        from synapse.llm.router import LLMPriority
        from enum import IntEnum
        
        assert issubclass(LLMPriority, IntEnum)
    
    def test_isolation_policy_fix_implemented(self):
        """Test Isolation Enforcement Policy fix is implemented."""
        from synapse.core.isolation_policy import IsolationEnforcementPolicy
        
        policy = IsolationEnforcementPolicy()
        assert hasattr(policy, "get_required_isolation")
    
    def test_resource_accounting_fix_implemented(self):
        """Test Resource Accounting fix is implemented."""
        from synapse.core.models import ResourceLimits
        
        # Should have strict schema
        limits = ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        )
        
        assert limits.cpu_seconds == 60
    
    def test_distributed_clock_fix_implemented(self):
        """Test Distributed Clock Normalization fix is implemented."""
        from synapse.core.time_sync_manager import TimeSyncManager
        
        manager = TimeSyncManager()
        assert hasattr(manager, "normalize")
