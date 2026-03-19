# Synapse Platform Specification

## Version Information

- **Platform Version:** 3.4.1
- **Protocol Version:** 1.0
- **Spec Version:** 3.1
- **Status:** Pre-Production

## Core Specification Documents

| Document | Description |
|----------|-------------|
| [Architecture Overview](docs/architecture_overview.md) | System architecture and components |
| [Security Model](docs/security_model.md) | Capability-based security + 4-level trust model |
| [Deterministic Execution](docs/deterministic_execution_model.md) | Determinism guarantees |
| [Capability Governance](docs/capability_governance.md) | Capability lifecycle management |
| [Distributed Execution](docs/distributed_execution_model.md) | Multi-node execution model |
| [Agent Runtime](docs/agent_runtime_model.md) | Agent execution environment |
| [Replay and Audit](docs/replay_and_audit.md) | Execution verification |
| [Deployment](docs/deployment_architecture.md) | Deployment modes |
| [Scaling Strategy](docs/platform_scaling_strategy.md) | Platform scaling |

## System Invariants

| Invariant | Description |
|-----------|-------------|
| 8-Step Cognitive Cycle | Perceive → Recall → Plan → Security → Act → Observe → Evaluate → Learn |
| 4-Level Trust Model | Trusted / Verified / Unverified / Human-Approved |
| 6-State Skill Lifecycle | Generated → Tested → Verified → Active → Deprecated → Archived |
| Capability Security | Zero implicit permissions; CapabilityScope enum enforced |
| Deterministic Execution | Identical inputs → identical outputs |
| Policy Governance | All actions validated by PolicyEngine |
| Replay Verifiability | All executions reconstructable |
| Zero Trust | No implicit trust between components |
| Cross-Platform | Environment adapters for Windows/Linux/macOS |

## Protocol Versioning

All modules implement:

```python
PROTOCOL_VERSION: str = "1.0"
```

## CapabilityScope Enum

```python
class CapabilityScope(str, Enum):
    FILESYSTEM_READ = "fs:read"
    FILESYSTEM_WRITE = "fs:write"
    NETWORK_HTTP = "net:http"
    PROCESS_SPAWN = "os:process"
    DEVICE_IOT = "iot:control"
    SYSTEM_INFO = "sys:info"
```

## Execution Trust Levels

```python
class SkillTrustLevel(str, Enum):
    TRUSTED = "trusted"           # Built-in skills → subprocess
    VERIFIED = "verified"         # Auto-tested + AST → subprocess (isolated)
    UNVERIFIED = "unverified"     # LLM-generated → sandbox (strict)
    HUMAN_APPROVED = "human_approved"  # User-approved → subprocess (extended)
```

## Deployment Modes

1. **Local Mode:** Single process, SQLite
2. **Docker Mode:** Containerized, PostgreSQL + Redis + ChromaDB
3. **Distributed Mode:** Multi-node cluster with Zero-Trust
