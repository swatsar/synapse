PROTOCOL_VERSION: str = "1.0"
from synapse.policy.engine import PolicyEngine
from synapse.security.capability_manager import CapabilityManager

class DistributedPolicyEngine(PolicyEngine):
    """PolicyEngine that also enforces capability federation across nodes.

    It inherits the core decision logic and adds a check that the caller has
    the ``policy:federate`` capability before any policy change is applied.
    """
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager):
        super().__init__(capability_manager=caps)
        self._caps = caps

    async def evaluate(self, manifest):
        # Ensure federation capability before delegating to the base logic.
        await self._caps.check_capability(["policy:federate"])
        return await super().evaluate(manifest)
