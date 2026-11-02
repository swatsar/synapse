"""Tests for dynamic registry load_from_path method."""
import pytest
import tempfile
import os


class TestDynamicRegistryLoad:
    """Test dynamic registry load_from_path method."""
    
    @pytest.fixture
    def registry(self):
        """Create a skill registry for testing."""
        from synapse.skills.dynamic.registry import SkillRegistry
        from synapse.security.capability_manager import CapabilityManager
        
        caps = CapabilityManager()
        caps.grant_capability("test:skill")
        
        return SkillRegistry(capability_manager=caps)
    
    @pytest.mark.asyncio
    async def test_load_from_path(self, registry):
        """Test loading a skill from a file."""
        # Create a temporary skill file
        skill_content = '''
from synapse.core.models import SkillManifest

manifest = SkillManifest(
    name="test_skill",
    version="1.0.0",
    description="Test skill",
    author="test",
    inputs={},
    outputs={},
    required_capabilities=["test:skill"]
)

async def handler(context):
    return {"success": True}
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(skill_content)
            temp_path = f.name
        
        try:
            await registry.load_from_path(temp_path)
            
            # Verify skill was loaded
            assert "test_skill" in registry.list_skills()
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_load_from_path_missing_manifest(self, registry):
        """Test loading a skill file without manifest."""
        skill_content = '''
# No manifest defined
async def handler(context):
    return {"success": True}
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(skill_content)
            temp_path = f.name
        
        try:
            with pytest.raises(AttributeError):
                await registry.load_from_path(temp_path)
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_load_from_path_missing_handler(self, registry):
        """Test loading a skill file without handler."""
        skill_content = '''
from synapse.core.models import SkillManifest

manifest = SkillManifest(
    name="test_skill",
    version="1.0.0",
    description="Test skill",
    author="test",
    inputs={},
    outputs={},
    required_capabilities=[]
)

# No handler defined
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(skill_content)
            temp_path = f.name
        
        try:
            with pytest.raises(AttributeError):
                await registry.load_from_path(temp_path)
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_load_from_path_invalid_path(self, registry):
        """Test loading from an invalid path."""
        with pytest.raises(FileNotFoundError):
            await registry.load_from_path("/nonexistent/path/skill.py")
