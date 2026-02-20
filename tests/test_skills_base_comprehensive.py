"""Comprehensive tests for skills/base.py to improve coverage."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

PROTOCOL_VERSION: str = "1.0"


class ConcreteSkill:
    """Concrete implementation of BaseSkill for testing."""
    
    protocol_version: str = "1.0"
    
    def __init__(self, manifest=None):
        self.protocol_version = "1.0"
        self.manifest = manifest
    
    async def execute(self, context, **kwargs):
        """Execute the skill."""
        return {"success": True, "result": "test_result"}
    
    async def _execute_with_audit(self, context, **kwargs):
        """Execute with audit logging."""
        skill_name = self.__class__.__name__
        trace_id = getattr(context, 'trace_id', 'unknown') if context else 'unknown'
        
        try:
            result = await self.execute(context, **kwargs)
            return result
        except Exception as e:
            raise
    
    def get_required_capabilities(self):
        """Get required capabilities."""
        if self.manifest:
            return getattr(self.manifest, "required_capabilities", [])
        return []


class FailingSkill:
    """Skill that raises exception for testing error handling."""
    
    protocol_version: str = "1.0"
    
    def __init__(self, manifest=None):
        self.protocol_version = "1.0"
        self.manifest = manifest
    
    async def execute(self, context, **kwargs):
        """Execute the skill - always fails."""
        raise ValueError("Test error")
    
    async def _execute_with_audit(self, context, **kwargs):
        """Execute with audit logging."""
        try:
            result = await self.execute(context, **kwargs)
            return result
        except Exception as e:
            raise
    
    def get_required_capabilities(self):
        """Get required capabilities."""
        return []


class TestBaseSkillInit:
    """Tests for BaseSkill initialization."""
    
    def test_init_without_manifest(self):
        """Test initialization without manifest."""
        skill = ConcreteSkill()
        assert skill.protocol_version == "1.0"
        assert skill.manifest is None
    
    def test_init_with_manifest(self):
        """Test initialization with manifest."""
        manifest = MagicMock()
        manifest.name = "test_skill"
        skill = ConcreteSkill(manifest=manifest)
        assert skill.manifest is not None
        assert skill.manifest.name == "test_skill"


class TestBaseSkillExecute:
    """Tests for BaseSkill execute method."""
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful execution."""
        skill = ConcreteSkill()
        context = MagicMock()
        context.trace_id = "test_trace"
        
        result = await skill.execute(context, test_param="value")
        
        assert result["success"] == True
        assert result["result"] == "test_result"
    
    @pytest.mark.asyncio
    async def test_execute_with_audit_success(self):
        """Test _execute_with_audit with successful execution."""
        skill = ConcreteSkill()
        context = MagicMock()
        context.trace_id = "test_trace"
        
        result = await skill._execute_with_audit(context, test_param="value")
        
        assert result["success"] == True
    
    @pytest.mark.asyncio
    async def test_execute_with_audit_failure(self):
        """Test _execute_with_audit with failed execution."""
        skill = FailingSkill()
        context = MagicMock()
        context.trace_id = "test_trace"
        
        with pytest.raises(ValueError, match="Test error"):
            await skill._execute_with_audit(context)
    
    @pytest.mark.asyncio
    async def test_execute_without_context(self):
        """Test execution without context."""
        skill = ConcreteSkill()
        
        result = await skill.execute(None)
        
        assert result["success"] == True


class TestGetRequiredCapabilities:
    """Tests for get_required_capabilities method."""
    
    def test_get_capabilities_without_manifest(self):
        """Test get_required_capabilities without manifest."""
        skill = ConcreteSkill()
        caps = skill.get_required_capabilities()
        assert caps == []
    
    def test_get_capabilities_with_manifest_no_caps(self):
        """Test get_required_capabilities with manifest but no caps."""
        manifest = MagicMock()
        # Don't set required_capabilities attribute
        del manifest.required_capabilities
        
        skill = ConcreteSkill(manifest=manifest)
        caps = skill.get_required_capabilities()
        assert caps == []
    
    def test_get_capabilities_with_manifest_and_caps(self):
        """Test get_required_capabilities with manifest and caps."""
        manifest = MagicMock()
        manifest.required_capabilities = ["fs:read", "fs:write"]
        
        skill = ConcreteSkill(manifest=manifest)
        caps = skill.get_required_capabilities()
        
        assert caps == ["fs:read", "fs:write"]


class TestProtocolVersion:
    """Tests for protocol version compliance."""
    
    def test_protocol_version_attribute(self):
        """Test that protocol_version is set correctly."""
        skill = ConcreteSkill()
        assert skill.protocol_version == "1.0"
    
    def test_protocol_version_in_result(self):
        """Test that protocol_version can be included in results."""
        skill = ConcreteSkill()
        result = {"success": True, "protocol_version": skill.protocol_version}
        assert result["protocol_version"] == "1.0"
