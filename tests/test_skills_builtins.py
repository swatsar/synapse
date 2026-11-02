"""Tests for built-in skills."""
import pytest
import os
import tempfile
from unittest.mock import MagicMock


class TestReadFileSkill:
    """Test read file skill."""
    
    @pytest.fixture
    def read_file_skill(self):
        """Create a read file skill for testing."""
        from synapse.skills.builtins.read_file import ReadFileSkill
        
        return ReadFileSkill()
    
    @pytest.fixture
    def context(self):
        """Create an execution context for testing."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        return ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=["fs:read"],
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
    
    def test_skill_creation(self, read_file_skill):
        """Test skill creation."""
        assert read_file_skill is not None
    
    @pytest.mark.asyncio
    async def test_execute(self, read_file_skill, context):
        """Test executing the skill."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_path = f.name
        
        try:
            result = await read_file_skill.execute(context, temp_path)
            assert result is not None
            assert result["success"] == True
            assert result["content"] == "test content"
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_execute_capability_denied(self, read_file_skill):
        """Test executing the skill without capability."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        context = ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=[],  # No capabilities
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
        
        result = await read_file_skill.execute(context, "/tmp/test.txt")
        assert result["success"] == False
        assert "error" in result


class TestWriteFileSkill:
    """Test write file skill."""
    
    @pytest.fixture
    def write_file_skill(self):
        """Create a write file skill for testing."""
        from synapse.skills.builtins.write_file import WriteFileSkill
        
        return WriteFileSkill()
    
    @pytest.fixture
    def context(self):
        """Create an execution context for testing."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        return ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=["fs:write"],
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
    
    def test_skill_creation(self, write_file_skill):
        """Test skill creation."""
        assert write_file_skill is not None
    
    @pytest.mark.asyncio
    async def test_execute(self, write_file_skill, context):
        """Test executing the skill."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_path = f.name
        
        try:
            result = await write_file_skill.execute(context, temp_path, "test content")
            assert result is not None
            assert result["success"] == True
            
            with open(temp_path, 'r') as f:
                content = f.read()
            assert content == "test content"
        finally:
            os.unlink(temp_path)


class TestWebSearchSkill:
    """Test web search skill."""
    
    @pytest.fixture
    def web_search_skill(self):
        """Create a web search skill for testing."""
        from synapse.skills.builtins.web_search import WebSearchSkill
        
        return WebSearchSkill()
    
    @pytest.fixture
    def context(self):
        """Create an execution context for testing."""
        from synapse.core.models import ExecutionContext, ResourceLimits
        
        return ExecutionContext(
            session_id="test_session",
            agent_id="test_agent",
            trace_id="test_trace",
            capabilities=["net:http"],
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
    
    def test_skill_creation(self, web_search_skill):
        """Test skill creation."""
        assert web_search_skill is not None
    
    @pytest.mark.asyncio
    async def test_execute(self, web_search_skill, context):
        """Test executing the skill."""
        result = await web_search_skill.execute(context, "test query")
        assert result is not None
        assert result["success"] == True
        assert "response" in result
