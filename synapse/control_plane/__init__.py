PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

PROTOCOL_VERSION: str = "1.0"
"""Control Plane for human-in-the-loop operations."""
from .control import HumanApprovalPipeline, ApprovalRequest, ApprovalResponse

__all__ = ["HumanApprovalPipeline", "ApprovalRequest", "ApprovalResponse"]
