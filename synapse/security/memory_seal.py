"""
Memory Seal - Cryptographic Sealing for Agent Memory
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from datetime import datetime, UTC
import hashlib
import json
import hmac


@dataclass(frozen=True)
class SealedMemory:
    """Cryptographically sealed memory snapshot"""
    seal_id: str
    agent_id: str
    data_hash: str
    signature: str
    created_at: str
    protocol_version: str = "1.0"


class MemorySeal:
    """Cryptographic memory sealing system"""
    
    def __init__(self, secret_key: bytes = b"synapse_default_key"):
        self.secret_key = secret_key
        self._sealed_memories: Dict[str, SealedMemory] = {}
    
    def seal(
        self,
        agent_id: str,
        data: Dict[str, Any]
    ) -> SealedMemory:
        """Create cryptographic seal for memory data"""
        # Compute data hash
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        data_hash = hashlib.sha256(canonical.encode()).hexdigest()
        
        # Create signature
        signature = self._create_signature(agent_id, data_hash)
        
        # Create seal ID
        seal_id = hashlib.sha256(
            f"{agent_id}:{data_hash}:{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Create sealed memory
        sealed = SealedMemory(
            seal_id=seal_id,
            agent_id=agent_id,
            data_hash=data_hash,
            signature=signature,
            created_at=datetime.now(UTC).isoformat()
        )
        
        self._sealed_memories[seal_id] = sealed
        
        return sealed
    
    def verify(self, seal_id: str, data: Dict[str, Any]) -> bool:
        """Verify memory seal integrity"""
        if seal_id not in self._sealed_memories:
            return False
        
        sealed = self._sealed_memories[seal_id]
        
        # Verify data hash
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        computed_hash = hashlib.sha256(canonical.encode()).hexdigest()
        
        if computed_hash != sealed.data_hash:
            return False
        
        # Verify signature
        expected_sig = self._create_signature(sealed.agent_id, sealed.data_hash)
        
        return hmac.compare_digest(expected_sig, sealed.signature)
    
    def detect_tampering(self, seal_id: str, data: Dict[str, Any]) -> bool:
        """Detect if sealed memory has been tampered with"""
        return not self.verify(seal_id, data)
    
    def reconstruct(
        self,
        seal_id: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Reconstruct data if seal is valid"""
        if self.verify(seal_id, data):
            return dict(data)
        return None
    
    def _create_signature(self, agent_id: str, data_hash: str) -> str:
        """Create HMAC signature"""
        message = f"{agent_id}:{data_hash}".encode()
        signature = hmac.new(
            self.secret_key,
            message,
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def get_seal_count(self) -> int:
        """Get total number of sealed memories"""
        return len(self._sealed_memories)
    
    def get_agent_seals(self, agent_id: str) -> list:
        """Get all seal IDs for an agent"""
        return [
            seal_id for seal_id, sealed in self._sealed_memories.items()
            if sealed.agent_id == agent_id
        ]
