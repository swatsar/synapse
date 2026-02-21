"""
Synapse Runtime Isolation Module

Provides multi-tenant execution isolation with:
- Execution Domain isolation
- Capability Domain boundaries
- Deterministic Sandbox
- Tenant Context security
- Isolation Enforcer

Protocol Version: 1.0
"""

from synapse.runtime_isolation.execution_domain import ExecutionDomain
from synapse.runtime_isolation.capability_domain import CapabilityDomain
from synapse.runtime_isolation.sandbox import DeterministicSandbox
from synapse.runtime_isolation.tenant_context import TenantContext
from synapse.runtime_isolation.isolation_enforcer import IsolationEnforcer

__all__ = [
    "ExecutionDomain",
    "CapabilityDomain",
    "DeterministicSandbox",
    "TenantContext",
    "IsolationEnforcer"
]

PROTOCOL_VERSION = "1.0"
