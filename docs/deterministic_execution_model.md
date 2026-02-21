# Deterministic Execution Model

## Overview

Synapse guarantees **deterministic execution**: identical inputs always produce identical outputs across all nodes.

---

## Determinism Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                DETERMINISTIC EXECUTION FLOW                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input + Seed                                               │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           DETERMINISTIC PLANNING                     │   │
│  │  • Seed-based ID generation                          │   │
│  │  • Deterministic task ordering                       │   │
│  │  • Hash-based decisions                              │   │
│  └─────────────────────────────────────────────────────┘   │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           STATE HASH COMPUTATION                     │   │
│  │  • Input hash                                        │   │
│  │  • Execution trace hash                              │   │
│  │  • Output hash                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           REPLAY VERIFICATION                        │   │
│  │  • Trace reconstruction                              │   │
│  │  • Hash comparison                                   │   │
│  │  • State validation                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│       │                                                     │
│       ▼                                                     │
│  Deterministic Output                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Determinism Guarantees

| Guarantee | Implementation | Verification |
|-----------|----------------|--------------|
| **Input Determinism** | Seed-based processing | Input hash comparison |
| **Planning Determinism** | No randomness in planner | Plan hash comparison |
| **Execution Determinism** | Isolated execution | State hash comparison |
| **Output Determinism** | Hash-addressed outputs | Output hash comparison |

---

## Seed Management

```python
class DeterministicSeedManager:
    """Manages deterministic seeds for reproducible execution"""
    
    def __init__(self, master_seed: int):
        self.master_seed = master_seed
        self._seed_history: List[int] = []
    
    def generate_seed(self, context: str) -> int:
        """Generate deterministic seed from master + context"""
        combined = f"{self.master_seed}:{context}"
        return int(hashlib.sha256(combined.encode()).hexdigest()[:8], 16)
```

---

## State Hashing

```python
class StateHash:
    """Computes deterministic state hashes"""
    
    @staticmethod
    def compute(state: dict) -> str:
        """Compute SHA-256 hash of state"""
        # Sort keys for determinism
        sorted_state = json.dumps(state, sort_keys=True)
        return hashlib.sha256(sorted_state.encode()).hexdigest()
```

---

## Replay System

```python
class ReplayManager:
    """Reconstructs and verifies executions"""
    
    async def record_execution(self, trace: ExecutionTrace):
        """Record execution trace for replay"""
        pass
    
    async def replay(self, trace_id: str) -> ExecutionResult:
        """Replay execution from trace"""
        pass
    
    async def verify(self, original: ExecutionResult, replayed: ExecutionResult) -> bool:
        """Verify replay produces identical result"""
        return original.state_hash == replayed.state_hash
```

---

## Deterministic ID Generation

```python
class DeterministicIDGenerator:
    """Generates deterministic IDs from seeds"""
    
    def __init__(self, seed: int):
        self.seed = seed
        self._counter = 0
    
    def generate(self, prefix: str = "id") -> str:
        """Generate deterministic ID"""
        combined = f"{prefix}:{self.seed}:{self._counter}"
        hash_value = hashlib.sha256(combined.encode()).hexdigest()[:12]
        self._counter += 1
        return f"{prefix}_{hash_value}"
```

---

## Multi-Node Consistency

For distributed execution:

1. **Same Input Hash**: All nodes compute identical input hash
2. **Same Plan Hash**: All nodes generate identical plan
3. **Same State Hash**: All nodes produce identical state

---

## Verification Tests

```python
def test_deterministic_execution():
    """Verify identical inputs produce identical outputs"""
    seed = 12345
    input_data = {"task": "process", "payload": 1}
    
    # Run twice with same seed
    result1 = execute(input_data, seed)
    result2 = execute(input_data, seed)
    
    assert result1.state_hash == result2.state_hash
    assert result1.output == result2.output
```

---

## Non-Determinism Prevention

The following are **prohibited**:

- ❌ Random number generation without seed
- ❌ System time in decision logic
- ❌ Non-deterministic ordering
- ❌ External state without hashing
- ❌ Parallel execution without ordering
