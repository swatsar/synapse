"""
Deterministic Planner - No Randomness Allowed
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Set
import hashlib
import json

from synapse.planning.plan_model import Plan, PlanStep, PlanBuilder


@dataclass
class PlanningInput:
    """Deterministic input for planning"""
    task: str
    capabilities: Set[str]
    constraints: Dict[str, Any]
    execution_seed: int
    policy_hash: str
    protocol_version: str = "1.0"


class DeterministicPlanner:
    """Planner that produces identical output for identical input"""
    
    def __init__(self):
        self._plan_cache: Dict[str, Plan] = {}
    
    def generate_plan(
        self,
        task: str,
        constraints: Dict[str, Any],
        capabilities: Set[str],
        seed: int
    ) -> Plan:
        """Generate deterministic plan"""
        # Create cache key
        cache_key = self._compute_cache_key(task, constraints, capabilities, seed)
        
        # Return cached plan if exists
        if cache_key in self._plan_cache:
            return self._plan_cache[cache_key]
        
        # Generate plan deterministically
        steps = self._generate_steps(task, capabilities, seed)
        
        # Build plan
        builder = PlanBuilder(
            task_id=self._compute_task_id(task, seed),
            execution_seed=seed,
            policy_hash=constraints.get("policy_hash", "")
        )
        
        for step in steps:
            builder.add_step(
                action=step["action"],
                capabilities=step["capabilities"],
                parameters=step.get("parameters", {})
            )
        
        plan = builder.build()
        
        # Cache the plan
        self._plan_cache[cache_key] = plan
        
        return plan
    
    def _generate_steps(
        self,
        task: str,
        capabilities: Set[str],
        seed: int
    ) -> List[Dict[str, Any]]:
        """Generate steps deterministically based on task and seed"""
        steps = []
        
        # Use seed for deterministic step generation
        hash_input = f"{task}:{seed}"
        hash_val = hashlib.sha256(hash_input.encode()).hexdigest()
        
        # Parse task keywords
        task_lower = task.lower()
        
        # Generate steps based on keywords and capabilities
        if "read" in task_lower and "fs:read" in capabilities:
            steps.append({
                "action": "read",
                "capabilities": {"fs:read"},
                "parameters": {"path": "/workspace"}
            })
        
        if "write" in task_lower and "fs:write" in capabilities:
            steps.append({
                "action": "write",
                "capabilities": {"fs:write"},
                "parameters": {"path": "/workspace"}
            })
        
        if "execute" in task_lower and "os:process" in capabilities:
            steps.append({
                "action": "execute",
                "capabilities": {"os:process"},
                "parameters": {"command": "echo"}
            })
        
        if "search" in task_lower and "net:http" in capabilities:
            steps.append({
                "action": "search",
                "capabilities": {"net:http"},
                "parameters": {"query": ""}
            })
        
        # Default step if none matched
        if not steps:
            steps.append({
                "action": "analyze",
                "capabilities": set(),
                "parameters": {}
            })
        
        return steps
    
    def _compute_cache_key(
        self,
        task: str,
        constraints: Dict[str, Any],
        capabilities: Set[str],
        seed: int
    ) -> str:
        """Compute deterministic cache key"""
        data = {
            "task": task,
            "constraints": constraints,
            "capabilities": sorted(list(capabilities)),
            "seed": seed
        }
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def _compute_task_id(self, task: str, seed: int) -> str:
        """Compute deterministic task ID"""
        data = f"{task}:{seed}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def verify_determinism(self, plan1: Plan, plan2: Plan) -> bool:
        """Verify two plans are identical"""
        return plan1.compute_deterministic_hash() == plan2.compute_deterministic_hash()
