"""Tests for WriteFileSkill with full coverage."""
import pytest
import os
import tempfile
from unittest.mock import MagicMock, AsyncMock, patch


class TestWriteFileSkillFull:
    """Test WriteFileSkill with full coverage."""
    
    @pytest.fixture
    def write_file_skill(self):
        """Create a WriteFileSkill."""
        from synapse.skills.builtins.write_file import WriteFileSkill
        
        return WriteFileSkill()
    
    @pytest.fixture
    def context_with_caps(self):
        """Create a context with write capabilities."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        return ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=["fs:write:/tmp/**"],
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
    
    @pytest.fixture
    def context_without_caps(self):
        """Create a context without write capabilities."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        return ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=["fs:read:/tmp/**"],
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
    
    @pytest.mark.asyncio
    async def test_write_file_success(self, write_file_skill, context_with_caps):
        """Test write_file success."""
        temp_path = "/tmp/test_write_file_success.txt"
        
        try:
            result = await write_file_skill.execute(context_with_caps, temp_path, "test content")
            
            assert result["success"] == True
            assert os.path.exists(temp_path)
            with open(temp_path, 'r') as f:
                assert f.read() == "test content"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_write_file_capability_denied(self, write_file_skill, context_without_caps):
        """Test write_file capability denied."""
        temp_path = "/tmp/test_write_file_denied.txt"
        
        result = await write_file_skill.execute(context_without_caps, temp_path, "test content")
        
        assert result["success"] == False
        assert "error" in result
        assert "Capability denied" in result["error"]
    
    @pytest.mark.asyncio
    async def test_write_file_creates_directory(self, write_file_skill, context_with_caps):
        """Test write_file creates directory."""
        temp_dir = "/tmp/test_dir_write"
        temp_path = os.path.join(temp_dir, "subdir", "test_file.txt")
        
        try:
            result = await write_file_skill.execute(context_with_caps, temp_path, "test content")
            
            assert result["success"] == True
            assert os.path.exists(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            if os.path.exists(os.path.dirname(temp_path)):
                os.rmdir(os.path.dirname(temp_path))
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
    
    @pytest.mark.asyncio
    async def test_write_file_error(self, write_file_skill, context_with_caps):
        """Test write_file error handling."""
        # Try to write to a path that will fail (e.g., permission denied)
        # We'll use a mock to simulate an error
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            result = await write_file_skill.execute(context_with_caps, "/tmp/test_error.txt", "test content")
            
            assert result["success"] == False
            assert "error" in result
