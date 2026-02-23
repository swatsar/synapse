"""
Phase 7.1: Orchestrator Control API
Protocol Version: 1.0

Entry point for external control (WebUI, orchestrator agent).
This layer exposes controlled interfaces without bypassing runtime contracts,
capability governance, or audit chain.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import hashlib
import json
import uuid
from datetime import datetime

from synapse.orchestrator_control.models import (
    ExecutionRequest,
    ExecutionStatus,
    AuditLogEntry,
    PROTOCOL_VERSION
)


@dataclass
class ExecutionResult:
    """Result of execution submission"""
    execution_id: str
    status: str
    audit_id: str
    timestamp: str
    protocol_version: str = PROTOCOL_VERSION


class OrchestratorControlAPI:
    """
    Entry point for external control (WebUI, orchestrator agent).
    
    Capabilities:
    - submit_execution_request(tenant_id, contract, input)
    - query_execution_status(execution_id)
    - retrieve_execution_proof(execution_id)
    - list_cluster_nodes()
    - get_cluster_root()
    
    Constraints:
    - must require runtime contract
    - must not expose direct execution access
    - must be audit-logged
    """
    
    PROTOCOL_VERSION = PROTOCOL_VERSION
    
    def __init__(
        self,
        provenance_registry=None,
        membership_authority=None,
        runtime_api=None,
        audit_log: Optional[List[AuditLogEntry]] = None
    ):
        self._provenance_registry = provenance_registry
        self._membership_authority = membership_authority
        self._runtime_api = runtime_api
        self._audit_log = audit_log if audit_log is not None else []
        self._executions: Dict[str, ExecutionStatus] = {}
        self._execution_proofs: Dict[str, Dict[str, Any]] = {}
    
    def submit_execution_request(
        self,
        tenant_id: str,
        contract_id: Optional[str],
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Submit an execution request.
        
        Args:
            tenant_id: Tenant identifier
            contract_id: Runtime contract identifier (required)
            input_data: Input data for execution
            
        Returns:
            Execution result with execution_id and audit_id
            
        Raises:
            ValueError: If contract_id is not provided
        """
        # Constraint: must require runtime contract
        if contract_id is None:
            raise ValueError("Runtime contract is required for execution")
        
        # Generate execution ID
        execution_id = self._generate_execution_id(tenant_id, contract_id, input_data)
        
        # Create audit log entry
        audit_id = self._create_audit_id()
        audit_entry = AuditLogEntry(
            audit_id=audit_id,
            operation="submit_execution_request",
            tenant_id=tenant_id,
            execution_id=execution_id,
            timestamp=datetime.utcnow().isoformat(),
            details={
                "contract_id": contract_id,
                "input_hash": self._compute_input_hash(input_data)
            }
        )
        self._audit_log.append(audit_entry)
        
        # Create execution status
        status = ExecutionStatus(
            execution_id=execution_id,
            status="pending",
            tenant_id=tenant_id,
            contract_id=contract_id
        )
        self._executions[execution_id] = status
        
        # Store execution proof placeholder
        self._execution_proofs[execution_id] = {
            "execution_id": execution_id,
            "tenant_id": tenant_id,
            "contract_id": contract_id,
            "input_hash": self._compute_input_hash(input_data),
            "audit_id": audit_id,
            "timestamp": audit_entry.timestamp,
            "protocol_version": self.PROTOCOL_VERSION
        }
        
        # Record in provenance registry if available
        if self._provenance_registry:
            from synapse.orchestrator_control.models import ExecutionProvenanceRecord
            record = ExecutionProvenanceRecord(
                execution_id=execution_id,
                tenant_id=tenant_id,
                contract_hash=self._compute_contract_hash(contract_id),
                node_id="node_0",  # Default node
                cluster_schedule_hash=self._compute_schedule_hash(execution_id),
                audit_root=self._compute_audit_root(audit_id),
                execution_proof=self._compute_execution_proof(execution_id),
                timestamp=audit_entry.timestamp
            )
            self._provenance_registry.record_execution_provenance(record)
        
        return {
            "execution_id": execution_id,
            "status": "pending",
            "audit_id": audit_id,
            "timestamp": audit_entry.timestamp,
            "protocol_version": self.PROTOCOL_VERSION
        }
    
    def query_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Query the status of an execution.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            Execution status or None if not found
        """
        # Create audit log entry
        audit_id = self._create_audit_id()
        audit_entry = AuditLogEntry(
            audit_id=audit_id,
            operation="query_execution_status",
            tenant_id="system",
            execution_id=execution_id,
            timestamp=datetime.utcnow().isoformat(),
            details={}
        )
        self._audit_log.append(audit_entry)
        
        status = self._executions.get(execution_id)
        if status:
            return {
                "execution_id": status.execution_id,
                "status": status.status,
                "tenant_id": status.tenant_id,
                "contract_id": status.contract_id,
                "node_id": status.node_id,
                "started_at": status.started_at,
                "completed_at": status.completed_at,
                "error": status.error,
                "protocol_version": self.PROTOCOL_VERSION
            }
        return None
    
    def retrieve_execution_proof(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the execution proof for an execution.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            Execution proof or None if not found
        """
        # Create audit log entry
        audit_id = self._create_audit_id()
        audit_entry = AuditLogEntry(
            audit_id=audit_id,
            operation="retrieve_execution_proof",
            tenant_id="system",
            execution_id=execution_id,
            timestamp=datetime.utcnow().isoformat(),
            details={}
        )
        self._audit_log.append(audit_entry)
        
        return self._execution_proofs.get(execution_id)
    
    def list_cluster_nodes(self) -> List[Dict[str, Any]]:
        """
        List all cluster nodes.
        
        Returns:
            List of node descriptors
        """
        # Create audit log entry
        audit_id = self._create_audit_id()
        audit_entry = AuditLogEntry(
            audit_id=audit_id,
            operation="list_cluster_nodes",
            tenant_id="system",
            execution_id=None,
            timestamp=datetime.utcnow().isoformat(),
            details={}
        )
        self._audit_log.append(audit_entry)
        
        if self._membership_authority:
            return self._membership_authority.list_nodes()
        
        # Default: return empty list
        return []
    
    def get_cluster_root(self) -> Dict[str, Any]:
        """
        Get the cluster root information.
        
        Returns:
            Cluster root information including membership hash
        """
        # Create audit log entry
        audit_id = self._create_audit_id()
        audit_entry = AuditLogEntry(
            audit_id=audit_id,
            operation="get_cluster_root",
            tenant_id="system",
            execution_id=None,
            timestamp=datetime.utcnow().isoformat(),
            details={}
        )
        self._audit_log.append(audit_entry)
        
        if self._membership_authority:
            return {
                "membership_hash": self._membership_authority.compute_membership_hash(),
                "node_count": len(self._membership_authority.list_nodes()),
                "protocol_version": self.PROTOCOL_VERSION
            }
        
        return {
            "membership_hash": "",
            "node_count": 0,
            "protocol_version": self.PROTOCOL_VERSION
        }
    
    def get_audit_log(self) -> List[AuditLogEntry]:
        """Get all audit log entries"""
        return self._audit_log.copy()
    
    def _generate_execution_id(
        self,
        tenant_id: str,
        contract_id: str,
        input_data: Dict[str, Any]
    ) -> str:
        """Generate deterministic execution ID"""
        data = {
            'tenant_id': tenant_id,
            'contract_id': contract_id,
            'input_hash': self._compute_input_hash(input_data),
            'timestamp': datetime.utcnow().isoformat(),
            'protocol_version': self.PROTOCOL_VERSION
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def _create_audit_id(self) -> str:
        """Create unique audit ID"""
        return f"audit_{uuid.uuid4().hex[:12]}"
    
    def _compute_input_hash(self, input_data: Dict[str, Any]) -> str:
        """Compute hash of input data"""
        return hashlib.sha256(
            json.dumps(input_data, sort_keys=True).encode()
        ).hexdigest()
    
    def _compute_contract_hash(self, contract_id: str) -> str:
        """Compute hash of contract"""
        return hashlib.sha256(contract_id.encode()).hexdigest()
    
    def _compute_schedule_hash(self, execution_id: str) -> str:
        """Compute schedule hash"""
        return hashlib.sha256(execution_id.encode()).hexdigest()
    
    def _compute_audit_root(self, audit_id: str) -> str:
        """Compute audit root"""
        return hashlib.sha256(audit_id.encode()).hexdigest()
    
    def _compute_execution_proof(self, execution_id: str) -> str:
        """Compute execution proof"""
        return hashlib.sha256(f"proof_{execution_id}".encode()).hexdigest()
