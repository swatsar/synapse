"""
Execution Authorization Token - Deterministic Authorization Chain
"""

import hashlib
import json
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, UTC

PROTOCOL_VERSION = "1.0"


@dataclass
class AuthorizationRequest:
    """Request for execution authorization"""
    tenant_id: str
    node_id: str
    capabilities: List[str]
    execution_seed: int
    protocol_version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class ExecutionAuthorizationToken:
    """Cryptographic execution authorization token"""
    token_id: str
    tenant_id: str
    node_id: str
    capabilities: List[str]
    execution_seed: int
    token_hash: str
    audit_root: str
    protocol_version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @classmethod
    def issue(cls, request: AuthorizationRequest) -> "ExecutionAuthorizationToken":
        """Issue deterministic authorization token"""
        # Compute deterministic token hash
        token_data = {
            "tenant_id": request.tenant_id,
            "node_id": request.node_id,
            "capabilities": sorted(request.capabilities),
            "execution_seed": request.execution_seed,
            "protocol_version": request.protocol_version
        }

        canonical = json.dumps(token_data, sort_keys=True, separators=(',', ':'))
        token_hash = hashlib.sha256(canonical.encode()).hexdigest()

        # Compute audit root
        audit_data = {
            "token_hash": token_hash,
            "timestamp": request.timestamp,
            "protocol_version": request.protocol_version
        }
        audit_root = hashlib.sha256(
            json.dumps(audit_data, sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest()

        return cls(
            token_id=f"token_{token_hash[:16]}",
            tenant_id=request.tenant_id,
            node_id=request.node_id,
            capabilities=request.capabilities,
            execution_seed=request.execution_seed,
            token_hash=token_hash,
            audit_root=audit_root,
            protocol_version=request.protocol_version
        )


class AuthorizationChain:
    """
    Deterministic authorization chain.
    Maintains verifiable chain of authorization tokens.
    """

    PROTOCOL_VERSION = PROTOCOL_VERSION

    def __init__(self):
        self._tokens: List[ExecutionAuthorizationToken] = []
        self._root_hash: Optional[str] = None

    def add_token(self, token: ExecutionAuthorizationToken):
        """Add token to chain"""
        self._tokens.append(token)
        self._update_root_hash()

    def verify_integrity(self) -> bool:
        """Verify chain integrity"""
        if not self._tokens:
            return True

        # Verify each token hash is valid
        for token in self._tokens:
            request = AuthorizationRequest(
                tenant_id=token.tenant_id,
                node_id=token.node_id,
                capabilities=token.capabilities,
                execution_seed=token.execution_seed,
                protocol_version=token.protocol_version
            )
            expected = ExecutionAuthorizationToken.issue(request)
            if token.token_hash != expected.token_hash:
                return False

        return True

    def compute_root_hash(self) -> str:
        """Compute root hash of entire chain"""
        if not self._tokens:
            return hashlib.sha256(b"empty_chain").hexdigest()

        chain_data = {
            "tokens": [token.token_hash for token in self._tokens],
            "protocol_version": self.PROTOCOL_VERSION
        }

        canonical = json.dumps(chain_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _update_root_hash(self):
        """Update cached root hash"""
        self._root_hash = self.compute_root_hash()

    def compute_chain_root(self) -> str:
        """Compute deterministic root hash of authorization chain"""
        import hashlib
        import json

        if not self._tokens:
            return hashlib.sha256("empty_chain".encode()).hexdigest()

        # Collect all token hashes in order
        token_hashes = [token.token_hash for token in self._tokens]

        chain_data = {
            "tokens": token_hashes,
            "protocol_version": self.PROTOCOL_VERSION
        }

        canonical = json.dumps(chain_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
