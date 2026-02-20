PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

PROTOCOL_VERSION: str = "1.0"
import pytest
from synapse.security.capability_manager import CapabilityManager, CapabilityError

@pytest.mark.asyncio
async def test_missing_capability_raises():
    cap_manager = CapabilityManager()
    with pytest.raises(CapabilityError):
        await cap_manager.validate_capabilities("file_ops", ["fs:read:/workspace/**"])

@pytest.mark.asyncio
async def test_capability_passes_when_all_present():
    cap_manager = CapabilityManager()
    # Should not raise
    await cap_manager.validate_capabilities("file_ops", ["fs:read:/workspace/**", "fs:write:/workspace/**"])
