"""
Remote Attestation Verification
"""

import hashlib
import json
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, UTC

PROTOCOL_VERSION = "1.0"


@dataclass
class AttestationRequest:
    """Request for remote attestation"""
    node_id: str
    execution_hash: str
    protocol_version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class AttestationResponse:
    """Response from attestation verification"""
    verified: bool
    attestation_hash: str
    node_id: str
    reason: str
    protocol_version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class RemoteAttestationVerifier:
    """
    Verifies remote node execution attestations.
    """

    PROTOCOL_VERSION = PROTOCOL_VERSION

    # Known valid execution hashes (simulated)
    VALID_HASHES = {
        "abc123": True,
        "def456": True,
        "ghi789": True
    }

    def verify(self, request: AttestationRequest) -> AttestationResponse:
        """Verify attestation request"""

        # Check if execution hash is known/valid
        is_valid = request.execution_hash in self.VALID_HASHES

        # Compute attestation hash
        att_data = {
            "node_id": request.node_id,
            "execution_hash": request.execution_hash,
            "verified": is_valid,
            "protocol_version": self.PROTOCOL_VERSION
        }

        canonical = json.dumps(att_data, sort_keys=True, separators=(',', ':'))
        attestation_hash = hashlib.sha256(canonical.encode()).hexdigest()

        reason = "Attestation verified" if is_valid else "Unknown execution hash"

        return AttestationResponse(
            verified=is_valid,
            attestation_hash=attestation_hash,
            node_id=request.node_id,
            reason=reason,
            protocol_version=self.PROTOCOL_VERSION
        )
