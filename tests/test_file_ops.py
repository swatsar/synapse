"""Tests for file operations."""
import pytest
import tempfile
import os
from unittest.mock import MagicMock, AsyncMock


class TestFileOps:
    """Test file operations."""

    @pytest.mark.asyncio
    async def test_read_file(self):
        """Test reading file."""
        from synapse.skills.system.file_ops import read_file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test content")
            path = f.name
        try:
            result = await read_file(path)
            assert result["content"] == "test content"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_write_file(self):
        """Test writing file."""
        from synapse.skills.system.file_ops import write_file
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            result = await write_file(path, "test content")
            assert result["status"] == "ok"
            with open(path, 'r') as f:
                assert f.read() == "test content"
