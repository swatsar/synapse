"""Tests for Code Generator."""

import pytest
from unittest.mock import AsyncMock, MagicMock

import sys
sys.path.insert(0, '/a0/usr/projects/project_synapse')

from synapse.integrations.code_generator import (
    CodeGenerator,
    GeneratedCode,
    CodeLanguage,
    CodeSecurityLevel,
    PROTOCOL_VERSION
)


class TestCodeGeneratorProtocol:
    """Tests for protocol version compliance."""
    
    def test_protocol_version_defined(self):
        assert PROTOCOL_VERSION == "1.0"
    
    def test_generator_has_protocol_version(self):
        assert CodeGenerator.PROTOCOL_VERSION == "1.0"
    
    def test_generated_code_has_protocol_version(self):
        code = GeneratedCode(code="test", language=CodeLanguage.PYTHON)
        assert code.protocol_version == "1.0"


class TestCodeGenerator:
    """Tests for CodeGenerator."""
    
    @pytest.fixture
    def generator(self):
        return CodeGenerator()
    
    @pytest.mark.asyncio
    async def test_generate_code(self, generator):
        result = await generator.generate(
            task_description="Create a hello world function",
            language=CodeLanguage.PYTHON
        )
        assert result.code is not None
        assert result.language == CodeLanguage.PYTHON
        assert result.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_security_scan_safe(self, generator):
        safe_code = "def hello(): return 'world'"
        level, issues = await generator._scan_security(safe_code, CodeLanguage.PYTHON)
        assert level == CodeSecurityLevel.SAFE
        assert len(issues) == 0
    
    @pytest.mark.asyncio
    async def test_security_scan_unsafe(self, generator):
        unsafe_code = "eval(user_input)"
        level, issues = await generator._scan_security(unsafe_code, CodeLanguage.PYTHON)
        assert level == CodeSecurityLevel.UNSAFE
        assert len(issues) > 0
    
    @pytest.mark.asyncio
    async def test_generate_tests(self, generator):
        tests = await generator._generate_tests("def test(): pass", CodeLanguage.PYTHON)
        assert "test" in tests.lower()
    
    @pytest.mark.asyncio
    async def test_generate_documentation(self, generator):
        docs = await generator._generate_documentation(
            "code",
            CodeLanguage.PYTHON,
            "test task"
        )
        assert "Protocol Version" in docs
        assert "1.0" in docs


class TestSkillManifest:
    """Tests for skill manifest."""
    
    def test_manifest_has_protocol_version(self):
        from synapse.integrations.code_generator import SKILL_MANIFEST
        assert SKILL_MANIFEST["protocol_version"] == "1.0"
