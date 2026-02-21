PROTOCOL_VERSION: str = "1.0"
"""
Policy engine for validation
"""

from synapse.orchestrator.task_model import Task
from synapse.governance.capability_policy import CapabilityPolicyEngine

class PolicyEngine:
    """Policy engine for task validation"""
    
    def __init__(self, policy_engine: CapabilityPolicyEngine):
        self.policy_engine = policy_engine
    
    def validate_task(self, task: Task) -> bool:
        """Validate task against policies"""
        for cap in task.required_capabilities:
            if not self.policy_engine.validate_capability(cap):
                return False
        return True
