"""
Deterministic behavior for reproducible execution
"""

import random
import hashlib
import uuid
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, UTC


class DeterministicOrder:
    """Ensures consistent ordering of elements"""
    
    @staticmethod
    def deterministic_order(items, seed):
        """Returns deterministic order of items using seed"""
        if not items:
            return []
        
        rng = random.Random(seed)
        items_list = list(items)
        rng.shuffle(items_list)
        return items_list


@dataclass
class DeterministicSeed:
    """Represents a deterministic seed"""
    value: int
    created_at: str = ""
    protocol_version: str = "1.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()


class DeterministicSeedManager:
    """Manages deterministic seeds for reproducible execution"""
    
    def __init__(self, master_seed: Optional[int] = None, seed: Optional[int] = None):
        # Instance attribute for protocol version
        self.protocol_version = "1.0"
        # Support both 'master_seed' and 'seed' as parameter names
        self.master_seed = master_seed or seed or random.randint(0, 2**32 - 1)
        self._seed_history: List[DeterministicSeed] = []
        self._current_seed: Optional[int] = None
    
    def generate_seed(self, context: Optional[str] = None) -> int:
        """Generate a deterministic seed based on master seed and context"""
        if context:
            context_hash = hashlib.sha256(f"{self.master_seed}:{context}".encode()).hexdigest()
            seed = int(context_hash[:8], 16)
        else:
            seed = (self.master_seed + len(self._seed_history)) % (2**32)
        
        self._seed_history.append(DeterministicSeed(value=seed))
        self._current_seed = seed
        return seed
    
    def get_current_seed(self) -> Optional[int]:
        """Get current seed"""
        return self._current_seed
    
    def set_seed(self, seed: int):
        """Set a specific seed"""
        self._current_seed = seed
        self._seed_history.append(DeterministicSeed(value=seed))
    
    def get_history(self) -> List[DeterministicSeed]:
        """Get seed history"""
        return self._seed_history.copy()
    
    def reset(self):
        """Reset seed manager"""
        self._seed_history.clear()
        self._current_seed = None


class DeterministicIDGenerator:
    """Generates deterministic IDs based on seeds"""
    
    def __init__(self, seed: Optional[int] = None):
        # Instance attribute for protocol version
        self.protocol_version = "1.0"
        self.seed = seed or random.randint(0, 2**32 - 1)
        self._counter = 0
    
    def generate(self, *args, **kwargs) -> str:
        """Generate a deterministic ID - accepts flexible arguments"""
        # Extract prefix from args or kwargs
        prefix = "id"
        if args and isinstance(args[0], str):
            prefix = args[0]
        elif 'prefix' in kwargs:
            prefix = kwargs['prefix']
        
        combined = f"{prefix}:{self.seed}:{self._counter}"
        hash_value = hashlib.sha256(combined.encode()).hexdigest()[:12]
        self._counter += 1
        return f"{prefix}_{hash_value}"
    
    def generate_uuid(self) -> str:
        """Generate a deterministic UUID"""
        combined = f"{self.seed}:{self._counter}"
        hash_bytes = hashlib.sha256(combined.encode()).digest()
        self._counter += 1
        return str(uuid.UUID(bytes=hash_bytes[:16]))
    
    def reset(self):
        """Reset counter"""
        self._counter = 0
    
    def set_seed(self, seed: int):
        """Set new seed"""
        self.seed = seed
        self._counter = 0
