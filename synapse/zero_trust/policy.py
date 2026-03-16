"""
Trust Policy Engine - Deterministic Policy Evaluation
"""

import hashlib
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, UTC

PROTOCOL_VERSION = "1.0"


@dataclass
class PolicyRequest:
    """Request for policy evaluation"""
    tenant_id: str
    node_id: str
    action: str
    resource: str
    capabilities: List[str]
    execution_seed: int
    protocol_version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class PolicyResult:
    """Result of policy evaluation"""
    approved: bool
    evaluation_hash: str
    reason: str
    required_capabilities: List[str]
    provided_capabilities: List[str]
    protocol_version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class TrustPolicyEngine:
    """
    Deterministic trust policy engine.
    Same input always produces same evaluation result.
    """

    PROTOCOL_VERSION = PROTOCOL_VERSION

    # Policy rules (deterministic)
    POLICY_RULES = {
        "read": ["fs:read"],
        "write": ["fs:write"],
        "execute": ["os:process"],
        "delete": ["fs:delete"]
    }

    def evaluate(self, request: PolicyRequest) -> PolicyResult:
        """Evaluate policy request deterministically"""
        # Determine required capabilities
        required = self.POLICY_RULES.get(request.action, [])

        # Check if capabilities are satisfied
        provided = sorted(request.capabilities)
        required_sorted = sorted(required)

        # Check capability match
        has_all_caps = all(cap in provided for cap in required_sorted)

        # Compute deterministic evaluation hash
        eval_data = {
            "tenant_id": request.tenant_id,
            "node_id": request.node_id,
            "action": request.action,
            "resource": request.resource,
            "capabilities": sorted(request.capabilities),
            "execution_seed": request.execution_seed,
            "approved": has_all_caps,
            "protocol_version": self.PROTOCOL_VERSION
        }

        canonical = json.dumps(eval_data, sort_keys=True, separators=(',', ':'))
        evaluation_hash = hashlib.sha256(canonical.encode()).hexdigest()

        # Determine reason
        if has_all_caps:
            reason = "Policy approved - all capabilities satisfied"
        else:
            missing = [cap for cap in required_sorted if cap not in provided]
            reason = f"Policy denied - missing capabilities: {missing}"

        return PolicyResult(
            approved=has_all_caps,
            evaluation_hash=evaluation_hash,
            reason=reason,
            required_capabilities=required_sorted,
            provided_capabilities=provided,
            protocol_version=self.PROTOCOL_VERSION
        )
