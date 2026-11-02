"""Comprehensive tests for resource manager."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestResourceManagerFull:
    """Test resource manager comprehensively."""
    
    @pytest.fixture
    def resource_manager(self):
        """Create a resource manager for testing."""
        from synapse.skills.autonomy.resource_manager import ResourceManager, ResourceLimits
        
        limits = ResourceLimits(
            max_cpu_percent=100,
            max_memory_mb=512,
            max_disk_mb=100,
            max_network_kb=1024
        )
        
        return ResourceManager(limits=limits)
    
    def test_resource_manager_creation(self, resource_manager):
        """Test resource manager creation."""
        assert resource_manager is not None
    
    def test_protocol_version(self, resource_manager):
        """Test protocol version."""
        assert resource_manager.protocol_version == "1.0"
    
    def test_check_within_limits_true(self, resource_manager):
        """Test checking usage within limits."""
        from synapse.skills.autonomy.resource_manager import ResourceUsage
        
        usage = ResourceUsage(
            cpu_percent=50,
            memory_mb=256,
            disk_mb=50,
            network_kb=512
        )
        
        result = resource_manager.check_within_limits(usage)
        assert result == True
    
    def test_check_within_limits_false(self, resource_manager):
        """Test checking usage exceeds limits."""
        from synapse.skills.autonomy.resource_manager import ResourceUsage
        
        usage = ResourceUsage(
            cpu_percent=150,
            memory_mb=1024,
            disk_mb=200,
            network_kb=2048
        )
        
        result = resource_manager.check_within_limits(usage)
        assert result == False
    
    def test_get_available(self, resource_manager):
        """Test getting available resources."""
        available = resource_manager.get_available()
        assert isinstance(available, dict)
        assert "cpu" in available
        assert "memory" in available
        assert "disk" in available
        assert "network" in available
    
    def test_record_usage(self, resource_manager):
        """Test recording usage."""
        from synapse.skills.autonomy.resource_manager import ResourceUsage
        
        usage = ResourceUsage(
            cpu_percent=50,
            memory_mb=256,
            disk_mb=50,
            network_kb=512
        )
        
        resource_manager.record_usage("test_skill", usage)
        
        history = resource_manager.get_usage_history("test_skill")
        assert len(history) == 1
    
    def test_get_usage_history_empty(self, resource_manager):
        """Test getting usage history for unknown skill."""
        history = resource_manager.get_usage_history("unknown_skill")
        assert history == []
    
    @pytest.mark.asyncio
    async def test_allocate_success(self, resource_manager):
        """Test successful allocation."""
        result = await resource_manager.allocate(
            skill_name="test_skill",
            cpu_percent=50,
            memory_mb=256,
            disk_mb=50,
            network_kb=512
        )
        
        assert result.success == True
        assert "cpu" in result.allocated
    
    @pytest.mark.asyncio
    async def test_allocate_exceeds_limits(self, resource_manager):
        """Test allocation that exceeds limits."""
        result = await resource_manager.allocate(
            skill_name="test_skill",
            cpu_percent=150,
            memory_mb=1024,
            disk_mb=200,
            network_kb=2048
        )
        
        assert result.success == False
        assert "exceeded" in result.error
    
    @pytest.mark.asyncio
    async def test_release(self, resource_manager):
        """Test releasing resources."""
        # First allocate
        await resource_manager.allocate(
            skill_name="test_skill",
            cpu_percent=50,
            memory_mb=256,
            disk_mb=50,
            network_kb=512
        )
        
        # Then release
        result = resource_manager.release("test_skill")
        assert result == True
    
    def test_release_unknown(self, resource_manager):
        """Test releasing unknown skill."""
        result = resource_manager.release("unknown_skill")
        assert result == False
