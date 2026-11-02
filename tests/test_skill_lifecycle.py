"""Tests for 6-Status Skill Lifecycle Implementation.
Phase 2: Skill Lifecycle Tests

Tests verify:
- All 6 statuses defined
- Valid transitions work correctly
- Invalid transitions are rejected
- Audit logging occurs
- protocol_version present
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from synapse.skills.dynamic.registry import (
    SkillRegistry,
    SkillLifecycleStatus,
    SkillLifecycleTransitionError,
    SkillRecord,
    PROTOCOL_VERSION,
    SPEC_VERSION
)
from synapse.core.models import SkillManifest, ResourceLimits


@pytest.fixture
def mock_capability_manager():
    manager = AsyncMock()
    manager.check_capability = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def sample_manifest():
    return SkillManifest(
        name="test_skill",
        version="1.0.0",
        description="Test skill",
        author="test",
        inputs={},
        outputs={},
        required_capabilities=[],
        trust_level="unverified",
        risk_level=1
    )


@pytest.fixture
def sample_handler():
    async def handler():
        return "test"
    return handler


@pytest.fixture
def registry(mock_capability_manager):
    return SkillRegistry(capability_manager=mock_capability_manager)


class TestProtocolVersion:
    """Test protocol version compliance."""
    
    def test_protocol_version_constant(self):
        """PROTOCOL_VERSION should be '1.0'."""
        assert PROTOCOL_VERSION == "1.0"
    
    def test_spec_version_constant(self):
        """SPEC_VERSION should be '3.1'."""
        assert SPEC_VERSION == "3.1"
    
    def test_registry_protocol_version(self, registry):
        """Registry should have protocol_version attribute."""
        assert registry.protocol_version == "1.0"


class TestSkillLifecycleStatus:
    """Test SkillLifecycleStatus enum."""
    
    def test_all_six_statuses_exist(self):
        """All 6 statuses should be defined."""
        assert SkillLifecycleStatus.GENERATED.value == "generated"
        assert SkillLifecycleStatus.TESTED.value == "tested"
        assert SkillLifecycleStatus.VERIFIED.value == "verified"
        assert SkillLifecycleStatus.ACTIVE.value == "active"
        assert SkillLifecycleStatus.DEPRECATED.value == "deprecated"
        assert SkillLifecycleStatus.ARCHIVED.value == "archived"
    
    def test_status_count(self):
        """Should have exactly 6 statuses."""
        assert len(SkillLifecycleStatus) == 6


class TestValidTransitions:
    """Test valid lifecycle transitions."""
    
    @pytest.mark.asyncio
    async def test_generated_to_tested(self, registry, sample_manifest, sample_handler):
        """GENERATED → TESTED should be valid."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        result = await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        assert result == True
        assert registry.get_status(skill_id) == SkillLifecycleStatus.TESTED
    
    @pytest.mark.asyncio
    async def test_tested_to_verified(self, registry, sample_manifest, sample_handler):
        """TESTED → VERIFIED should be valid."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        result = await registry.transition(skill_id, SkillLifecycleStatus.VERIFIED)
        assert result == True
        assert registry.get_status(skill_id) == SkillLifecycleStatus.VERIFIED
    
    @pytest.mark.asyncio
    async def test_verified_to_active(self, registry, sample_manifest, sample_handler):
        """VERIFIED → ACTIVE should be valid."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        await registry.transition(skill_id, SkillLifecycleStatus.VERIFIED)
        result = await registry.transition(skill_id, SkillLifecycleStatus.ACTIVE)
        assert result == True
        assert registry.get_status(skill_id) == SkillLifecycleStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_active_to_deprecated(self, registry, sample_manifest, sample_handler):
        """ACTIVE → DEPRECATED should be valid."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        await registry.transition(skill_id, SkillLifecycleStatus.VERIFIED)
        await registry.transition(skill_id, SkillLifecycleStatus.ACTIVE)
        result = await registry.transition(skill_id, SkillLifecycleStatus.DEPRECATED)
        assert result == True
        assert registry.get_status(skill_id) == SkillLifecycleStatus.DEPRECATED
    
    @pytest.mark.asyncio
    async def test_deprecated_to_archived(self, registry, sample_manifest, sample_handler):
        """DEPRECATED → ARCHIVED should be valid."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        await registry.transition(skill_id, SkillLifecycleStatus.VERIFIED)
        await registry.transition(skill_id, SkillLifecycleStatus.ACTIVE)
        await registry.transition(skill_id, SkillLifecycleStatus.DEPRECATED)
        result = await registry.transition(skill_id, SkillLifecycleStatus.ARCHIVED)
        assert result == True
        assert registry.get_status(skill_id) == SkillLifecycleStatus.ARCHIVED
    
    @pytest.mark.asyncio
    async def test_generated_to_archived(self, registry, sample_manifest, sample_handler):
        """GENERATED → ARCHIVED should be valid."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        result = await registry.transition(skill_id, SkillLifecycleStatus.ARCHIVED)
        assert result == True
        assert registry.get_status(skill_id) == SkillLifecycleStatus.ARCHIVED


class TestInvalidTransitions:
    """Test invalid lifecycle transitions."""
    
    @pytest.mark.asyncio
    async def test_generated_to_active_invalid(self, registry, sample_manifest, sample_handler):
        """GENERATED → ACTIVE should be invalid."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        with pytest.raises(SkillLifecycleTransitionError):
            await registry.transition(skill_id, SkillLifecycleStatus.ACTIVE)
    
    @pytest.mark.asyncio
    async def test_generated_to_verified_invalid(self, registry, sample_manifest, sample_handler):
        """GENERATED → VERIFIED should be invalid."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        with pytest.raises(SkillLifecycleTransitionError):
            await registry.transition(skill_id, SkillLifecycleStatus.VERIFIED)
    
    @pytest.mark.asyncio
    async def test_archived_no_transitions(self, registry, sample_manifest, sample_handler):
        """ARCHIVED should have no outgoing transitions."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.ARCHIVED)
        
        # Try all possible transitions from ARCHIVED
        for status in SkillLifecycleStatus:
            if status != SkillLifecycleStatus.ARCHIVED:
                with pytest.raises(SkillLifecycleTransitionError):
                    await registry.transition(skill_id, status)
    
    @pytest.mark.asyncio
    async def test_active_to_tested_invalid(self, registry, sample_manifest, sample_handler):
        """ACTIVE → TESTED should be invalid."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        await registry.transition(skill_id, SkillLifecycleStatus.VERIFIED)
        await registry.transition(skill_id, SkillLifecycleStatus.ACTIVE)
        
        with pytest.raises(SkillLifecycleTransitionError):
            await registry.transition(skill_id, SkillLifecycleStatus.TESTED)


class TestSkillRecord:
    """Test SkillRecord class."""
    
    def test_record_creation(self, sample_manifest, sample_handler):
        """SkillRecord should be created with correct attributes."""
        record = SkillRecord(
            skill_id="test-id",
            manifest=sample_manifest,
            handler=sample_handler
        )
        assert record.skill_id == "test-id"
        assert record.status == SkillLifecycleStatus.GENERATED
        assert record.protocol_version == "1.0"
    
    def test_record_to_dict(self, sample_manifest, sample_handler):
        """SkillRecord.to_dict() should include protocol_version."""
        record = SkillRecord(
            skill_id="test-id",
            manifest=sample_manifest,
            handler=sample_handler
        )
        d = record.to_dict()
        assert "protocol_version" in d
        assert d["protocol_version"] == "1.0"
        assert "status" in d
        assert "status_history" in d


class TestRegistryMethods:
    """Test registry helper methods."""
    
    @pytest.mark.asyncio
    async def test_register_returns_skill_id(self, registry, sample_manifest, sample_handler):
        """register() should return a skill ID."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        assert skill_id is not None
        assert isinstance(skill_id, str)
    
    @pytest.mark.asyncio
    async def test_get_status(self, registry, sample_manifest, sample_handler):
        """get_status() should return current status."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        status = registry.get_status(skill_id)
        assert status == SkillLifecycleStatus.GENERATED
    
    @pytest.mark.asyncio
    async def test_get_active_skills(self, registry, sample_manifest, sample_handler):
        """get_active_skills() should return only active skills."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        await registry.transition(skill_id, SkillLifecycleStatus.VERIFIED)
        await registry.transition(skill_id, SkillLifecycleStatus.ACTIVE)
        
        active = registry.get_active_skills()
        assert len(active) == 1
        assert active[0].skill_id == skill_id
    
    @pytest.mark.asyncio
    async def test_get_skills_by_status(self, registry, sample_manifest, sample_handler):
        """get_skills_by_status() should filter correctly."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        
        tested = registry.get_skills_by_status(SkillLifecycleStatus.TESTED)
        assert len(tested) == 1
        
        generated = registry.get_skills_by_status(SkillLifecycleStatus.GENERATED)
        assert len(generated) == 0
    
    @pytest.mark.asyncio
    async def test_activate_skill(self, registry, sample_manifest, sample_handler):
        """activate_skill() should transition to ACTIVE."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        await registry.transition(skill_id, SkillLifecycleStatus.VERIFIED)
        result = await registry.activate_skill(skill_id)
        assert result == True
        assert registry.get_status(skill_id) == SkillLifecycleStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_deprecate_skill(self, registry, sample_manifest, sample_handler):
        """deprecate_skill() should transition to DEPRECATED."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        await registry.transition(skill_id, SkillLifecycleStatus.VERIFIED)
        await registry.transition(skill_id, SkillLifecycleStatus.ACTIVE)
        result = await registry.deprecate_skill(skill_id)
        assert result == True
        assert registry.get_status(skill_id) == SkillLifecycleStatus.DEPRECATED
    
    @pytest.mark.asyncio
    async def test_archive_skill(self, registry, sample_manifest, sample_handler):
        """archive_skill() should transition to ARCHIVED."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        await registry.transition(skill_id, SkillLifecycleStatus.VERIFIED)
        await registry.transition(skill_id, SkillLifecycleStatus.ACTIVE)
        await registry.transition(skill_id, SkillLifecycleStatus.DEPRECATED)
        result = await registry.archive_skill(skill_id)
        assert result == True
        assert registry.get_status(skill_id) == SkillLifecycleStatus.ARCHIVED


class TestStatusHistory:
    """Test status history tracking."""
    
    @pytest.mark.asyncio
    async def test_status_history_records_transitions(self, registry, sample_manifest, sample_handler):
        """Each transition should be recorded in status_history."""
        skill_id = await registry.register(sample_manifest, sample_handler)
        await registry.transition(skill_id, SkillLifecycleStatus.TESTED)
        
        record = registry.get_by_id(skill_id)
        assert len(record.status_history) == 2  # initial + transition
        
        last_entry = record.status_history[-1]
        assert last_entry["status"] == "tested"
        assert "from_status" in last_entry
        assert "timestamp" in last_entry
