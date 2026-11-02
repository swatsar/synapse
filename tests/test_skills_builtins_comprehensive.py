"""Comprehensive tests for skills builtins."""
import pytest
import tempfile
import os
from unittest.mock import MagicMock, AsyncMock, patch


class TestReadFileSkillComprehensive:
    """Test read_file skill comprehensively."""
    
    @pytest.fixture
    def skill(self):
        """Create a read_file skill for testing."""
        from synapse.skills.builtins.read_file import ReadFileSkill
        
        return ReadFileSkill()
    
    @pytest.fixture
    def context(self):
        """Create a mock execution context."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        return ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=["fs:read:/workspace/**"],
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
    
    def test_skill_creation(self, skill):
        """Test skill creation."""
        assert skill is not None
    
    @pytest.mark.asyncio
    async def test_execute_read_file(self, skill, context):
        """Test reading a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test content")
            
            result = await skill.execute(context, path=test_file)
            
            assert result["success"] == True
            assert "test content" in result["content"]
    
    @pytest.mark.asyncio
    async def test_execute_read_file_capability_denied(self, skill):
        """Test reading a file without capability."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        context = ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=[],  # No fs:read capability
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
        
        result = await skill.execute(context, path="/tmp/test.txt")
        
        assert result["success"] == False
        assert "Capability denied" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_read_file_not_found(self, skill, context):
        """Test reading a non-existent file."""
        result = await skill.execute(context, path="/nonexistent/file.txt")
        
        assert result["success"] == False
        assert "error" in result


class TestWriteFileSkillComprehensive:
    """Test write_file skill comprehensively."""
    
    @pytest.fixture
    def skill(self):
        """Create a write_file skill for testing."""
        from synapse.skills.builtins.write_file import WriteFileSkill
        
        return WriteFileSkill()
    
    @pytest.fixture
    def context(self):
        """Create a mock execution context."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        return ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=["fs:write:/workspace/**"],
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
    
    def test_skill_creation(self, skill):
        """Test skill creation."""
        assert skill is not None
    
    @pytest.mark.asyncio
    async def test_execute_write_file(self, skill, context):
        """Test writing a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            
            result = await skill.execute(context, path=test_file, content="test content")
            
            assert result["success"] == True
            
            with open(test_file, "r") as f:
                assert f.read() == "test content"
    
    @pytest.mark.asyncio
    async def test_execute_write_file_capability_denied(self, skill):
        """Test writing a file without capability."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        context = ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=[],  # No fs:write capability
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
        
        result = await skill.execute(context, path="/tmp/test.txt", content="test")
        
        assert result["success"] == False
        assert "Capability denied" in result["error"]
