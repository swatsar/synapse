"""Dashboard - Minimal control plane UI."""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

PROTOCOL_VERSION: str = "1.0"


@dataclass
class AgentInfo:
    """Agent information for display."""
    id: str
    name: str
    status: str = "idle"
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class ApprovalRequest:
    """Pending approval request."""
    id: str
    action: str
    risk_level: int
    status: str = "pending"
    protocol_version: str = PROTOCOL_VERSION


class Dashboard:
    """Minimal dashboard for system control."""
    protocol_version: str = PROTOCOL_VERSION
    
    def __init__(self, orchestrator=None, capability_manager=None):
        self._orchestrator = orchestrator
        self._capability_manager = capability_manager
        self._agents: List[AgentInfo] = []
        self._approvals: List[ApprovalRequest] = []
        self._logs: List[Dict[str, Any]] = []
    
    def get_cluster_state(self) -> Dict[str, Any]:
        """Get cluster state."""
        return {
            "status": "operational",
            "nodes": 1,
            "protocol_version": PROTOCOL_VERSION
        }
    
    def list_agents(self) -> List[AgentInfo]:
        """List all agents."""
        return self._agents
    
    def add_agent(self, agent: AgentInfo) -> None:
        """Add an agent."""
        self._agents.append(agent)
    
    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Get pending approval requests."""
        return [a for a in self._approvals if a.status == "pending"]
    
    def add_approval_request(self, request: ApprovalRequest) -> None:
        """Add an approval request."""
        self._approvals.append(request)
    
    def approve(self, approval_id: str) -> bool:
        """Approve a request."""
        for approval in self._approvals:
            if approval.id == approval_id:
                approval.status = "approved"
                return True
        return False
    
    def reject(self, approval_id: str) -> bool:
        """Reject a request."""
        for approval in self._approvals:
            if approval.id == approval_id:
                approval.status = "rejected"
                return True
        return False
    
    async def execute_task(self, task: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a task."""
        if self._orchestrator:
            return await self._orchestrator.handle({"task": task, "payload": payload})
        return {"status": "completed", "protocol_version": PROTOCOL_VERSION}
    
    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent logs."""
        return self._logs[-limit:]
    
    def add_log(self, log: Dict[str, Any]) -> None:
        """Add a log entry."""
        log["protocol_version"] = PROTOCOL_VERSION
        self._logs.append(log)
