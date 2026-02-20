"""Deterministic Execution Module.

Provides deterministic ID generation and execution utilities.
"""
import hashlib
import uuid
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


class DeterministicIDGenerator:
    """Generates deterministic IDs based on namespace and input.
    
    Same namespace + same input = same output.
    Different input = different output.
    """
    
    protocol_version: str = "1.0"
    
    def __init__(self, namespace: str = "default", seed: Optional[int] = None):
        """Initialize generator with namespace or seed.
        
        Args:
            namespace: Namespace for deterministic generation
            seed: Optional seed (converted to namespace if provided)
        """
        self.protocol_version = "1.0"
        # Support both seed and namespace for backward compatibility
        if seed is not None:
            self._namespace = str(seed)
        else:
            self._namespace = namespace
    
    def generate(self, *args) -> str:
        """Generate deterministic ID from inputs.
        
        Supports two calling conventions:
        - generate(input_data: str) - uses instance namespace
        - generate(namespace: str, input_data: str) - uses provided namespace
        
        Args:
            *args: Either (input_data) or (namespace, input_data)
            
        Returns:
            Deterministic UUID string
        """
        if len(args) == 1:
            # Single argument: use instance namespace
            input_data = args[0]
            combined = f"{self._namespace}:{input_data}"
        elif len(args) == 2:
            # Two arguments: use provided namespace
            namespace, input_data = args
            combined = f"{namespace}:{input_data}"
        else:
            raise ValueError(f"generate() takes 1 or 2 arguments, got {len(args)}")
        
        hash_bytes = hashlib.sha256(combined.encode()).digest()
        deterministic_uuid = uuid.UUID(bytes=hash_bytes[:16])
        return str(deterministic_uuid)
    
    def generate_task_id(self, task_name: str, context_seed: int) -> str:
        """Generate task ID from name and context seed.
        
        Args:
            task_name: Task name
            context_seed: Context execution seed
            
        Returns:
            Deterministic task ID
        """
        combined = f"{context_seed}:{task_name}"
        hash_bytes = hashlib.sha256(combined.encode()).digest()
        deterministic_uuid = uuid.UUID(bytes=hash_bytes[:16])
        return str(deterministic_uuid)


@dataclass
class DeterministicSeedManager:
    """Manages deterministic seeds for reproducible execution.
    
    Ensures same seed produces same execution path.
    """
    
    protocol_version: str = "1.0"
    seed: int = 0
    _counter: int = field(default=0, repr=False)
    
    def get_next_seed(self) -> int:
        """Get next deterministic seed.
        
        Returns:
            Next seed in sequence
        """
        self._counter += 1
        return self.seed + self._counter
    
    def derive_seed(self, context: str) -> int:
        """Derive seed from context string.
        
        Args:
            context: Context string
            
        Returns:
            Derived seed
        """
        combined = f"{self.seed}:{context}"
        hash_val = hashlib.sha256(combined.encode()).hexdigest()
        return int(hash_val[:8], 16)
    
    def reset(self) -> None:
        """Reset counter."""
        self._counter = 0
