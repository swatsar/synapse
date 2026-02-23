"""Governor Agent for adaptive governance.

Phase 11 - Continuous Self-Improvement & Adaptive Governance.
"""
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

PROTOCOL_VERSION: str = "1.0"


@dataclass
class GovernanceAction:
    """Action to be taken by governor."""
    action_type: str
    target: str
    parameters: Dict[str, Any]
    risk_level: int
    seed: int
    protocol_version: str = "1.0"


@dataclass
class ActionResult:
    """Result of governance action."""
    success: bool
    action_id: str
    action_type: str
    approval_required: bool = False
    status: str = "completed"
    error: str = ""
    protocol_version: str = "1.0"


@dataclass
class GovernanceDecision:
    """Decision made by governor based on analysis."""
    analysis: Dict[str, Any]
    bottlenecks: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    feedback: Dict[str, Any]
    protocol_version: str = "1.0"


class GovernorAgent:
    """Agent for adaptive governance and policy management."""
    
    def __init__(
        self,
        telemetry: Any,
        policy_engine: Any,
        resource_manager: Any,
        audit_logger: Any = None,
        cluster_manager: Any = None
    ):
        self.telemetry = telemetry
        self.policy_engine = policy_engine
        self.resource_manager = resource_manager
        self.audit_logger = audit_logger
        self.cluster_manager = cluster_manager
        self.protocol_version = PROTOCOL_VERSION
    
    def _generate_id(self, seed: int, action_type: str, target: str) -> str:
        """Generate deterministic action ID."""
        data = f"{seed}:{action_type}:{target}"
        return f"act-{hashlib.md5(data.encode(), usedforsecurity=False).hexdigest()}"  # nosec B324
    
    async def analyze(self) -> GovernanceDecision:
        """Analyze system metrics and make governance decision."""
        # Audit log
        if self.audit_logger:
            self.audit_logger.record({
                "event": "governance_analysis_started",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        # Get system metrics
        system_metrics = {}
        if self.telemetry:
            system_metrics = self.telemetry.get_system_metrics()
        
        # Get skill metrics
        skill_metrics = {}
        if self.telemetry and hasattr(self.telemetry, 'get_skill_metrics'):
            skill_metrics = self.telemetry.get_skill_metrics()
        
        # Analyze for bottlenecks
        bottlenecks = self._detect_bottlenecks(system_metrics, skill_metrics)
        
        # Generate actions
        actions = self._generate_actions(bottlenecks)
        
        # Create feedback for optimizer
        feedback = self._create_feedback(bottlenecks, actions)
        
        # Audit log completion
        if self.audit_logger:
            self.audit_logger.record({
                "event": "governance_analysis_completed",
                "bottlenecks_count": len(bottlenecks),
                "actions_count": len(actions),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        return GovernanceDecision(
            analysis={
                "system": system_metrics,
                "skills": skill_metrics
            },
            bottlenecks=bottlenecks,
            actions=actions,
            feedback=feedback
        )
    
    async def execute_action(self, action: GovernanceAction) -> ActionResult:
        """Execute a governance action."""
        action_id = self._generate_id(action.seed, action.action_type, action.target)
        
        # Check if approval required
        approval_required = action.risk_level >= 3
        
        if approval_required:
            return ActionResult(
                success=False,
                action_id=action_id,
                action_type=action.action_type,
                approval_required=True,
                status="pending_approval"
            )
        
        # Execute based on action type
        try:
            if action.action_type == "adjust_resource_limit":
                if self.resource_manager:
                    await self.resource_manager.adjust_limits(action.parameters)
            
            elif action.action_type == "change_security_policy":
                if self.policy_engine:
                    await self.policy_engine.update_policy(action.parameters)
            
            elif action.action_type == "optimize_skill":
                # Would integrate with optimizer
                pass
            
            # Audit log
            if self.audit_logger:
                self.audit_logger.record({
                    "event": "governance_action_executed",
                    "action_id": action_id,
                    "action_type": action.action_type,
                    "target": action.target,
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            return ActionResult(
                success=True,
                action_id=action_id,
                action_type=action.action_type,
                status="completed"
            )
            
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=action_id,
                action_type=action.action_type,
                status="failed",
                error=str(e)
            )
    
    def _detect_bottlenecks(
        self,
        system_metrics: Dict[str, Any],
        skill_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect bottlenecks from metrics."""
        bottlenecks = []
        
        # Check system metrics
        if system_metrics:
            # High failure rate
            failure_rate = system_metrics.get("failure_rate", 0)
            if failure_rate > 0.1:
                bottlenecks.append({
                    "type": "high_failure_rate",
                    "source": "system",
                    "value": failure_rate,
                    "threshold": 0.1
                })
            
            # Resource utilization
            resource_util = system_metrics.get("resource_utilization", {})
            if resource_util.get("cpu", 0) > 80:
                bottlenecks.append({
                    "type": "high_cpu",
                    "source": "system",
                    "value": resource_util["cpu"],
                    "threshold": 80
                })
        
        # Check skill metrics
        if skill_metrics:
            for skill_name, metrics in skill_metrics.items():
                if isinstance(metrics, dict):
                    success_rate = metrics.get("success_rate", 1.0)
                    if success_rate < 0.8:
                        bottlenecks.append({
                            "type": "low_success_rate",
                            "source": f"skill:{skill_name}",
                            "value": success_rate,
                            "threshold": 0.8
                        })
                    
                    latency = metrics.get("latency_ms", 0)
                    if latency > 300:
                        bottlenecks.append({
                            "type": "high_latency",
                            "source": f"skill:{skill_name}",
                            "value": latency,
                            "threshold": 300
                        })
        
        return bottlenecks
    
    def _generate_actions(self, bottlenecks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate actions to address bottlenecks."""
        actions = []
        
        for bottleneck in bottlenecks:
            if bottleneck["type"] == "high_failure_rate":
                actions.append({
                    "action_type": "improve_reliability",
                    "target": bottleneck["source"],
                    "parameters": {"focus": "failure_reduction"},
                    "risk_level": 2
                })
            
            elif bottleneck["type"] == "high_cpu":
                actions.append({
                    "action_type": "adjust_resource_limit",
                    "target": bottleneck["source"],
                    "parameters": {"max_cpu": 90},
                    "risk_level": 1
                })
            
            elif bottleneck["type"] == "low_success_rate":
                actions.append({
                    "action_type": "optimize_skill",
                    "target": bottleneck["source"],
                    "parameters": {"focus": "success_rate"},
                    "risk_level": 2
                })
            
            elif bottleneck["type"] == "high_latency":
                actions.append({
                    "action_type": "optimize_skill",
                    "target": bottleneck["source"],
                    "parameters": {"focus": "latency"},
                    "risk_level": 1
                })
        
        return actions
    
    def _create_feedback(
        self,
        bottlenecks: List[Dict[str, Any]],
        actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create feedback for optimizer and policy engine."""
        return {
            "optimizer": {
                "bottlenecks": bottlenecks,
                "suggested_improvements": [a for a in actions if a["action_type"] == "optimize_skill"]
            },
            "policy": {
                "resource_adjustments": [a for a in actions if a["action_type"] == "adjust_resource_limit"],
                "security_changes": [a for a in actions if a["action_type"] == "change_security_policy"]
            }
        }
