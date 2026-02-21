"""
Formal Plan Model for Deterministic Planning
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, UTC
import hashlib
import json


@dataclass(frozen=True)
class PlanStep:
    """Immutable plan step"""
    step_id: str
    action: str
    required_capabilities: Set[str]
    parameters: Dict[str, Any]
    order: int
    protocol_version: str = "1.0"
    
    def to_canonical(self) -> str:
        """Canonical serialization"""
        data = {
            "step_id": self.step_id,
            "action": self.action,
            "required_capabilities": sorted(list(self.required_capabilities)),
            "parameters": self.parameters,
            "order": self.order,
            "protocol_version": self.protocol_version
        }
        return json.dumps(data, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True)
class Plan:
    """Immutable deterministic plan"""
    id: str
    task_id: str
    steps: List[PlanStep]
    required_capabilities: Set[str]
    policy_hash: str
    execution_seed: int
    created_at: str
    protocol_version: str = "1.0"
    
    def compute_deterministic_hash(self) -> str:
        """Compute deterministic hash of plan"""
        data = {
            "id": self.id,
            "task_id": self.task_id,
            "steps": [step.to_canonical() for step in sorted(self.steps, key=lambda s: s.order)],
            "required_capabilities": sorted(list(self.required_capabilities)),
            "policy_hash": self.policy_hash,
            "execution_seed": self.execution_seed,
            "protocol_version": self.protocol_version
        }
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def get_step_count(self) -> int:
        """Get number of steps"""
        return len(self.steps)
    
    def get_all_capabilities(self) -> Set[str]:
        """Get all required capabilities"""
        caps = set(self.required_capabilities)
        for step in self.steps:
            caps.update(step.required_capabilities)
        return caps


@dataclass
class PlanBuilder:
    """Builder for creating plans deterministically"""
    task_id: str
    execution_seed: int
    policy_hash: str
    protocol_version: str = "1.0"
    
    def __init__(self, task_id: str, execution_seed: int, policy_hash: str):
        self.task_id = task_id
        self.execution_seed = execution_seed
        self.policy_hash = policy_hash
        self._steps: List[PlanStep] = []
        self._capabilities: Set[str] = set()
    
    def add_step(self, action: str, capabilities: Set[str], parameters: Dict[str, Any] = None) -> 'PlanBuilder':
        """Add a step to the plan"""
        step_id = hashlib.sha256(
            f"{self.task_id}:{len(self._steps)}:{action}".encode()
        ).hexdigest()[:16]
        
        step = PlanStep(
            step_id=step_id,
            action=action,
            required_capabilities=frozenset(capabilities),
            parameters=parameters or {},
            order=len(self._steps)
        )
        
        self._steps.append(step)
        self._capabilities.update(capabilities)
        return self
    
    def build(self) -> Plan:
        """Build the immutable plan"""
        plan_id = hashlib.sha256(
            f"{self.task_id}:{self.execution_seed}:{self.policy_hash}".encode()
        ).hexdigest()[:16]
        
        return Plan(
            id=plan_id,
            task_id=self.task_id,
 steps=tuple(self._steps),
            required_capabilities=frozenset(self._capabilities),
            policy_hash=self.policy_hash,
            execution_seed=self.execution_seed,
            created_at=datetime.now(UTC).isoformat()
        )
