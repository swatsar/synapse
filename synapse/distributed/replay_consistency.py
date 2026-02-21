"""
Multi-Node Replay Consistency
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, UTC
import hashlib
import json

@dataclass
class StateHash:
    """Deterministic state hash"""
    node_id: str
    workflow_id: str
    execution_seed: int
    state_hash: str
    timestamp: str
    protocol_version: str = "1.0"
    
    @classmethod
    def compute(cls, node_id: str, workflow_id: str, execution_seed: int, state: Dict) -> 'StateHash':
        """Compute deterministic state hash
        
        IMPORTANT: node_id is NOT included in hash computation
        to ensure identical state produces identical hash across nodes.
        """
        # node_id is NOT included in hash - only workflow_id, seed, and state
        state_data = {
            "workflow_id": workflow_id,
            "execution_seed": execution_seed,
            "state": state,
            "protocol_version": "1.0"
        }
        canonical = json.dumps(state_data, sort_keys=True, separators=(',', ':'))
        state_hash = hashlib.sha256(canonical.encode()).hexdigest()
        
        return cls(
            node_id=node_id,
            workflow_id=workflow_id,
            execution_seed=execution_seed,
            state_hash=state_hash,
            timestamp=datetime.now(UTC).isoformat()
        )


@dataclass
class ConsistencyReport:
    """Replay consistency report"""
    workflow_id: str
    execution_seed: int
    node_hashes: Dict[str, str]  # node_id -> state_hash
    is_consistent: bool
    mismatch_details: List[Dict[str, Any]]
    timestamp: str
    protocol_version: str = "1.0"


class ReplayConsistencyManager:
    """Manages replay consistency across nodes"""
    
    def __init__(self):
        self._state_hashes: Dict[str, List[StateHash]] = {}  # workflow_id -> list of hashes
    
    def record_state_hash(self, state_hash: StateHash):
        """Record state hash from a node"""
        key = f"{state_hash.workflow_id}:{state_hash.execution_seed}"
        if key not in self._state_hashes:
            self._state_hashes[key] = []
        self._state_hashes[key].append(state_hash)
    
    def check_consistency(self, workflow_id: str, execution_seed: int) -> ConsistencyReport:
        """Check consistency across nodes"""
        key = f"{workflow_id}:{execution_seed}"
        hashes = self._state_hashes.get(key, [])
        
        node_hashes = {h.node_id: h.state_hash for h in hashes}
        unique_hashes = set(node_hashes.values())
        
        is_consistent = len(unique_hashes) <= 1
        
        mismatch_details = []
        if not is_consistent:
            for node_id, hash_val in node_hashes.items():
                mismatch_details.append({
                    "node_id": node_id,
                    "state_hash": hash_val,
                    "expected": list(unique_hashes)[0] if unique_hashes else None
                })
        
        return ConsistencyReport(
            workflow_id=workflow_id,
            execution_seed=execution_seed,
            node_hashes=node_hashes,
            is_consistent=is_consistent,
            mismatch_details=mismatch_details,
            timestamp=datetime.now(UTC).isoformat()
        )
    
    def replay_workflow(self, workflow_id: str, execution_seed: int) -> Optional[ConsistencyReport]:
        """Replay and verify workflow"""
        return self.check_consistency(workflow_id, execution_seed)
