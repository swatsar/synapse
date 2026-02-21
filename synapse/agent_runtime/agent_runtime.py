"""
Secure Agent Runtime
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, UTC
import hashlib
import json
import asyncio

from synapse.planning.plan_model import Plan
from synapse.planning.policy_constrained_planner import PolicyConstrainedPlanner, PlanningConstraints


@dataclass
class AgentResult:
    """Result of agent execution"""
    success: bool
    plan_hash: str
    execution_trace: List[Dict[str, Any]]
    used_capabilities: Set[str]
    deterministic_state_hash: str
    error: Optional[str] = None
    timestamp: str = ""
    protocol_version: str = "1.0"


@dataclass
class AgentContext:
    """Capability-bound context for agent"""
    agent_id: str
    task_id: str
    capabilities: Set[str]
    execution_seed: int
    max_steps: int = 10
    max_time_ms: int = 30000
    protocol_version: str = "1.0"


class AgentRuntime:
    """Secure agent runtime that runs within ExecutionNode"""
    
    def __init__(self, planner: PolicyConstrainedPlanner):
        self.planner = planner
        self._execution_trace: List[Dict[str, Any]] = []
        self._used_capabilities: Set[str] = set()
    
    async def run(self, task: str, context: AgentContext) -> AgentResult:
        """Run agent with capability-bound context"""
        self._execution_trace = []
        self._used_capabilities = set()
        
        # Step 1: Create planning constraints
        constraints = PlanningConstraints(
            allowed_capabilities=context.capabilities,
            max_steps=context.max_steps,
            policy_hash=self.planner.policy_hash
        )
        
        # Step 2: Generate plan
        planning_result = self.planner.generate_plan(
            task_id=context.task_id,
            task_description=task,
            constraints=constraints,
            execution_seed=context.execution_seed
        )
        
        if not planning_result.success:
            return AgentResult(
                success=False,
                plan_hash="",
                execution_trace=self._execution_trace,
                used_capabilities=self._used_capabilities,
                deterministic_state_hash=self._compute_state_hash(),
                error=f"Planning failed: {planning_result.violations}",
                timestamp=datetime.now(UTC).isoformat()
            )
        
        plan = planning_result.plan
        plan_hash = planning_result.plan_hash
        
        # Step 3: Execute plan steps
        try:
            for step in plan.steps:
                # Record execution
                step_result = await self._execute_step(step, context)
                self._execution_trace.append(step_result)
                self._used_capabilities.update(step.required_capabilities)
                
                if not step_result.get("success"):
                    return AgentResult(
                        success=False,
                        plan_hash=plan_hash,
                        execution_trace=self._execution_trace,
                        used_capabilities=self._used_capabilities,
                        deterministic_state_hash=self._compute_state_hash(),
                        error=f"Step {step.step_id} failed",
                        timestamp=datetime.now(UTC).isoformat()
                    )
            
            return AgentResult(
                success=True,
                plan_hash=plan_hash,
                execution_trace=self._execution_trace,
                used_capabilities=self._used_capabilities,
                deterministic_state_hash=self._compute_state_hash(),
                timestamp=datetime.now(UTC).isoformat()
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                plan_hash=plan_hash,
                execution_trace=self._execution_trace,
                used_capabilities=self._used_capabilities,
                deterministic_state_hash=self._compute_state_hash(),
                error=str(e),
                timestamp=datetime.now(UTC).isoformat()
            )
    
    async def _execute_step(self, step, context: AgentContext) -> Dict[str, Any]:
        """Execute a single step"""
        # Check capabilities
        if not step.required_capabilities.issubset(context.capabilities):
            return {
                "step_id": step.step_id,
                "action": step.action,
                "success": False,
                "error": "Missing capabilities",
                "timestamp": datetime.now(UTC).isoformat()
            }
        
        # Simulate execution (in real implementation, would call skills)
        await asyncio.sleep(0.001)  # Minimal delay for async
        
        return {
            "step_id": step.step_id,
            "action": step.action,
            "success": True,
            "timestamp": datetime.now(UTC).isoformat()
        }
    
    def _compute_state_hash(self) -> str:
        """Compute deterministic state hash"""
        data = {
            "trace": [
                {"step_id": t.get("step_id"), "success": t.get("success")}
                for t in self._execution_trace
            ],
            "capabilities": sorted(list(self._used_capabilities))
        }
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
