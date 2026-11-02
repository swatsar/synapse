"""Tests for builtin skills."""
import pytest
from unittest.mock import MagicMock, patch


class TestBuiltinSkills:
    """Test builtin skills."""

    def test_read_file_skill_import(self):
        """Test read file skill import."""
        from synapse.skills.builtins.read_file import ReadFileSkill
        skill = ReadFileSkill()
        assert skill is not None

    def test_write_file_skill_import(self):
        """Test write file skill import."""
        from synapse.skills.builtins.write_file import WriteFileSkill
        skill = WriteFileSkill()
        assert skill is not None

    def test_web_search_skill_import(self):
        """Test web search skill import."""
        from synapse.skills.builtins.web_search import WebSearchSkill
        skill = WebSearchSkill()
        assert skill is not None

    @pytest.mark.asyncio
    async def test_read_file_execute(self):
        """Test read file execution."""
        from synapse.skills.builtins.read_file import ReadFileSkill
        skill = ReadFileSkill()
        context = MagicMock()
        context.capabilities = ["fs:read"]
        result = await skill.execute(context, path="/tmp/test.txt")
        assert result is not None

    @pytest.mark.asyncio
    async def test_web_search_execute(self):
        """Test web search execution."""
        from synapse.skills.builtins.web_search import WebSearchSkill
        skill = WebSearchSkill()
        context = MagicMock()
        context.capabilities = ["web:search"]
        result = await skill.execute(context, query="test")
        assert result is not None

    @pytest.mark.asyncio
    async def test_write_file_execute(self):
        """Test write file execution."""
        from synapse.skills.builtins.write_file import WriteFileSkill
        skill = WriteFileSkill()
        context = MagicMock()
        context.capabilities = ["fs:write"]
        result = await skill.execute(context, path="/tmp/test.txt", content="test")
        assert result is not None
