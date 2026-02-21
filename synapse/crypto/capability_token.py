"""
Signed Capability Token System for Cryptographic Governance
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, UTC
import hashlib
import hmac
import secrets
import json

@dataclass(frozen=True)
class CapabilityToken:
    """Immutable signed capability token"""
    token_id: str
    agent_id: str
    capability: str
    scope: str
    issued_at: str
    expires_at: str
    issuer_id: str
    signature: str
    protocol_version: str = "1.0"
    
    def to_canonical(self) -> str:
        """Canonical serialization for deterministic hashing"""
        data = {
            "token_id": self.token_id,
            "agent_id": self.agent_id,
            "capability": self.capability,
            "scope": self.scope,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "issuer_id": self.issuer_id,
            "protocol_version": self.protocol_version
        }
        return json.dumps(data, sort_keys=True, separators=(',', ':'))
    
    def compute_hash(self) -> str:
        """Deterministic token hash"""
        canonical = self.to_canonical()
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        now = datetime.now(UTC).isoformat()
        return now > self.expires_at


class TokenIssuer:
    """Issues signed capability tokens"""
    
    def __init__(self, issuer_id: str, secret_key: Optional[bytes] = None):
        self.issuer_id = issuer_id
        self.secret_key = secret_key or secrets.token_bytes(32)
        self._issued_tokens: Dict[str, CapabilityToken] = {}
    
    def issue_token(
        self,
        agent_id: str,
        capability: str,
        scope: str,
        ttl_seconds: int = 3600
    ) -> CapabilityToken:
        """Issue a signed capability token"""
        now = datetime.now(UTC)
        issued_at = now.isoformat()
        expires_at = datetime.fromtimestamp(
            now.timestamp() + ttl_seconds, UTC
        ).isoformat()
        
        token_id = hashlib.sha256(
            f"{agent_id}:{capability}:{issued_at}".encode()
        ).hexdigest()[:16]
        
        # Create unsigned token data
        unsigned_data = {
            "token_id": token_id,
            "agent_id": agent_id,
            "capability": capability,
            "scope": scope,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "issuer_id": self.issuer_id,
            "protocol_version": "1.0"
        }
        
        # Generate signature
        canonical = json.dumps(unsigned_data, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.secret_key,
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()
        
        token = CapabilityToken(
            token_id=token_id,
            agent_id=agent_id,
            capability=capability,
            scope=scope,
            issued_at=issued_at,
            expires_at=expires_at,
            issuer_id=self.issuer_id,
            signature=signature
        )
        
        self._issued_tokens[token_id] = token
        return token
    
    def get_issued_token(self, token_id: str) -> Optional[CapabilityToken]:
        """Get issued token by ID"""
        return self._issued_tokens.get(token_id)


class TokenVerifier:
    """Verifies signed capability tokens"""
    
    def __init__(self, issuer_id: str, secret_key: bytes):
        self.issuer_id = issuer_id
        self.secret_key = secret_key
    
    def verify_token(self, token: CapabilityToken) -> bool:
        """Verify token signature and validity"""
        # Check issuer
        if token.issuer_id != self.issuer_id:
            return False
        
        # Check expiration
        if token.is_expired():
            return False
        
        # Verify signature
        unsigned_data = {
            "token_id": token.token_id,
            "agent_id": token.agent_id,
            "capability": token.capability,
            "scope": token.scope,
            "issued_at": token.issued_at,
            "expires_at": token.expires_at,
            "issuer_id": token.issuer_id,
            "protocol_version": token.protocol_version
        }
        
        canonical = json.dumps(unsigned_data, sort_keys=True, separators=(',', ':'))
        expected_signature = hmac.new(
            self.secret_key,
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(token.signature, expected_signature)


class TokenRevocationList:
    """Manages revoked tokens"""
    
    def __init__(self):
        self._revoked: Dict[str, str] = {}  # token_id -> revocation_reason
    
    def revoke(self, token_id: str, reason: str = "revoked"):
        """Revoke a token"""
        self._revoked[token_id] = reason
    
    def is_revoked(self, token_id: str) -> bool:
        """Check if token is revoked"""
        return token_id in self._revoked
    
    def get_revocation_reason(self, token_id: str) -> Optional[str]:
        """Get revocation reason"""
        return self._revoked.get(token_id)
