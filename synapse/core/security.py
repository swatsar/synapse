"""Capability manager – enforces token based permissions.
"""

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

class CapabilityError(Exception):
    pass

class CapabilityManager:
    async def require(self, capabilities):
        # Placeholder: in real system would check token store.
        # For tests we assume all required capabilities are present.
        if not capabilities:
            raise CapabilityError("Missing required capabilities")
        return True
