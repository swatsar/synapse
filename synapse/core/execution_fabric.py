"""ExecutionFabric – deterministic node selection and task submission (sync)."""
import hashlib
import json
from typing import Any, Dict, List
from .determinism import DeterministicSeedManager

PROTOCOL_VERSION: str = "1.0"

class ExecutionFabric:
    """Deterministic task routing to cluster nodes."""
    protocol_version: str = PROTOCOL_VERSION
    
    def __init__(self, seed_manager: DeterministicSeedManager = None):
        self.nodes: List[Any] = []
        self.seed_manager = seed_manager or DeterministicSeedManager()
        self._selection_counter = 0

    def register_node(self, node):
        """Register a node for task execution."""
        self.nodes.append(node)

    def select_node(self, task: Dict[str, Any]):
        """Select a node deterministically based on task content.
        Same task always routes to the same node.
        """
        if not self.nodes:
            raise RuntimeError("No nodes registered")
        
        # Use task hash for deterministic selection
        task_str = json.dumps(task, sort_keys=True, default=str)
        task_hash = int(hashlib.sha256(task_str.encode()).hexdigest(), 16)
        idx = task_hash % len(self.nodes)
        return self.nodes[idx]

    def submit(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a task to the selected node."""
        node = self.select_node(task)
        result = node.execute(task)
        return result
