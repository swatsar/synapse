"""Self-Improvement Engine for continuous optimization.

Phase 11 - Continuous Self-Improvement & Adaptive Governance.
"""
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime, timezone

PROTOCOL_VERSION: str = "1.0"


@dataclass
class ImprovementPlan:
    """Plan for self-improvement action."""
    target: str
    improvement_type: str
    risk_level: int
    seed: int
    cluster_wide: bool = False
    checkpoint_id: Optional[str] = None
    protocol_version: str = "1.0"


@dataclass
class ImprovementResult:
    """Result of self-improvement action."""
    success: bool
    improvement_id: str
    status: str
    approval_required: bool = False
    analysis: Optional[Dict[str, Any]] = None
    bottlenecks: Optional[list] = None
    actions_taken: Optional[list] = None
    cluster_propagated: bool = False
    nodes_affected: int = 0
    rollback_executed: bool = False
    restored_checkpoint_id: Optional[str] = None
    cluster_rollback: bool = False
    error: str = ""
    protocol_version: str = "1.0"


class SelfImprovementEngine:
    """Engine for continuous self-improvement and adaptation."""
    
    def __init__(
        self,
        telemetry: Any,
        resource_manager: Any,
        policy_engine: Any,
        skill_registry: Any,
        rollback_manager: Any = None,
        cluster_manager: Any = None,
        audit_logger: Any = None
    ):
        self.telemetry = telemetry
        self.resource_manager = resource_manager
        self.policy_engine = policy_engine
        self.skill_registry = skill_registry
        self.rollback_manager = rollback_manager
        self.cluster_manager = cluster_manager
        self.audit_logger = audit_logger
        self.protocol_version = PROTOCOL_VERSION
    
    def _generate_id(self, seed: int, target: str, improvement_type: str) -> str:
        """Generate deterministic improvement ID."""
        data = f"{seed}:{target}:{improvement_type}"
        return f"imp-{hashlib.md5(data.encode(), usedforsecurity=False).hexdigest()}"  # nosec B324
    
    async def improve(self, plan: ImprovementPlan) -> ImprovementResult:
        """Execute self-improvement plan."""
        improvement_id = self._generate_id(
            plan.seed, plan.target, plan.improvement_type
        )
        
        # Audit log start
        if self.audit_logger:
            self.audit_logger.record({
                "event": "improvement_started",
                "improvement_id": improvement_id,
                "target": plan.target,
                "type": plan.improvement_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        # Record telemetry event
        if self.telemetry and hasattr(self.telemetry, 'record'):
            try:
                self.telemetry.record("improvement_started", {
                    "improvement_id": improvement_id,
                    "target": plan.target
                })
            except:
                pass
        
        # Check if approval required
        approval_required = False
        if plan.risk_level >= 3:
            approval_required = True
        elif self.policy_engine and hasattr(self.policy_engine, 'requires_approval'):
            approval_required = self.policy_engine.requires_approval(plan.risk_level)
        
        if approval_required:
            return ImprovementResult(
                success=False,
                improvement_id=improvement_id,
                status="pending_approval",
                approval_required=True
            )
        
        # Check resource availability
        if self.resource_manager:
            available = self.resource_manager.get_available()
            if not available:
                return ImprovementResult(
                    success=False,
                    improvement_id=improvement_id,
                    status="failed",
                    error="Insufficient resources for improvement"
                )
        
        # Analyze metrics
        analysis = {}
        if self.telemetry:
            if "cluster" in plan.target:
                analysis = self.telemetry.get_system_metrics()
            elif "skill:" in plan.target:
                skill_name = plan.target.split(":")[1]
                analysis = self.telemetry.get_skill_metrics(skill_name)
            else:
                analysis = self.telemetry.get_system_metrics()
        
        # Detect bottlenecks
        bottlenecks = self._detect_bottlenecks(analysis)
        
        # Generate actions
        actions = self._generate_actions(analysis, bottlenecks, plan)
        
        # Execute improvement
        try:
            # Register improvement if skill registry available
            registered = True
            if self.skill_registry and "skill:" in plan.target:
                # Create a simple object instead of MagicMock
                class SimpleSkill:
                    def __init__(self, name, risk_level):
                        self.name = name
                        self.risk_level = risk_level
                
                skill = SimpleSkill(f"improved_{plan.target}", plan.risk_level)
                registered = await self.skill_registry.register(skill)
            
            if not registered:
                # Trigger rollback
                rollback_executed = False
                restored_checkpoint = None
                cluster_rollback = False
                nodes_affected = 0
                
                if self.rollback_manager:
                    checkpoint_id = plan.checkpoint_id
                    if not checkpoint_id:
                        checkpoint_id = await self.rollback_manager.create_checkpoint(
                            agent_id="self_improvement",
                            session_id=improvement_id
                        )
                    
                    # Create simple rollback request
                    class RollbackRequest:
                        def __init__(self, cp_id):
                            self.checkpoint_id = cp_id
                    
                    rollback_result = await self.rollback_manager.execute_rollback(
                        RollbackRequest(checkpoint_id)
                    )
                    rollback_executed = rollback_result.success if hasattr(rollback_result, 'success') else True
                    restored_checkpoint = checkpoint_id
                
                if plan.cluster_wide and self.cluster_manager:
                    cluster_result = await self.cluster_manager.rollback_all()
                    cluster_rollback = cluster_result.get("success", False)
                    nodes_affected = cluster_result.get("nodes_rolled_back", 0)
                
                # Record telemetry
                if self.telemetry and hasattr(self.telemetry, 'record'):
                    try:
                        self.telemetry.record("improvement_failed", {
                            "improvement_id": improvement_id,
                            "rollback_executed": rollback_executed
                        })
                    except:
                        pass
                
                return ImprovementResult(
                    success=False,
                    improvement_id=improvement_id,
                    status="failed",
                    analysis=analysis,
                    bottlenecks=bottlenecks,
                    actions_taken=actions,
                    rollback_executed=rollback_executed,
                    restored_checkpoint_id=restored_checkpoint,
                    cluster_rollback=cluster_rollback,
                    nodes_affected=nodes_affected,
                    error="Registration failed"
                )
            
            # Cluster propagation
            cluster_propagated = False
            nodes_affected = 0
            
            if plan.cluster_wide and self.cluster_manager:
                cluster_result = await self.cluster_manager.broadcast_improvement(
                    improvement_id, actions
                )
                cluster_propagated = cluster_result.get("success", False)
                nodes_affected = cluster_result.get("nodes_updated", 0)
            
            # Record telemetry completion
            if self.telemetry and hasattr(self.telemetry, 'record'):
                try:
                    self.telemetry.record("improvement_completed", {
                        "improvement_id": improvement_id,
                        "cluster_propagated": cluster_propagated
                    })
                except:
                    pass
            
            # Audit log completion
            if self.audit_logger:
                self.audit_logger.record({
                    "event": "improvement_completed",
                    "improvement_id": improvement_id,
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            return ImprovementResult(
                success=True,
                improvement_id=improvement_id,
                status="completed",
                analysis=analysis,
                bottlenecks=bottlenecks,
                actions_taken=actions,
                cluster_propagated=cluster_propagated,
                nodes_affected=nodes_affected
            )
            
        except Exception as e:
            # Trigger rollback on exception
            rollback_executed = False
            restored_checkpoint = None
            cluster_rollback = False
            nodes_affected = 0
            
            if self.rollback_manager:
                checkpoint_id = plan.checkpoint_id
                if not checkpoint_id:
                    checkpoint_id = await self.rollback_manager.create_checkpoint(
                        agent_id="self_improvement",
                        session_id=improvement_id
                    )
                
                class RollbackRequest:
                    def __init__(self, cp_id):
                        self.checkpoint_id = cp_id
                
                rollback_result = await self.rollback_manager.execute_rollback(
                    RollbackRequest(checkpoint_id)
                )
                rollback_executed = rollback_result.success if hasattr(rollback_result, 'success') else True
                restored_checkpoint = checkpoint_id
            
            if plan.cluster_wide and self.cluster_manager:
                cluster_result = await self.cluster_manager.rollback_all()
                cluster_rollback = cluster_result.get("success", False)
                nodes_affected = cluster_result.get("nodes_rolled_back", 0)
            
            return ImprovementResult(
                success=False,
                improvement_id=improvement_id,
                status="failed",
                analysis=analysis,
                bottlenecks=bottlenecks,
                rollback_executed=rollback_executed,
                restored_checkpoint_id=restored_checkpoint,
                cluster_rollback=cluster_rollback,
                nodes_affected=nodes_affected,
                error=str(e)
            )
    
    def _detect_bottlenecks(self, analysis: Dict[str, Any]) -> list:
        """Detect performance bottlenecks from analysis."""
        bottlenecks = []
        
        if not analysis:
            return bottlenecks
        
        # Check success rate
        success_rate = analysis.get("success_rate", 1.0)
        if success_rate < 0.8:
            bottlenecks.append({
                "type": "low_success_rate",
                "value": success_rate,
                "threshold": 0.8
            })
        
        # Check latency
        latency = analysis.get("avg_latency_ms", 0)
        if latency > 300:
            bottlenecks.append({
                "type": "high_latency",
                "value": latency,
                "threshold": 300
            })
        
        # Check resource utilization
        resource_util = analysis.get("resource_utilization", {})
        if resource_util.get("cpu", 0) > 80:
            bottlenecks.append({
                "type": "high_cpu",
                "value": resource_util["cpu"],
                "threshold": 80
            })
        
        # Check failure rate
        failure_rate = analysis.get("failure_rate", 0)
        if failure_rate > 0.1:
            bottlenecks.append({
                "type": "high_failure_rate",
                "value": failure_rate,
                "threshold": 0.1
            })
        
        return bottlenecks
    
    def _generate_actions(
        self,
        analysis: Dict[str, Any],
        bottlenecks: list,
        plan: ImprovementPlan
    ) -> list:
        """Generate improvement actions based on analysis."""
        actions = []
        
        for bottleneck in bottlenecks:
            if bottleneck["type"] == "low_success_rate":
                actions.append({
                    "action": "optimize_skill",
                    "target": plan.target,
                    "improvement": "increase_success_rate"
                })
            elif bottleneck["type"] == "high_latency":
                actions.append({
                    "action": "optimize_performance",
                    "target": plan.target,
                    "improvement": "reduce_latency"
                })
            elif bottleneck["type"] == "high_cpu":
                actions.append({
                    "action": "adjust_resources",
                    "target": plan.target,
                    "improvement": "reduce_cpu_usage"
                })
            elif bottleneck["type"] == "high_failure_rate":
                actions.append({
                    "action": "improve_reliability",
                    "target": plan.target,
                    "improvement": "reduce_failures"
                })
        
        return actions
