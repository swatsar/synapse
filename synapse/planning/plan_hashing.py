"""
Deterministic Plan Hashing
"""

from typing import Dict, List, Any, Set
import hashlib
import json


class PlanHasher:
    """Deterministic plan hashing"""
    
    @staticmethod
    def compute_plan_hash(
        task_id: str,
        steps: List[Dict[str, Any]],
        capabilities: Set[str],
        policy_hash: str,
        execution_seed: int
    ) -> str:
        """Compute deterministic hash of plan components"""
        data = {
            "task_id": task_id,
            "steps": [
                {
                    "action": step.get("action"),
                    "capabilities": sorted(list(step.get("capabilities", set()))),
                    "parameters": step.get("parameters", {}),
                    "order": step.get("order", 0)
                }
                for step in sorted(steps, key=lambda s: s.get("order", 0))
            ],
            "capabilities": sorted(list(capabilities)),
            "policy_hash": policy_hash,
            "execution_seed": execution_seed,
            "protocol_version": "1.0"
        }
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    @staticmethod
    def compute_step_hash(step_id: str, action: str, parameters: Dict[str, Any]) -> str:
        """Compute deterministic hash of a single step"""
        data = {
            "step_id": step_id,
            "action": action,
            "parameters": parameters,
            "protocol_version": "1.0"
        }
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    @staticmethod
    def compute_policy_hash(policy_rules: Dict[str, Any]) -> str:
        """Compute deterministic hash of policy rules"""
        canonical = json.dumps(policy_rules, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    @staticmethod
    def verify_plan_integrity(plan_hash: str, plan_data: Dict[str, Any]) -> bool:
        """Verify plan integrity against hash"""
        computed = PlanHasher.compute_plan_hash(
            task_id=plan_data.get("task_id"),
            steps=plan_data.get("steps", []),
            capabilities=set(plan_data.get("capabilities", [])),
            policy_hash=plan_data.get("policy_hash"),
            execution_seed=plan_data.get("execution_seed")
        )
        return computed == plan_hash
