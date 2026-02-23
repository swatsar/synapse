"""
Phase 7.1: Orchestrator Control Plane

This module provides a secure control plane for orchestrator agents
and WebUI to manage distributed deterministic execution.

Components:
- OrchestratorControlAPI: Entry point for external control
- ExecutionProvenanceRegistry: Track full execution lineage
- ClusterMembershipAuthority: Deterministic cluster membership governance

Protocol Version: 1.0
"""

from synapse.orchestrator_control.orchestrator_control_api import OrchestratorControlAPI
from synapse.orchestrator_control.execution_provenance_registry import ExecutionProvenanceRegistry
from synapse.orchestrator_control.cluster_membership_authority import ClusterMembershipAuthority

__all__ = [
    'OrchestratorControlAPI',
    'ExecutionProvenanceRegistry',
    'ClusterMembershipAuthority'
]

PROTOCOL_VERSION = "1.0"
