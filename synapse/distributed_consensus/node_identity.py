"""
Node Identity for Synapse Distributed Execution.
Provides cryptographic node identity and verification.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import hashlib
import secrets

PROTOCOL_VERSION: str = "1.0"


@dataclass
class NodeIdentity:
    """Cryptographic node identity"""
    node_id: str
    public_key: str
    private_key: str  # In production, this would be secured
    certificate: str
    created_at: datetime
    expires_at: Optional[datetime]
    protocol_version: str = PROTOCOL_VERSION


class NodeIdentityManager:
    """
    Manages node identities.
    
    Invariants:
    - Node IDs are unique
    - Identities are cryptographically verifiable
    - Expired identities are rejected
    """
    
    def __init__(self):
        self._identities: dict = {}
    
    async def generate_identity(self, node_id: Optional[str] = None) -> NodeIdentity:
        """Generate a new node identity"""
        if node_id is None:
            node_id = self._generate_node_id()
        
        # Generate key pair (simplified for demo)
        private_key = secrets.token_hex(32)
        public_key = hashlib.sha256(private_key.encode()).hexdigest()
        
        # Generate certificate - deterministic based on node_id + public_key only
        certificate = self._generate_certificate(node_id, public_key)
        
        identity = NodeIdentity(
            node_id=node_id,
            public_key=public_key,
            private_key=private_key,
            certificate=certificate,
            created_at=datetime.utcnow(),
            expires_at=None,
            protocol_version=PROTOCOL_VERSION
        )
        
        self._identities[node_id] = identity
        return identity
    
    async def verify_identity(self, identity: NodeIdentity) -> bool:
        """Verify a node identity"""
        # Check if identity exists in our registry
        if identity.node_id not in self._identities:
            return False
        
        stored = self._identities[identity.node_id]
        
        # Verify public key matches
        if identity.public_key != stored.public_key:
            return False
        
        # Verify certificate matches
        if identity.certificate != stored.certificate:
            return False
        
        # Check expiration
        if identity.expires_at and datetime.utcnow() > identity.expires_at:
            return False
        
        return True
    
    async def revoke_identity(self, node_id: str) -> bool:
        """Revoke a node identity"""
        if node_id not in self._identities:
            return False
        
        del self._identities[node_id]
        return True
    
    def _generate_node_id(self) -> str:
        """Generate unique node ID"""
        return f"node_{secrets.token_hex(8)}"
    
    def _generate_certificate(self, node_id: str, public_key: str) -> str:
        """Generate node certificate (deterministic)"""
        cert_data = f"{node_id}:{public_key}"
        return hashlib.sha256(cert_data.encode()).hexdigest()
