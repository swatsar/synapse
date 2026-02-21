# Capability Governance

## Overview

Synapse implements a **formal capability governance system** for managing agent permissions throughout their lifecycle.

---

## Governance Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                CAPABILITY GOVERNANCE FLOW                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐                                            │
│  │   Request   │                                            │
│  │  Capability │                                            │
│  └──────┬──────┘                                            │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              POLICY VALIDATION                       │   │
│  │  • Check agent authorization                         │   │
│  │  • Validate scope                                    │   │
│  │  • Check resource limits                             │   │
│  └─────────────────────────────────────────────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              TOKEN ISSUANCE                           │   │
│  │  • Generate signed token                              │   │
│  │  • Set expiration                                     │   │
│  │  • Register in registry                               │   │
│  └─────────────────────────────────────────────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              LIFECYCLE MANAGEMENT                     │   │
│  │  • Track usage                                        │   │
│  │  • Monitor expiration                                 │   │
│  │  • Handle revocation                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Capability Registry

```python
class CapabilityRegistry:
    """Central registry for all capabilities"""
    
    def __init__(self):
        self._capabilities: Dict[str, CapabilityMetadata] = {}
        self._tokens: Dict[str, CapabilityToken] = {}
    
    async def register_capability(self, capability: str, metadata: CapabilityMetadata):
        """Register a new capability type"""
        pass
    
    async def issue_token(self, agent_id: str, capability: str, scope: str) -> CapabilityToken:
        """Issue a capability token to an agent"""
        pass
    
    async def revoke_token(self, token_id: str):
        """Revoke a capability token"""
        pass
```

---

## Capability Metadata

```python
@dataclass
class CapabilityMetadata:
    """Metadata for a capability type"""
    capability: str
    description: str
    risk_level: int           # 1-5
    requires_approval: bool
    max_scope: str
    default_ttl: int          # seconds
    protocol_version: str = "1.0"
```

---

## Issuance Policy

| Capability | Risk Level | Approval Required | Default TTL |
|------------|------------|-------------------|-------------|
| `fs:read` | 1 | No | 3600s |
| `fs:write` | 2 | No | 1800s |
| `net:http` | 2 | No | 3600s |
| `os:process` | 4 | Yes | 300s |
| `memory:admin` | 5 | Yes | 60s |

---

## Revocation

Capabilities can be revoked:

1. **Manual Revocation**: Admin-initiated
2. **Expiration**: Time-based automatic
3. **Policy Violation**: Automatic on violation
4. **Agent Termination**: Cleanup on agent stop

---

## Audit Trail

All capability operations are logged:

```python
@dataclass
class CapabilityAuditEntry:
    entry_id: str
    timestamp: datetime
    operation: str           # issue, use, revoke, expire
    agent_id: str
    capability: str
    token_id: str
    result: str
    protocol_version: str = "1.0"
```
