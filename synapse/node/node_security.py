"""
Node Security for capability validation
"""

from synapse.governance.issuance import CapabilityIssuer
from synapse.transport.message import CapabilityError

class NodeSecurity:
    """Security layer for execution node"""
    
    def __init__(self, issuer: CapabilityIssuer):
        self.issuer = issuer
    
    def validate_capabilities(self, context) -> bool:
        """Validate capabilities for execution context"""
        if not context.agent_id or not hasattr(context, "capabilities"):
            raise CapabilityError("Missing agent_id or capabilities in context")
        
        # Check if capabilities is empty - no implicit permissions
        if not context.capabilities:
            raise CapabilityError("No capabilities provided - zero implicit permissions")
        
        for capability in context.capabilities:
            if not self.issuer.validate(context.agent_id, capability):
                raise CapabilityError(f"Capability {capability} not valid for agent {context.agent_id}")
        
        return True
    
    def check_required_capabilities(self, workflow, context):
        """Check if all required capabilities are present"""
        required = workflow.required_capabilities if hasattr(workflow, "required_capabilities") else set()
        if not required:
            return True
        
        available = context.capabilities if hasattr(context, "capabilities") else set()
        missing = required - available
        
        if missing:
            raise CapabilityError(f"Missing required capabilities: {missing}")
