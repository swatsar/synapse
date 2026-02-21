"""
Distributed Execution Node Protocol
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, UTC
import hashlib
import json
import secrets

@dataclass(frozen=True)
class NodeIdentity:
    """Cryptographic node identity"""
    node_id: str
    public_key: str
    created_at: str
    protocol_version: str = "1.0"
    
    def compute_hash(self) -> str:
        """Deterministic identity hash"""
        data = {
            "node_id": self.node_id,
            "public_key": self.public_key,
            "created_at": self.created_at,
            "protocol_version": self.protocol_version
        }
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class ExecutionRequest:
    """Signed execution request"""
    request_id: str
    workflow_id: str
    workflow_hash: str
    requester_id: str
    target_node_id: str
    capability_token_id: str
    execution_seed: int
    timestamp: str
    signature: str
    protocol_version: str = "1.0"
    
    def to_canonical(self) -> str:
        """Canonical serialization"""
        data = {
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "workflow_hash": self.workflow_hash,
            "requester_id": self.requester_id,
            "target_node_id": self.target_node_id,
            "capability_token_id": self.capability_token_id,
            "execution_seed": self.execution_seed,
            "timestamp": self.timestamp,
            "protocol_version": self.protocol_version
        }
        return json.dumps(data, sort_keys=True, separators=(',', ':'))


@dataclass
class ExecutionTrace:
    """Network-safe execution trace"""
    trace_id: str
    workflow_id: str
    node_id: str
    state_hash: str
    steps: List[Dict[str, Any]]
    execution_time_ms: int
    timestamp: str
    signature: str
    protocol_version: str = "1.0"
    
    def compute_hash(self) -> str:
        """Deterministic trace hash"""
        data = {
            "trace_id": self.trace_id,
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "state_hash": self.state_hash,
            "steps": self.steps,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp,
            "protocol_version": self.protocol_version
        }
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()


class NodeHandshake:
    """Node handshake protocol"""
    
    def __init__(self, node_identity: NodeIdentity, secret_key: bytes):
        self.identity = node_identity
        self.secret_key = secret_key
    
    def create_handshake_request(self) -> Dict[str, Any]:
        """Create handshake request"""
        timestamp = datetime.now(UTC).isoformat()
        challenge = secrets.token_hex(16)
        
        return {
            "node_id": self.identity.node_id,
            "public_key": self.identity.public_key,
            "timestamp": timestamp,
            "challenge": challenge,
            "protocol_version": "1.0"
        }
    
    def verify_handshake_response(self, response: Dict[str, Any]) -> bool:
        """Verify handshake response"""
        required_fields = ["node_id", "signature", "timestamp"]
        return all(field in response for field in required_fields)
