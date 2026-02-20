"""Human-in-the-loop Control Layer.

Implements SYSTEM_SPEC_v3.1 Phase 9 - Human Approval Pipeline.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone


PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Risk level threshold for approval
APPROVAL_RISK_THRESHOLD = 3


@dataclass
class ApprovalRequest:
    """Request for human approval."""
    task_id: str
    task_name: str
    risk_level: int
    trace_id: str
    timestamp: str
    protocol_version: str = "1.0"


@dataclass
class ApprovalResponse:
    """Response from human approval."""
    approved: bool
    task_id: str
    approver: str
    timestamp: str
    protocol_version: str = "1.0"


class HumanApprovalPipeline:
    """Pipeline for human-in-the-loop approval.
    
    Responsibilities:
    - Route high-risk tasks to approval queue
    - Send approval requests via connectors
    - Maintain deterministic ordering
    - Log all approval decisions
    """
    
    protocol_version: str = PROTOCOL_VERSION
    
    def __init__(
        self,
        connector_runtime: Any = None,
        audit_logger: Any = None,
        policy_engine: Any = None
    ):
        self.connector_runtime = connector_runtime
        self.audit_logger = audit_logger
        self.policy_engine = policy_engine
        self._approval_queue: List[ApprovalRequest] = []
    
    async def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task through the approval pipeline.
        
        Args:
            task: Task to process
            
        Returns:
            Processing result with status
        """
        risk_level = task.get("risk_level", 1)
        trace_id = task.get("trace_id", "unknown")
        
        # Check if approval is required
        requires_approval = self._requires_approval(risk_level)
        
        # Log processing start
        if self.audit_logger:
            self.audit_logger.record({
                "event": "approval_pipeline_started",
                "task": task.get("name"),
                "risk_level": risk_level,
                "requires_approval": requires_approval,
                "trace_id": trace_id,
                "protocol_version": self.protocol_version
            })
        
        if requires_approval:
            # Create approval request
            request = ApprovalRequest(
                task_id=task.get("id", "unknown"),
                task_name=task.get("name", "unknown"),
                risk_level=risk_level,
                trace_id=trace_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            # Add to queue
            self._approval_queue.append(request)
            
            # Send approval request via connector
            if self.connector_runtime:
                await self.connector_runtime.send_approval_request(request.__dict__)
            
            return {
                "status": "pending_approval",
                "task_id": request.task_id,
                "trace_id": trace_id,
                "protocol_version": self.protocol_version
            }
        
        # No approval required
        return {
            "status": "approved",
            "task_id": task.get("id", "unknown"),
            "trace_id": trace_id,
            "protocol_version": self.protocol_version
        }
    
    def _requires_approval(self, risk_level: int) -> bool:
        """Check if task requires approval.
        
        Args:
            risk_level: Risk level of task
            
        Returns:
            True if approval is required
        """
        if self.policy_engine:
            return self.policy_engine.requires_approval(risk_level)
        
        return risk_level >= APPROVAL_RISK_THRESHOLD
    
    def order_queue(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Order approval queue deterministically.
        
        Args:
            tasks: List of tasks to order
            
        Returns:
            Ordered list of tasks
        """
        # Sort by timestamp for deterministic ordering
        return sorted(tasks, key=lambda t: t.get("timestamp", ""))
    
    async def wait_for_approval(
        self,
        task_id: str,
        timeout_seconds: int = 300
    ) -> ApprovalResponse:
        """Wait for human approval response.
        
        Args:
            task_id: Task to wait for
            timeout_seconds: Timeout in seconds
            
        Returns:
            Approval response
        """
        if self.connector_runtime:
            response = await self.connector_runtime.wait_for_response(task_id)
            return ApprovalResponse(
                approved=response.get("approved", False),
                task_id=task_id,
                approver=response.get("approver", "unknown"),
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        # Default approval for testing
        return ApprovalResponse(
            approved=True,
            task_id=task_id,
            approver="system",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
