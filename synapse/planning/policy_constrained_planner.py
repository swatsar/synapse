"""
Policy-Constrained Planning Engine
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, UTC
import hashlib
import json

from synapse.planning.plan_model import Plan, PlanStep, PlanBuilder
from synapse.planning.plan_hashing import PlanHasher


@dataclass
class PlanningConstraints:
    """Constraints for deterministic planning"""
    allowed_capabilities: Set[str]
    max_steps: int = 10
    max_depth: int = 5
    policy_hash: str = ""
    protocol_version: str = "1.0"


@dataclass
class PlanningResult:
    """Result of planning attempt"""
    success: bool
    plan: Optional[Plan]
    violations: List[str]
    plan_hash: Optional[str]
    timestamp: str
    protocol_version: str = "1.0"


class PolicyConstrainedPlanner:
    """Planner that enforces policy constraints"""
    
    def __init__(self, policy_rules: Dict[str, Any]):
        self.policy_rules = policy_rules
        self.policy_hash = PlanHasher.compute_policy_hash(policy_rules)
    
    def generate_plan(
        self,
        task_id: str,
        task_description: str,
        constraints: PlanningConstraints,
        execution_seed: int
    ) -> PlanningResult:
        """Generate a deterministic plan within constraints"""
        violations = []
        
        # Step 1: Parse task into candidate steps
        candidate_steps = self._parse_task(task_description, execution_seed)
        
        # Step 2: Filter by capabilities
        filtered_steps = []
        for step in candidate_steps:
            step_caps = step.get("capabilities", set())
            if step_caps.issubset(constraints.allowed_capabilities):
                filtered_steps.append(step)
            else:
                missing = step_caps - constraints.allowed_capabilities
                violations.append(f"Step '{step.get('action')}' requires missing capabilities: {missing}")
        
        # Step 3: Validate against policy
        validated_steps = []
        for step in filtered_steps:
            if self._validate_step_policy(step):
                validated_steps.append(step)
            else:
                violations.append(f"Step '{step.get('action')}' violates policy")
        
        # Step 4: Check max steps
        if len(validated_steps) > constraints.max_steps:
            validated_steps = validated_steps[:constraints.max_steps]
            violations.append(f"Plan truncated to {constraints.max_steps} steps")
        
        # Step 5: Build plan if valid
        if not validated_steps:
            return PlanningResult(
                success=False,
                plan=None,
                violations=violations,
                plan_hash=None,
                timestamp=datetime.now(UTC).isoformat()
            )
        
        # Build deterministic plan
        builder = PlanBuilder(
            task_id=task_id,
            execution_seed=execution_seed,
            policy_hash=self.policy_hash
        )
        
        for i, step in enumerate(validated_steps):
            builder.add_step(
                action=step.get("action"),
                capabilities=set(step.get("capabilities", [])),
                parameters=step.get("parameters", {})
            )
        
        plan = builder.build()
        plan_hash = plan.compute_deterministic_hash()
        
        return PlanningResult(
            success=True,
            plan=plan,
            violations=violations,
            plan_hash=plan_hash,
            timestamp=datetime.now(UTC).isoformat()
        )
    
    def _parse_task(self, task_description: str, seed: int) -> List[Dict[str, Any]]:
        """Parse task into candidate steps deterministically"""
        # Deterministic parsing based on seed
        import hashlib
        
        # Create deterministic step generation
        hash_input = f"{task_description}:{seed}"
        hash_val = hashlib.sha256(hash_input.encode()).hexdigest()
        
        # Generate steps based on task keywords
        steps = []
        task_lower = task_description.lower()
        
        if "read" in task_lower or "get" in task_lower:
            steps.append({
                "action": "read",
                "capabilities": {"fs:read"},
                "parameters": {"path": "/workspace"},
                "order": len(steps)
            })
        
        if "write" in task_lower or "save" in task_lower:
            steps.append({
                "action": "write",
                "capabilities": {"fs:write"},
                "parameters": {"path": "/workspace"},
                "order": len(steps)
            })
        
        if "execute" in task_lower or "run" in task_lower:
            steps.append({
                "action": "execute",
                "capabilities": {"os:process"},
                "parameters": {"command": "echo"},
                "order": len(steps)
            })
        
        if "search" in task_lower or "find" in task_lower:
            steps.append({
                "action": "search",
                "capabilities": {"net:http"},
                "parameters": {"query": ""},
                "order": len(steps)
            })
        
        # Default step if none matched
        if not steps:
            steps.append({
                "action": "analyze",
                "capabilities": set(),
                "parameters": {},
                "order": 0
            })
        
        return steps
    
    def _validate_step_policy(self, step: Dict[str, Any]) -> bool:
        """Validate step against policy rules"""
        # Check forbidden actions
        forbidden = self.policy_rules.get("forbidden_actions", [])
        if step.get("action") in forbidden:
            return False
        
        # Check required capabilities are allowed
        required_caps = set(step.get("capabilities", set()))
        allowed_caps = set(self.policy_rules.get("allowed_capabilities", []))
        
        if allowed_caps and not required_caps.issubset(allowed_caps):
            return False
        
        return True
    
    def validate_plan(self, plan: Plan, capabilities: Set[str]) -> bool:
        """Validate an existing plan against capabilities"""
        plan_caps = plan.get_all_capabilities()
        return plan_caps.issubset(capabilities)
