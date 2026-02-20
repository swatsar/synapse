"""Direct tests for synapse/skills/base.py BaseSkill class."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

PROTOCOL_VERSION: str = "1.0"


# Create a concrete implementation of BaseSkill for testing
def create_concrete_skill_class():
    """Create a concrete skill class that inherits from BaseSkill."""
    from synapse.skills.base import BaseSkill
    
    class TestConcreteSkill(BaseSkill):
        """Concrete implementation for testing."""
        
        async def execute(self, context, **kwargs):
            """Execute the skill."""
            return {"success": True, "result": "test_result", "protocol_version": self.protocol_version}
    
    return TestConcreteSkill


def create_failing_skill_class():
    """Create a skill class that raises exceptions."""
    from synapse.skills.base import BaseSkill
    
    class TestFailingSkill(BaseSkill):
        """Failing implementation for testing."""
        
        async def execute(self, context, **kwargs):
            """Execute the skill - always fails."""
            raise ValueError("Test error from skill")
    
    return TestFailingSkill


class TestBaseSkillDirect:
    """Direct tests for BaseSkill class."""
    
    def test_init_without_manifest(self):
        """Test BaseSkill initialization without manifest."""
        TestSkill = create_concrete_skill_class()
        skill = TestSkill()
        
        assert skill.protocol_version == "1.0"
        assert skill.manifest is None
    
    def test_init_with_manifest(self):
        """Test BaseSkill initialization with manifest."""
        TestSkill = create_concrete_skill_class()
        manifest = MagicMock()
        manifest.name = "test_skill"
        
        skill = TestSkill(manifest=manifest)
        
        assert skill.manifest is not None
        assert skill.manifest.name == "test_skill"
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful skill execution."""
        TestSkill = create_concrete_skill_class()
        skill = TestSkill()
        context = MagicMock()
        context.trace_id = "test_trace_123"
        
        result = await skill.execute(context, test_param="value")
        
        assert result["success"] == True
        assert result["result"] == "test_result"
    
    @pytest.mark.asyncio
    async def test_execute_with_audit_success(self):
        """Test _execute_with_audit with successful execution."""
        TestSkill = create_concrete_skill_class()
        skill = TestSkill()
        context = MagicMock()
        context.trace_id = "test_trace_456"
        
        result = await skill._execute_with_audit(context, param1="value1")
        
        assert result["success"] == True
    
    @pytest.mark.asyncio
    async def test_execute_with_audit_failure(self):
        """Test _execute_with_audit with failed execution."""
        TestFailingSkill = create_failing_skill_class()
        skill = TestFailingSkill()
        context = MagicMock()
        context.trace_id = "test_trace_789"
        
        with pytest.raises(ValueError, match="Test error from skill"):
            await skill._execute_with_audit(context)
    
    @pytest.mark.asyncio
    async def test_execute_with_audit_no_context(self):
        """Test _execute_with_audit without context."""
        TestSkill = create_concrete_skill_class()
        skill = TestSkill()
        
        result = await skill._execute_with_audit(None)
        
        assert result["success"] == True
    
    def test_get_required_capabilities_no_manifest(self):
        """Test get_required_capabilities without manifest."""
        TestSkill = create_concrete_skill_class()
        skill = TestSkill()
        
        caps = skill.get_required_capabilities()
        
        assert caps == []
    
    def test_get_required_capabilities_with_manifest_no_caps(self):
        """Test get_required_capabilities with manifest but no caps attribute."""
        TestSkill = create_concrete_skill_class()
        manifest = MagicMock(spec=[])  # No required_capabilities attribute
        
        skill = TestSkill(manifest=manifest)
        caps = skill.get_required_capabilities()
        
        assert caps == []
    
    def test_get_required_capabilities_with_manifest_and_caps(self):
        """Test get_required_capabilities with manifest and caps."""
        TestSkill = create_concrete_skill_class()
        manifest = MagicMock()
        manifest.required_capabilities = ["fs:read", "fs:write", "network:http"]
        
        skill = TestSkill(manifest=manifest)
        caps = skill.get_required_capabilities()
        
        assert caps == ["fs:read", "fs:write", "network:http"]
    
    def test_protocol_version_class_attribute(self):
        """Test that protocol_version is a class attribute."""
        TestSkill = create_concrete_skill_class()
        assert TestSkill.protocol_version == "1.0"
    
    def test_protocol_version_instance_attribute(self):
        """Test that protocol_version is set on instance."""
        TestSkill = create_concrete_skill_class()
        skill = TestSkill()
        assert skill.protocol_version == "1.0"


class TestSkillTrustLevel:
    """Tests for SkillTrustLevel class."""
    
    def test_trust_level_trusted(self):
        """Test TRUSTED trust level."""
        from synapse.skills.base import SkillTrustLevel
        assert SkillTrustLevel.TRUSTED == "trusted"
    
    def test_trust_level_verified(self):
        """Test VERIFIED trust level."""
        from synapse.skills.base import SkillTrustLevel
        assert SkillTrustLevel.VERIFIED == "verified"
    
    def test_trust_level_unverified(self):
        """Test UNVERIFIED trust level."""
        from synapse.skills.base import SkillTrustLevel
        assert SkillTrustLevel.UNVERIFIED == "unverified"


class TestModuleConstants:
    """Tests for module-level constants."""
    
    def test_protocol_version_constant(self):
        """Test module PROTOCOL_VERSION constant."""
        from synapse.skills.base import PROTOCOL_VERSION
        assert PROTOCOL_VERSION == "1.0"
    
    def test_spec_version_constant(self):
        """Test module SPEC_VERSION constant."""
        from synapse.skills.base import SPEC_VERSION
        assert SPEC_VERSION == "3.1"
