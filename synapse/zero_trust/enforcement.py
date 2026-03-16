"""
Zero-Trust Execution Enforcement
"""

import hashlib
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, UTC

from .identity import TrustIdentityRegistry, NodeDescriptor
from .authorization import ExecutionAuthorizationToken, AuthorizationRequest
from .policy import TrustPolicyEngine, PolicyRequest

PROTOCOL_VERSION = "1.0"


@dataclass
class ExecutionResult:
    """Result of zero-trust execution attempt"""
    success: bool
    error: Optional[str] = None
    execution_hash: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class ZeroTrustEnforcer:
    """
    Enforces zero-trust execution policy.
    Blocks execution without proper identity, token, and policy approval.
    """

    PROTOCOL_VERSION = PROTOCOL_VERSION

    def __init__(self):
        self._identity_registry = TrustIdentityRegistry()
        self._policy_engine = TrustPolicyEngine()
        self._tokens: Dict[str, ExecutionAuthorizationToken] = {}

    def register_identity(self, node_id: str, cluster_id: str, capabilities: List[str] = None):
        """Register node identity with capabilities"""
        descriptor = NodeDescriptor(
            node_id=node_id,
            cluster_id=cluster_id,
            capabilities=capabilities or [],
            protocol_version=self.PROTOCOL_VERSION
        )
        self._identity_registry.register(descriptor)

    def issue_token(self, tenant_id: str, node_id: str,
                    capabilities: List[str]) -> ExecutionAuthorizationToken:
        """Issue authorization token"""
        request = AuthorizationRequest(
            tenant_id=tenant_id,
            node_id=node_id,
            capabilities=capabilities,
            execution_seed=0,
            protocol_version=self.PROTOCOL_VERSION
        )
        token = ExecutionAuthorizationToken.issue(request)
        self._tokens[token.token_id] = token
        return token

    def execute(self, node_id: Optional[str], action: str,
                resource: str, token: Optional[ExecutionAuthorizationToken] = None,
                policy_approved: bool = True) -> ExecutionResult:
        """Execute with zero-trust enforcement"""

        # Check 1: Identity required
        if node_id is None:
            return ExecutionResult(
                success=False,
                error="Execution blocked - no valid identity provided"
            )

        identity = self._identity_registry.get_identity(node_id)
        if identity is None:
            return ExecutionResult(
                success=False,
                error="Execution blocked - identity not registered"
            )

        # Check 2: Authorization token required
        if token is None:
            return ExecutionResult(
                success=False,
                error="Execution blocked - no authorization token provided"
            )

        # Check 3: Tenant validation - must not be empty
        if not token.tenant_id or token.tenant_id.strip() == "":
            return ExecutionResult(
                success=False,
                error="Execution blocked - missing tenant_id in token"
            )

        # Check 4: Capability validation - token capabilities must be subset of identity
        identity_caps = set(identity.capabilities)
        token_caps = set(token.capabilities)
        if not token_caps.issubset(identity_caps):
            missing = token_caps - identity_caps
            return ExecutionResult(
                success=False,
                error=f"Execution blocked - missing capabilities: {missing}"
            )

        # Check 5: Audit root integrity - verify hash matches expected
        expected_audit_root = hashlib.sha256(
            f"{token.tenant_id}:{token.node_id}:{token.token_id}:{self.PROTOCOL_VERSION}".encode()
        ).hexdigest()
        if token.audit_root != expected_audit_root:
            return ExecutionResult(
                success=False,
                error="Execution blocked - audit_root integrity violation"
            )

        # Check 6: Cluster assignment integrity - must match identity cluster
        if token.cluster_assignment != identity.cluster_id:
            return ExecutionResult(
                success=False,
                error="Execution blocked - cluster_assignment mismatch"
            )

        # Check 7: Policy approval required
        if not policy_approved:
            return ExecutionResult(
                success=False,
                error="Execution blocked - policy approval denied"
            )

        # All checks passed
        execution_hash = hashlib.sha256(
            f"{node_id}:{action}:{resource}:{self.PROTOCOL_VERSION}".encode()
        ).hexdigest()

        return ExecutionResult(
            success=True,
            execution_hash=execution_hash
        )
