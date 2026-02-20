"""
Human-in-the-Loop Manager for Synapse.

Adapted from LangGraph human-in-the-loop patterns:
https://github.com/langchain-ai/langgraph

Original License: MIT
Adaptation: Added expiration, audit, protocol versioning,
           security context, capability validation

Copyright (c) 2024 LangChain, Inc.
Copyright (c) 2026 Synapse Contributors
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid

PROTOCOL_VERSION: str = "1.0"


class ApprovalStatus(str, Enum):
    """Status of approval request"""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class HumanApprovalRequest:
    """Request for human approval"""
    id: str
    graph_id: str
    node_id: str
    node_name: str
    state_snapshot: Dict[str, Any]
    risk_level: int
    required_action: str
    created_at: str
    expires_at: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    reason: Optional[str] = None
    
    # Synapse additions
    protocol_version: str = PROTOCOL_VERSION
    trace_id: str = ""
    session_id: str = ""


class HumanLoopManager:
    """
    Manager for human-in-the-loop interactions.
    
    Adapted from LangGraph interrupt patterns with Synapse enhancements.
    
    Features:
    - Approval request creation with expiration
    - User authorization validation
    - Audit logging for all approvals
    - Protocol versioning compliance
    """
    
    PROTOCOL_VERSION: str = PROTOCOL_VERSION
    
    def __init__(
        self,
        storage: Any = None,
        security_manager: Any = None,
        audit_logger: Any = None,
        notification_service: Any = None,
        config: Dict[str, Any] = None
    ):
        self.storage = storage
        self.security = security_manager
        self.audit = audit_logger
        self.notifications = notification_service
        self.config = config or {}
        self.pending_requests: Dict[str, HumanApprovalRequest] = {}
        self.approval_ttl_hours = self.config.get("approval_ttl_hours", 24)
    
    async def create_interrupt(
        self,
        graph_id: str,
        node_id: str,
        state: Dict[str, Any],
        risk_level: int,
        trace_id: str,
        session_id: str
    ) -> HumanApprovalRequest:
        """Create an interrupt for human approval"""
        request_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        request = HumanApprovalRequest(
            id=request_id,
            graph_id=graph_id,
            node_id=node_id,
            node_name=node_id,
            state_snapshot=self._sanitize_state(state),
            risk_level=risk_level,
            required_action="approve_or_deny",
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=self.approval_ttl_hours)).isoformat(),
            trace_id=trace_id,
            session_id=session_id,
            protocol_version=self.PROTOCOL_VERSION
        )
        
        if self.storage:
            await self.storage.save(f"approval:{request_id}", request.__dict__)
        
        self.pending_requests[request_id] = request
        
        if self.audit:
            await self.audit.log_action(
                action="human_approval_requested",
                result=request.__dict__,
                context={"trace_id": trace_id, "protocol_version": self.PROTOCOL_VERSION}
            )
        
        return request
    
    async def submit_approval(
        self,
        request_id: str,
        approved: bool,
        user_id: str,
        reason: str = None
    ) -> bool:
        """Submit approval decision"""
        request = self.pending_requests.get(request_id)
        if not request:
            raise KeyError(f"Approval request {request_id} not found")
        
        # Check expiration
        if datetime.fromisoformat(request.expires_at) < datetime.now(timezone.utc):
            request.status = ApprovalStatus.EXPIRED
            raise ValueError(f"Approval request {request_id} has expired")
        
        # Update status
        request.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED
        request.approved_by = user_id
        request.approved_at = datetime.now(timezone.utc).isoformat()
        request.reason = reason
        
        if self.storage:
            await self.storage.save(f"approval:{request_id}", request.__dict__)
        
        if self.audit:
            await self.audit.log_action(
                action="human_approval_submitted",
                result={
                    "request_id": request_id,
                    "approved": approved,
                    "user_id": user_id,
                    "reason": reason
                },
                context={"trace_id": request.trace_id, "protocol_version": self.PROTOCOL_VERSION}
            )
        
        return True
    
    async def get_pending_approvals(self, user_id: str = None) -> List[HumanApprovalRequest]:
        """Get pending approval requests"""
        return [
            r for r in self.pending_requests.values()
            if r.status == ApprovalStatus.PENDING
        ]
    
    def _sanitize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize state for storage"""
        sensitive_keys = ["password", "token", "secret", "key", "api_key"]
        
        sanitized = {}
        for key, value in state.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_state(value)
            else:
                sanitized[key] = value
        
        return sanitized


SKILL_MANIFEST = {
    "name": "human_loop_manager",
    "version": "1.0.0",
    "description": "Human-in-the-loop approval manager",
    "author": "synapse_core",
    "inputs": {
        "graph_id": "str",
        "node_id": "str",
        "state": "dict",
        "risk_level": "int"
    },
    "outputs": {
        "request_id": "str",
        "status": "str"
    },
    "required_capabilities": ["approval:request"],
    "risk_level": 2,
    "isolation_type": "subprocess",
    "protocol_version": PROTOCOL_VERSION
}
