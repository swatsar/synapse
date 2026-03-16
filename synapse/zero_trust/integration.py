"""
Zero-Trust Integration - Distributed Execution
"""

import hashlib
import json
from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime, UTC

from .identity import TrustIdentityRegistry, NodeDescriptor
from .authorization import ExecutionAuthorizationToken, AuthorizationRequest, AuthorizationChain
from .policy import TrustPolicyEngine, PolicyRequest
from .enforcement import ZeroTrustEnforcer

PROTOCOL_VERSION = "1.0"


@dataclass
class CrossNodePermission:
    """Permission for cross-node execution"""
    source_node: str
    target_node: str
    capabilities: List[str]
    permission_hash: str
    protocol_version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class ZeroTrustIntegration:
    """
    Integration layer for zero-trust distributed execution.
    Ensures deterministic execution across nodes.
    """

    PROTOCOL_VERSION = PROTOCOL_VERSION

    def __init__(self):
        self._identity_registry = TrustIdentityRegistry()
        self._policy_engine = TrustPolicyEngine()
        self._auth_chain = AuthorizationChain()

    def run_distributed_execution(self, tenant_id: str, node_id: str,
                                   cluster_id: str, execution_seed: int) -> str:
        """Run distributed execution with zero-trust layer"""

        # 1. Register identity
        descriptor = NodeDescriptor(
            node_id=node_id,
            cluster_id=cluster_id,
            capabilities=["fs:read", "fs:write"],
            protocol_version=self.PROTOCOL_VERSION
        )
        identity = self._identity_registry.register(descriptor)

        # 2. Issue authorization token
        auth_request = AuthorizationRequest(
            tenant_id=tenant_id,
            node_id=node_id,
            capabilities=["fs:read", "fs:write"],
            execution_seed=execution_seed,
            protocol_version=self.PROTOCOL_VERSION
        )
        token = ExecutionAuthorizationToken.issue(auth_request)
        self._auth_chain.add_token(token)

        # 3. Evaluate policy
        policy_request = PolicyRequest(
            tenant_id=tenant_id,
            node_id=node_id,
            action="execute",
            resource="/distributed/workflow",
            capabilities=["fs:read", "fs:write"],
            execution_seed=execution_seed,
            protocol_version=self.PROTOCOL_VERSION
        )
        policy_result = self._policy_engine.evaluate(policy_request)

        # 4. Compute execution root hash
        execution_data = {
            "identity_hash": identity.identity_hash,
            "token_hash": token.token_hash,
            "policy_hash": policy_result.evaluation_hash,
            "execution_seed": execution_seed,
            "protocol_version": self.PROTOCOL_VERSION
        }

        canonical = json.dumps(execution_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def issue_cross_node_permission(self, source_node: str, target_node: str,
                                     capabilities: List[str]) -> CrossNodePermission:
        """Issue cross-node permission"""
        permission_data = {
            "source_node": source_node,
            "target_node": target_node,
            "capabilities": sorted(capabilities),
            "protocol_version": self.PROTOCOL_VERSION
        }

        canonical = json.dumps(permission_data, sort_keys=True, separators=(',', ':'))
        permission_hash = hashlib.sha256(canonical.encode()).hexdigest()

        return CrossNodePermission(
            source_node=source_node,
            target_node=target_node,
            capabilities=capabilities,
            permission_hash=permission_hash,
            protocol_version=self.PROTOCOL_VERSION
        )

    def replay_permission(self, permission: CrossNodePermission) -> CrossNodePermission:
        """Replay cross-node permission"""
        # Deterministic replay - same hash
        return CrossNodePermission(
            source_node=permission.source_node,
            target_node=permission.target_node,
            capabilities=permission.capabilities,
            permission_hash=permission.permission_hash,
            protocol_version=permission.protocol_version
        )
