"""Tests for local OS environment."""
import pytest
from unittest.mock import MagicMock


class TestLocalOS:
    """Test local OS environment."""
    
    @pytest.fixture
    def local_os(self):
        """Create a local OS environment for testing."""
        from synapse.environment.local_os import LocalOS
        from synapse.security.capability_manager import CapabilityManager
        from synapse.security.execution_guard import ExecutionGuard
        from synapse.core.models import ResourceLimits
        
        caps = CapabilityManager()
        caps.grant_capability("fs:read")
        caps.grant_capability("fs:write")
        caps.grant_capability("process:spawn")
        caps.grant_capability("network:http")
        
        limits = ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        )
        guard = ExecutionGuard(limits=limits)
        
        return LocalOS(guard=guard, caps=caps)
    
    def test_local_os_creation(self, local_os):
        """Test local OS creation."""
        assert local_os is not None
    
    def test_protocol_version(self, local_os):
        """Test protocol version."""
        assert local_os.protocol_version == "1.0"
