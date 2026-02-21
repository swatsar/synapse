"""
Deterministic Scheduler for Synapse Control Plane.
Provides deterministic task distribution across nodes.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import hashlib
import json

PROTOCOL_VERSION: str = "1.0"


@dataclass
class Task:
    """Task to be scheduled"""
    task_id: str
    required_capabilities: List[str]
    priority: int
    payload: dict
    execution_seed: int
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class ScheduledTask:
    """Task with assigned node"""
    task: Task
    node_id: str
    schedule_hash: str
    protocol_version: str = PROTOCOL_VERSION


class DeterministicScheduler:
    """
    Schedules tasks deterministically across nodes.
    
    Invariants:
    - Same input produces same distribution
    - Capability-aware routing
    - Hash-based decisions
    """
    
    def __init__(self, seed: int = 0):
        self.seed = seed
    
    async def schedule(
        self,
        tasks: List[Task],
        nodes: List[dict]
    ) -> List[ScheduledTask]:
        """
        Schedule tasks across nodes deterministically.
        
        Args:
            tasks: Tasks to schedule
            nodes: Available nodes with capabilities
        
        Returns:
            List of scheduled tasks with node assignments
        """
        # Sort for determinism
        sorted_tasks = sorted(tasks, key=lambda t: t.task_id)
        sorted_nodes = sorted(nodes, key=lambda n: n["node_id"])
        
        scheduled = []
        
        for task in sorted_tasks:
            # Find capable nodes
            capable_nodes = [
                n for n in sorted_nodes
                if self._has_capabilities(n, task.required_capabilities)
            ]
            
            if not capable_nodes:
                continue
            
            # Deterministic node selection based on task hash
            node_index = self._select_node_index(task, len(capable_nodes))
            selected_node = capable_nodes[node_index]
            
            schedule_hash = self._compute_schedule_hash(task, selected_node)
            
            scheduled.append(ScheduledTask(
                task=task,
                node_id=selected_node["node_id"],
                schedule_hash=schedule_hash,
                protocol_version=PROTOCOL_VERSION
            ))
        
        return scheduled
    
    def _has_capabilities(self, node: dict, required: List[str]) -> bool:
        """Check if node has required capabilities"""
        node_caps = set(node.get("capabilities", []))
        return all(cap in node_caps for cap in required)
    
    def _select_node_index(self, task: Task, node_count: int) -> int:
        """Deterministically select node index"""
        # Hash-based selection for determinism
        combined = f"{self.seed}:{task.task_id}:{task.execution_seed}"
        hash_value = int(hashlib.sha256(combined.encode()).hexdigest(), 16)
        return hash_value % node_count
    
    def _compute_schedule_hash(self, task: Task, node: dict) -> str:
        """Compute deterministic schedule hash"""
        schedule_data = {
            "task_id": task.task_id,
            "node_id": node["node_id"],
            "seed": self.seed
        }
        schedule_json = json.dumps(schedule_data, sort_keys=True)
        return hashlib.sha256(schedule_json.encode()).hexdigest()
