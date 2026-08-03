# Synapse Platform Specification

## Version Information

- **Platform Version:** 3.4.1
- **Protocol Version:** 1.0
- **Spec Version:** 3.1
- **Status:** Pre-Production

## Core Specification Documents

| Document | Description | Status |
|----------|-------------|--------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture and components | ✅ Exists |
| [Security Model](docs/user/security.md) | Capability-based security + 4-level trust model | ✅ Exists |
| [Deterministic Execution](ARCHITECTURE.md#deterministic-fabric) | Determinism guarantees | ✅ In ARCHITECTURE.md |
| [Capability Governance](SPECIFICATION.md#capability-governance) | Capability lifecycle management | ✅ In SPECIFICATION.md |
| [Distributed Execution](ARCHITECTURE.md#control-plane) | Multi-node execution model | ✅ In ARCHITECTURE.md |
| [Agent Runtime](ARCHITECTURE.md#agent-runtime) | Agent execution environment | ✅ In ARCHITECTURE.md |
| [Replay and Audit](ARCHITECTURE.md#audit-layer) | Execution verification | ✅ In ARCHITECTURE.md |
| [Deployment](docs/admin/deployment.md) | Deployment modes | ✅ Exists |
| [Scaling Strategy](docs/admin/monitoring.md) | Platform scaling | ✅ Exists |

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
