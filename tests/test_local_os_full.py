"""Tests for LocalOS with full coverage."""
import pytest
import os
import tempfile
from unittest.mock import MagicMock, AsyncMock, patch


class TestLocalOSFull:
    """Test LocalOS with full coverage."""
    
    @pytest.fixture
    def local_os(self):
        """Create a LocalOS."""
        from synapse.environment.local_os import LocalOS
        from synapse.security.capability_manager import CapabilityManager
        from synapse.security.execution_guard import ExecutionGuard
        from synapse.core.models import ResourceLimits
        
        caps = CapabilityManager()
        caps.grant_capability("fs:read:/tmp/**")
        caps.grant_capability("fs:write:/tmp/**")
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
    
    @pytest.mark.asyncio
    async def test_read_file(self, local_os):
        """Test read_file."""
        # Create a temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, dir='/tmp') as f:
            f.write("test content")
            temp_path = f.name
        
        try:
            result = await local_os.read_file(temp_path)
            assert result == "test content"
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_write_file(self, local_os):
        """Test write_file."""
        temp_path = "/tmp/test_write_file.txt"
        
        try:
            await local_os.write_file(temp_path, "test content")
            
            with open(temp_path, 'r') as f:
                result = f.read()
            
            assert result == "test content"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_execute_process(self, local_os):
        """Test execute_process."""
        result = await local_os.execute_process("echo", "hello")
        
        assert result["returncode"] == 0
        assert "hello" in result["stdout"]
