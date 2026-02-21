"""
State Hash Consensus for Synapse Distributed Execution.
Ensures all nodes agree on execution state.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib
import json

PROTOCOL_VERSION: str = "1.0"


@dataclass
class StateHash:
    """Hash of execution state"""
    hash_value: str
    timestamp: datetime
    node_id: str
    execution_id: str
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class ConsensusResult:
    """Result of consensus check"""
    agreed: bool
    agreed_hash: Optional[str]
    disagreeing_nodes: List[str]
    timestamp: datetime
    protocol_version: str = PROTOCOL_VERSION


class StateHashConsensus:
    """
    Manages state hash consensus across nodes.
    
    Invariants:
    - All nodes must agree on state hash
    - Disagreement triggers rollback
    - Consensus is deterministic
    """
    
    def __init__(self, required_agreement: float = 1.0):
        self.required_agreement = required_agreement
        self._state_hashes: Dict[str, StateHash] = {}
    
    async def submit_hash(self, state_hash: StateHash) -> bool:
        """Submit a state hash from a node"""
        key = f"{state_hash.execution_id}:{state_hash.node_id}"
        self._state_hashes[key] = state_hash
        return True
    
    async def check_consensus(self, execution_id: str) -> ConsensusResult:
        """Check if all nodes agree on state hash"""
        # Get all hashes for this execution
        execution_hashes = [
            h for h in self._state_hashes.values()
            if h.execution_id == execution_id
        ]
        
        if not execution_hashes:
            return ConsensusResult(
                agreed=False,
                agreed_hash=None,
                disagreeing_nodes=[],
                timestamp=datetime.utcnow(),
                protocol_version=PROTOCOL_VERSION
            )
        
        # Count hash occurrences
        hash_counts: Dict[str, List[str]] = {}
        for h in execution_hashes:
            if h.hash_value not in hash_counts:
                hash_counts[h.hash_value] = []
            hash_counts[h.hash_value].append(h.node_id)
        
        # Find majority hash
        majority_hash = max(hash_counts.keys(), key=lambda k: len(hash_counts[k]))
        agreement_ratio = len(hash_counts[majority_hash]) / len(execution_hashes)
        
        agreed = agreement_ratio >= self.required_agreement
        disagreeing = [
            node_id for hash_val, nodes in hash_counts.items()
            if hash_val != majority_hash
            for node_id in nodes
        ]
        
        return ConsensusResult(
            agreed=agreed,
            agreed_hash=majority_hash if agreed else None,
            disagreeing_nodes=disagreeing,
            timestamp=datetime.utcnow(),
            protocol_version=PROTOCOL_VERSION
        )
    
    async def compute_state_hash(self, state: dict) -> str:
        """Compute deterministic state hash"""
        # Sort for determinism
        state_json = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_json.encode()).hexdigest()
    
    def clear_execution(self, execution_id: str):
        """Clear hashes for an execution"""
        keys_to_remove = [
            k for k in self._state_hashes
            if k.startswith(f"{execution_id}:")
        ]
        for key in keys_to_remove:
            del self._state_hashes[key]
