"""
Phase 7.1: Orchestrator Control Plane - Data Models
Protocol Version: 1.0

This module defines data structures for the orchestrator control plane.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib
import json


PROTOCOL_VERSION = "1.0"


@dataclass
class ExecutionRequest:
    """Request for execution submission"""
    tenant_id: str
    contract_id: str
    input_data: Dict[str, Any]
    protocol_version: str = PROTOCOL_VERSION
    
    def compute_hash(self) -> str:
        """Compute deterministic hash of request"""
        data = {
            'tenant_id': self.tenant_id,
            'contract_id': self.contract_id,
            'input_data': self.input_data,
            'protocol_version': self.protocol_version
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()


@dataclass
class ExecutionProvenanceRecord:
    """Record of execution provenance"""
    execution_id: str
    tenant_id: str
    contract_hash: str
    node_id: str
    cluster_schedule_hash: str
    audit_root: str
    execution_proof: str
    timestamp: str
    protocol_version: str = PROTOCOL_VERSION
    
    def compute_provenance_hash(self) -> str:
        """Compute deterministic hash of provenance record"""
        data = {
            'execution_id': self.execution_id,
            'tenant_id': self.tenant_id,
            'contract_hash': self.contract_hash,
            'node_id': self.node_id,
            'cluster_schedule_hash': self.cluster_schedule_hash,
            'audit_root': self.audit_root,
            'execution_proof': self.execution_proof,
            'timestamp': self.timestamp,
            'protocol_version': self.protocol_version
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()


@dataclass
class TrustedNodeDescriptor:
    """Descriptor for a trusted cluster node"""
    node_id: str
    node_name: str
    public_key: str
    trust_level: int
    registered_at: str
    protocol_version: str = PROTOCOL_VERSION
    
    def compute_node_hash(self) -> str:
        """Compute deterministic hash of node descriptor"""
        data = {
            'node_id': self.node_id,
            'node_name': self.node_name,
            'public_key': self.public_key,
            'trust_level': self.trust_level,
            'registered_at': self.registered_at,
            'protocol_version': self.protocol_version
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()


@dataclass
class ExecutionStatus:
    """Status of an execution"""
    execution_id: str
    status: str  # pending, running, completed, failed
    tenant_id: str
    contract_id: str
    node_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class ClusterMembership:
    """Cluster membership state"""
    membership_hash: str
    nodes: List[str]
    quorum_count: int
    timestamp: str
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class AuditLogEntry:
    """Audit log entry for control plane operations"""
    audit_id: str
    operation: str
    tenant_id: str
    execution_id: Optional[str]
    timestamp: str
    details: Dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION
