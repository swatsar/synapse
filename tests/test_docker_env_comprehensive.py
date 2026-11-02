"""Comprehensive tests for Docker environment."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile
import os


class TestDockerEnvComprehensive:
    """Test Docker environment comprehensively."""
    
    @pytest.fixture
    def docker_env(self):
        """Create a Docker environment for testing."""
        from synapse.environment.docker_env import DockerEnv
        from synapse.security.execution_guard import ExecutionGuard
        from synapse.security.capability_manager import CapabilityManager
        from synapse.core.models import ResourceLimits
        
        # Resolve the real temp dir (long path form) and scope file grants to it.
        tmp = os.path.realpath(tempfile.gettempdir()).replace("\\", "/")
        caps = CapabilityManager()
        caps.grant_capability(f"fs:read:{tmp}/**")
        caps.grant_capability(f"fs:write:{tmp}/**")
        caps.grant_capability("process:spawn")
        caps.grant_capability("network:http")
        
        limits = ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        )
        guard = ExecutionGuard(limits=limits)
        
        return DockerEnv(guard=guard, caps=caps)
    
    def test_docker_env_creation(self, docker_env):
        """Test Docker environment creation."""
        assert docker_env is not None
    
    def test_protocol_version(self, docker_env):
        """Test protocol version."""
        assert docker_env.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_read_file(self, docker_env):
        """Test reading a file."""
        # Create a temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test content")
            temp_path = f.name
        
        try:
            result = await docker_env.read_file(
                os.path.realpath(temp_path).replace("\\", "/")
            )
            assert result == "test content"
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_write_file(self, docker_env):
        """Test writing a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "test_write.txt")
            await docker_env.write_file(
                os.path.realpath(temp_path).replace("\\", "/"), "test write content"
            )
            
            # Verify file was written
            with open(temp_path, 'r') as f:
                content = f.read()
            assert content == "test write content"
    
    @pytest.mark.asyncio
    async def test_execute_process(self, docker_env):
        """Test executing a process with a portable command."""
        import sys

        result = await docker_env.execute_process(
            sys.executable, "-c", "print('test')"
        )

        # DockerEnv delegates to LocalOS and returns the process result.
        assert result is not None
        assert result["returncode"] == 0
        assert "test" in result["stdout"]
    
    @pytest.mark.asyncio
    async def test_http_request(self, docker_env):
        """Test HTTP request."""
        # Skip HTTP tests as they require network
        pytest.skip("HTTP requests require network access")
