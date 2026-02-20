PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

PROTOCOL_VERSION: str = "1.0"
import pytest
import asyncio
from synapse.security.execution_guard import ExecutionGuard, ResourceLimitError
from synapse.core.models import ResourceLimits

# Dummy async skill for testing – will be used by ExecutionGuard
async def dummy_skill():
    return {"status": "ok"}
# Attach required metadata attributes expected by ExecutionGuard

dummy_skill.trust_level = "trusted"

dummy_skill.risk_level = 1

@pytest.mark.asyncio
async def test_guard_enforces_resources():
    # Zero CPU limit should raise a ResourceLimitError
    limits = ResourceLimits(cpu_seconds=0, memory_mb=256, disk_mb=10, network_kb=500)
    guard = ExecutionGuard(limits)
    with pytest.raises(ResourceLimitError):
        await guard.run(dummy_skill)

@pytest.mark.asyncio
async def test_guard_allows_execution():
    limits = ResourceLimits(cpu_seconds=10, memory_mb=256, disk_mb=10, network_kb=500)
    guard = ExecutionGuard(limits)
    result = await guard.run(dummy_skill)
    assert result == {"status": "ok"}
