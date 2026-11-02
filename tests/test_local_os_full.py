"""Tests for LocalOS with full coverage."""
import pytest
import os
import sys
import tempfile
from unittest.mock import MagicMock, AsyncMock, patch


def _posix(path: str) -> str:
    """Normalize a path to forward slashes for capability patterns."""
    return path.replace("\\", "/")


class TestLocalOSFull:
    """Test LocalOS with full coverage."""

    @pytest.fixture
    def local_os(self):
        """Create a LocalOS with capabilities scoped to the platform temp dir."""
        from synapse.environment.local_os import LocalOS
        from synapse.security.capability_manager import CapabilityManager
        from synapse.security.execution_guard import ExecutionGuard
        from synapse.core.models import ResourceLimits

        tmp = _posix(tempfile.gettempdir())
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

        return LocalOS(guard=guard, caps=caps)

    @pytest.mark.asyncio
    async def test_read_file(self, local_os):
        """Test read_file."""
        # Create a temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            result = await local_os.read_file(_posix(temp_path))
            assert result == "test content"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_write_file(self, local_os):
        """Test write_file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "test_write_file.txt")

            await local_os.write_file(_posix(temp_path), "test content")

            with open(temp_path, 'r') as f:
                result = f.read()

            assert result == "test content"

    @pytest.mark.asyncio
    async def test_execute_process(self, local_os):
        """Test execute_process with a portable command."""
        result = await local_os.execute_process(
            sys.executable, "-c", "print('hello')"
        )

        assert result["returncode"] == 0
        assert "hello" in result["stdout"]
