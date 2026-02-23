"""
Phase 7: Distributed Orchestration Layer
Protocol Version: 1.0

Components:
- DistributedExecutionDomain
- ClusterScheduler
- OrchestratorRuntimeBridge
- FederatedAuditCoordinator
"""

from .distributed_execution_domain import DistributedExecutionDomain
from .cluster_scheduler import ClusterScheduler
from .orchestrator_runtime_bridge import OrchestratorRuntimeBridge
from .federated_audit_coordinator import FederatedAuditCoordinator

__all__ = [
    'DistributedExecutionDomain',
    'ClusterScheduler',
    'OrchestratorRuntimeBridge',
    'FederatedAuditCoordinator'
]

PROTOCOL_VERSION = "1.0"
