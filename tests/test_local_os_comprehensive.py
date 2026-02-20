"""Comprehensive tests for local OS environment."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile
import os


class TestLocalOSComprehensive:
    """Test local OS environment comprehensively."""
    
    @pytest.fixture
    def local_os(self):
        """Create a local OS environment for testing."""
        from synapse.environment.local_os import LocalOS
        from synapse.security.execution_guard import ExecutionGuard
        from synapse.security.capability_manager import CapabilityManager
        from synapse.core.models import ResourceLimits
        
        caps = CapabilityManager()
        caps.grant_capability("fs:read:/")
        caps.grant_capability("fs:write:/")
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
    
    @pytest.mark.asyncio
    async def test_read_file(self, local_os):
        """Test reading a file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_path = f.name
        
        try:
            content = await local_os.read_file(temp_path)
            assert content == "test content"
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_write_file(self, local_os):
        """Test writing a file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, "test.txt")
            
            await local_os.write_file(temp_path, "test content")
            
            with open(temp_path, 'r') as f:
                content = f.read()
            
            assert content == "test content"
    
    @pytest.mark.asyncio
    async def test_execute_process(self, local_os):
        """Test executing a process."""
        # Use the correct signature: command, *args
        result = await local_os.execute_process("echo", "hello")
        
        assert result is not None
        assert result["returncode"] == 0
        assert "hello" in result["stdout"]
    
    @pytest.mark.asyncio
    async def test_http_request(self, local_os):
        """Test HTTP request."""
        # Skip this test as it requires network
        pytest.skip("Requires network")
