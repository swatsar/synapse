"""Tests for resource-aware skill execution.

Phase 10 - Production Autonomy & Self-Optimization.
"""
import pytest
from unittest.mock import MagicMock
from synapse.skills.autonomy.resource_manager import (
    ResourceManager,
    ResourceLimits,
    ResourceUsage
)


pytestmark = pytest.mark.unit


@pytest.fixture
def resource_manager():
    """Create resource manager with default limits."""
    return ResourceManager(
        limits=ResourceLimits(
            max_cpu_percent=80,
            max_memory_mb=4096,
            max_disk_mb=10240,
            max_network_kb=10240
        )
    )


@pytest.mark.asyncio
async def test_resource_manager_checks_limits(resource_manager):
    """ResourceManager correctly checks resource limits."""
    usage = ResourceUsage(
        cpu_percent=50,
        memory_mb=2048,
        disk_mb=5000,
        network_kb=5000
    )
    
    result = resource_manager.check_within_limits(usage)
    
    assert result is True


@pytest.mark.asyncio
async def test_resource_manager_rejects_over_limit(resource_manager):
    """ResourceManager rejects usage over limits."""
    usage = ResourceUsage(
        cpu_percent=90,  # Over 80% limit
        memory_mb=2048,
        disk_mb=5000,
        network_kb=5000
    )
    
    result = resource_manager.check_within_limits(usage)
    
    assert result is False


@pytest.mark.asyncio
async def test_resource_manager_gets_available_resources(resource_manager):
    """ResourceManager returns available resources."""
    available = resource_manager.get_available()
    
    assert "cpu" in available
    assert "memory" in available
    assert "disk" in available
    assert "network" in available


@pytest.mark.asyncio
async def test_resource_manager_tracks_usage(resource_manager):
    """ResourceManager tracks resource usage over time."""
    usage = ResourceUsage(
        cpu_percent=50,
        memory_mb=2048,
        disk_mb=5000,
        network_kb=5000
    )
    
    resource_manager.record_usage("skill_1", usage)
    
    history = resource_manager.get_usage_history("skill_1")
    
    assert len(history) == 1
    assert history[0].cpu_percent == 50


@pytest.mark.asyncio
async def test_resource_manager_enforces_limits_during_execution(resource_manager):
    """ResourceManager enforces limits during skill execution."""
    # Simulate skill trying to use too much memory
    result = await resource_manager.allocate(
        skill_name="test_skill",
        cpu_percent=30,
        memory_mb=5000,  # Over limit
        disk_mb=1000,
        network_kb=1000
    )
    
    assert result.success is False
    assert "memory" in result.error.lower()


def test_resource_limits_protocol_version():
    """ResourceLimits has protocol_version."""
    limits = ResourceLimits(
        max_cpu_percent=80,
        max_memory_mb=4096,
        max_disk_mb=10240,
        max_network_kb=10240
    )
    
    assert limits.protocol_version == "1.0"


def test_resource_usage_protocol_version():
    """ResourceUsage has protocol_version."""
    usage = ResourceUsage(
        cpu_percent=50,
        memory_mb=2048,
        disk_mb=5000,
        network_kb=5000
    )
    
    assert usage.protocol_version == "1.0"
