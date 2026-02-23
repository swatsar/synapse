"""Adaptive Policy Manager for dynamic policy updates.

Phase 11 - Continuous Self-Improvement & Adaptive Governance.
"""
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime, timezone

PROTOCOL_VERSION: str = "1.0"


@dataclass
class PolicyUpdate:
    """Policy update request."""
    policy_name: str
    updates: Dict[str, Any]
    reason: str
    risk_level: int
    seed: int
    cluster_wide: bool = False
    protocol_version: str = "1.0"


@dataclass
class PolicyUpdateResult:
    """Result of policy update."""
    success: bool
    update_id: str
    policy_name: str
    status: str
    approval_required: bool = False
    cluster_propagated: bool = False
    nodes_updated: int = 0
    error: str = ""
    protocol_version: str = "1.0"


class AdaptivePolicyManager:
    """Manager for dynamic policy updates."""
    
    def __init__(
        self,
        telemetry: Any,
        audit_logger: Any = None,
        cluster_manager: Any = None,
        policy_engine: Any = None
    ):
        self.telemetry = telemetry
        self.audit_logger = audit_logger
        self.cluster_manager = cluster_manager
        self.policy_engine = policy_engine
        self.policies: Dict[str, Dict[str, Any]] = {}
        self.protocol_version = PROTOCOL_VERSION
    
    def _generate_id(self, seed: int, policy_name: str) -> str:
        """Generate deterministic update ID."""
        data = f"{seed}:{policy_name}"
        return f"pol-{hashlib.md5(data.encode(), usedforsecurity=False).hexdigest()}"  # nosec B324
    
    async def apply_update(self, update: PolicyUpdate) -> PolicyUpdateResult:
        """Apply a policy update."""
        update_id = self._generate_id(update.seed, update.policy_name)
        
        # Audit log start
        if self.audit_logger:
            self.audit_logger.record({
                "event": "policy_update_started",
                "update_id": update_id,
                "policy_name": update.policy_name,
                "reason": update.reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        # Check if approval required
        approval_required = update.risk_level >= 3
        
        if approval_required:
            return PolicyUpdateResult(
                success=False,
                update_id=update_id,
                policy_name=update.policy_name,
                status="pending_approval",
                approval_required=True
            )
        
        try:
            # Apply policy update locally
            if update.policy_name not in self.policies:
                self.policies[update.policy_name] = {}
            
            self.policies[update.policy_name].update(update.updates)
            
            # Update policy engine if available
            if self.policy_engine and hasattr(self.policy_engine, 'update_policy'):
                await self.policy_engine.update_policy(update.updates)
            
            # Cluster propagation
            cluster_propagated = False
            nodes_updated = 0
            
            if update.cluster_wide and self.cluster_manager:
                cluster_result = await self.cluster_manager.broadcast_policy(
                    update.policy_name,
                    update.updates
                )
                cluster_propagated = cluster_result.get("success", False)
                nodes_updated = cluster_result.get("nodes_updated", 0)
            
            # Audit log completion
            if self.audit_logger:
                self.audit_logger.record({
                    "event": "policy_update_completed",
                    "update_id": update_id,
                    "policy_name": update.policy_name,
                    "success": True,
                    "cluster_propagated": cluster_propagated,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            return PolicyUpdateResult(
                success=True,
                update_id=update_id,
                policy_name=update.policy_name,
                status="applied",
                cluster_propagated=cluster_propagated,
                nodes_updated=nodes_updated
            )
            
        except Exception as e:
            # Audit log failure
            if self.audit_logger:
                self.audit_logger.record({
                    "event": "policy_update_failed",
                    "update_id": update_id,
                    "policy_name": update.policy_name,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            return PolicyUpdateResult(
                success=False,
                update_id=update_id,
                policy_name=update.policy_name,
                status="failed",
                error=str(e)
            )
    
    def get_policy(self, policy_name: str) -> Optional[Dict[str, Any]]:
        """Get current policy state."""
        return self.policies.get(policy_name)
    
    def get_all_policies(self) -> Dict[str, Dict[str, Any]]:
        """Get all policies."""
        return self.policies.copy()
    
    async def analyze_and_suggest(self) -> Dict[str, Any]:
        """Analyze telemetry and suggest policy updates."""
        suggestions = []
        
        if self.telemetry:
            metrics = self.telemetry.get_system_metrics()
            
            # Suggest resource limit adjustments
            resource_util = metrics.get("resource_utilization", {})
            if resource_util.get("cpu", 0) > 70:
                suggestions.append({
                    "policy": "resource_limits",
                    "update": {"max_cpu": 90},
                    "reason": "High CPU utilization detected",
                    "risk_level": 1
                })
            
            # Suggest failure rate adjustments
            failure_rate = metrics.get("failure_rate", 0)
            if failure_rate > 0.05:
                suggestions.append({
                    "policy": "retry_policy",
                    "update": {"max_retries": 5},
                    "reason": "Elevated failure rate detected",
                    "risk_level": 1
                })
        
        return {
            "suggestions": suggestions,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
