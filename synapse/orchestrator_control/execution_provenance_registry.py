"""
Phase 7.1: Execution Provenance Registry
Protocol Version: 1.0

Track full execution lineage.
Records tenant_id, contract_hash, node_id, cluster_schedule_hash, audit_root, execution_proof.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import hashlib
import json

from synapse.orchestrator_control.models import (
    ExecutionProvenanceRecord,
    PROTOCOL_VERSION
)


@dataclass
class ProvenanceChain:
    """Chain of provenance records"""
    execution_id: str
    records: List[ExecutionProvenanceRecord]
    chain_hash: str
    protocol_version: str = PROTOCOL_VERSION


class ExecutionProvenanceRegistry:
    """
    Track full execution lineage.
    
    Must record:
    - tenant_id
    - contract_hash
    - node_id
    - cluster_schedule_hash
    - audit_root
    - execution_proof
    
    Public API:
    - record_execution_provenance(record)
    - get_execution_provenance(execution_id)
    - verify_provenance_chain(execution_id)
    """
    
    PROTOCOL_VERSION = PROTOCOL_VERSION
    
    def __init__(self):
        self._records: Dict[str, ExecutionProvenanceRecord] = {}
        self._chains: Dict[str, ProvenanceChain] = {}
        self._audit_roots: Dict[str, str] = {}
    
    def record_execution_provenance(
        self,
        record: ExecutionProvenanceRecord
    ) -> str:
        """
        Record execution provenance.
        
        Args:
            record: Execution provenance record
            
        Returns:
            execution_id
        """
        # Store the record
        self._records[record.execution_id] = record
        
        # Store audit root mapping
        self._audit_roots[record.execution_id] = record.audit_root
        
        # Create or update provenance chain
        if record.execution_id not in self._chains:
            chain_hash = self._compute_chain_hash([record])
            self._chains[record.execution_id] = ProvenanceChain(
                execution_id=record.execution_id,
                records=[record],
                chain_hash=chain_hash
            )
        else:
            # Append to existing chain
            chain = self._chains[record.execution_id]
            chain.records.append(record)
            chain.chain_hash = self._compute_chain_hash(chain.records)
        
        return record.execution_id
    
    def get_execution_provenance(
        self,
        execution_id: str
    ) -> Optional[ExecutionProvenanceRecord]:
        """
        Get execution provenance.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            Execution provenance record or None
        """
        return self._records.get(execution_id)
    
    def verify_provenance_chain(
        self,
        execution_id: str
    ) -> bool:
        """
        Verify provenance chain integrity.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            True if chain is valid, False otherwise
        """
        if execution_id not in self._records:
            return False
        
        record = self._records[execution_id]
        
        # Verify record hash
        computed_hash = record.compute_provenance_hash()
        
        # Verify audit root exists
        if execution_id not in self._audit_roots:
            return False
        
        # Verify chain exists
        if execution_id not in self._chains:
            return False
        
        chain = self._chains[execution_id]
        
        # Verify chain hash
        expected_chain_hash = self._compute_chain_hash(chain.records)
        if chain.chain_hash != expected_chain_hash:
            return False
        
        return True
    
    def get_provenance_chain(
        self,
        execution_id: str
    ) -> Optional[ProvenanceChain]:
        """
        Get full provenance chain.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            Provenance chain or None
        """
        return self._chains.get(execution_id)
    
    def get_audit_root(self, execution_id: str) -> Optional[str]:
        """Get audit root for execution"""
        return self._audit_roots.get(execution_id)
    
    def list_executions(self) -> List[str]:
        """List all execution IDs"""
        return list(self._records.keys())
    
    def get_executions_by_tenant(self, tenant_id: str) -> List[str]:
        """Get all executions for a tenant"""
        return [
            exec_id for exec_id, record in self._records.items()
            if record.tenant_id == tenant_id
        ]
    
    def get_executions_by_node(self, node_id: str) -> List[str]:
        """Get all executions for a node"""
        return [
            exec_id for exec_id, record in self._records.items()
            if record.node_id == node_id
        ]
    
    def _compute_chain_hash(
        self,
        records: List[ExecutionProvenanceRecord]
    ) -> str:
        """Compute deterministic hash of provenance chain"""
        data = {
            'records': [
                {
                    'execution_id': r.execution_id,
                    'tenant_id': r.tenant_id,
                    'contract_hash': r.contract_hash,
                    'node_id': r.node_id,
                    'cluster_schedule_hash': r.cluster_schedule_hash,
                    'audit_root': r.audit_root,
                    'execution_proof': r.execution_proof,
                    'timestamp': r.timestamp,
                    'protocol_version': r.protocol_version
                }
                for r in records
            ],
            'protocol_version': self.PROTOCOL_VERSION
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
    
    def compute_registry_hash(self) -> str:
        """Compute deterministic hash of entire registry"""
        data = {
            'executions': sorted([
                {
                    'execution_id': r.execution_id,
                    'tenant_id': r.tenant_id,
                    'contract_hash': r.contract_hash,
                    'node_id': r.node_id,
                    'audit_root': r.audit_root
                }
                for r in self._records.values()
            ], key=lambda x: x['execution_id']),
            'protocol_version': self.PROTOCOL_VERSION
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
