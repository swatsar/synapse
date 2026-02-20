PROTOCOL_VERSION: str = "1.0"
from typing import List

from synapse.core.models import SkillManifest
from synapse.security.capability_manager import CapabilityManager

class PolicyEngine:
    """Simple policy engine that decides whether a skill may be executed.
    It checks safety constraints, required capabilities and adaptive parameters.
    """
    protocol_version: str = "1.0"

    def __init__(self, capability_manager: CapabilityManager):
        self.capability_manager = capability_manager
        self._rules: List[callable] = []
        self._register_default_rules()

    def _register_default_rules(self):
        # Rule: reject skills with risk_level > 3 unless explicit approval capability exists
        def risk_rule(manifest: SkillManifest) -> bool:
            if getattr(manifest, "risk_level", 0) > 3:
                return "admin_approval" in self.capability_manager.active_capabilities
            return True
        self._rules.append(risk_rule)

    def add_rule(self, rule_callable):
        """Add a custom rule – it must accept a SkillManifest and return bool."""
        self._rules.append(rule_callable)

    async def evaluate(self, manifest: SkillManifest) -> bool:
        """Return True if all rules allow execution of the given skill manifest."""
        for rule in self._rules:
            if not rule(manifest):
                return False
        # Ensure the capability manager knows the required capabilities
        await self.capability_manager.check_capability(manifest.required_capabilities)
        return True
