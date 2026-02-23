"""
Phase 7: Cluster Scheduler
Protocol Version: 1.0

Deterministic scheduling across nodes with:
- Deterministic node selection
- Consistent hashing strategy
- Tenant-aware placement
- Schedule reproducibility across cluster
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class ClusterSchedule:
    """Schedule for cluster-wide execution"""
    schedule_id: str
    tenant_id: str
    node_assignments: Dict[str, List[str]]  # node_id -> task_ids
    execution_seed: int
    created_at: str
    protocol_version: str = "1.0"


@dataclass
class Task:
    """Task for scheduling"""
    task_id: str
    action: str
    input: Dict[str, Any]
    priority: int = 0
    protocol_version: str = "1.0"


class ClusterScheduler:
    """
    Deterministic scheduling across nodes.
    
    Provides:
    - Deterministic node selection
    - Consistent hashing strategy
    - Tenant-aware placement
    - Schedule reproducibility across cluster
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    # Default node pool for scheduling
    DEFAULT_NODES = ["node_0", "node_1", "node_2"]
    
    def __init__(self, nodes: List[str] = None):
        self._nodes = nodes or self.DEFAULT_NODES.copy()
        self._schedule_counter = 0
    
    def schedule_cluster_execution(self, tenant_id: str, task: Dict[str, Any]) -> str:
        """
        Schedule execution on a cluster node.
        
        Uses consistent hashing to ensure same tenant+task
        always maps to same node.
        
        Args:
            tenant_id: Tenant identifier
            task: Task specification
            
        Returns:
            node_id: The assigned node identifier
        """
        # Deterministic assignment using consistent hashing
        task_id = task.get("task_id", "default")
        assignment_key = f"{tenant_id}:{task_id}"
        hash_value = hashlib.sha256(assignment_key.encode()).hexdigest()
        
        # Select node based on hash
        node_index = int(hash_value[:8], 16) % len(self._nodes)
        return self._nodes[node_index]
    
    def compute_cluster_schedule_hash(self, schedule: ClusterSchedule) -> str:
        """
        Compute deterministic hash of cluster schedule.
        
        Args:
            schedule: Cluster schedule to hash
            
        Returns:
            str: SHA-256 hash of schedule
        """
        # Canonical serialization
        schedule_state = {
            "schedule_id": schedule.schedule_id,
            "tenant_id": schedule.tenant_id,
            "node_assignments": {
                k: sorted(v) for k, v in sorted(schedule.node_assignments.items())
            },
            "execution_seed": schedule.execution_seed,
            "created_at": schedule.created_at,
            "protocol_version": schedule.protocol_version
        }
        
        canonical = json.dumps(schedule_state, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def create_schedule(self, 
                        tenant_id: str, 
                        tasks: List[Dict[str, Any]],
                        execution_seed: int = None) -> ClusterSchedule:
        """
        Create a cluster schedule for multiple tasks.
        
        Args:
            tenant_id: Tenant identifier
            tasks: List of tasks to schedule
            execution_seed: Optional execution seed
            
        Returns:
            ClusterSchedule: The created schedule
        """
        if execution_seed is None:
            execution_seed = self._generate_seed(tenant_id, tasks)
        
        # Assign tasks to nodes
        node_assignments: Dict[str, List[str]] = {node: [] for node in self._nodes}
        
        for task in tasks:
            node_id = self.schedule_cluster_execution(tenant_id, task)
            task_id = task.get("task_id", f"task_{len(tasks)}")
            node_assignments[node_id].append(task_id)
        
        # Create schedule
        self._schedule_counter += 1
        schedule = ClusterSchedule(
            schedule_id=f"schedule_{self._schedule_counter}",
            tenant_id=tenant_id,
            node_assignments=node_assignments,
            execution_seed=execution_seed,
            created_at=datetime.utcnow().isoformat()
        )
        
        return schedule
    
    def _generate_seed(self, tenant_id: str, tasks: List[Dict[str, Any]]) -> int:
        """Generate deterministic seed from tenant and tasks"""
        data = {
            "tenant_id": tenant_id,
            "tasks": sorted([t.get("task_id", "") for t in tasks])
        }
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        hash_value = hashlib.sha256(canonical.encode()).hexdigest()
        return int(hash_value[:8], 16)
    
    def add_node(self, node_id: str):
        """Add a node to the scheduler pool"""
        if node_id not in self._nodes:
            self._nodes.append(node_id)
    
    def remove_node(self, node_id: str):
        """Remove a node from the scheduler pool"""
        if node_id in self._nodes:
            self._nodes.remove(node_id)
    
    def get_nodes(self) -> List[str]:
        """Get all nodes in the scheduler pool"""
        return self._nodes.copy()
