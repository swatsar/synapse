# Synapse Security Model

## Overview

Synapse implements a **Capability-Based Security Model** with zero implicit permissions and cryptographic verification.

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SECURITY BOUNDARIES                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              CAPABILITY TOKEN LAYER                 │   │
│  │  • Cryptographic signing                             │   │
│  │  • Scope restrictions                                │   │
│  │  • Time-based expiration                             │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              PERMISSION ENFORCEMENT                  │   │
│  │  • Runtime capability checks                         │   │
│  │  • Policy validation                                 │   │
│  │  • Audit logging                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              EXECUTION ISOLATION                     │   │
│  │  • Container sandboxing                              │   │
│  │  • Resource limits                                   │   │
│  │  • Network isolation                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Capability Token Structure

```python
@dataclass
class CapabilityToken:
    """Cryptographically signed capability token"""
    token_id: str
    agent_id: str
    capability: str           # e.g., "fs:read:/workspace/**"
    scope: str               # Resource scope
    issued_at: datetime
    expires_at: datetime
    issuer_id: str
    signature: str           # Cryptographic signature
    protocol_version: str = "1.0"
```

---

## Capability Scopes

| Scope Pattern | Description | Example |
|---------------|-------------|---------|
| `fs:read:<path>` | File read access | `fs:read:/workspace/**` |
| `fs:write:<path>` | File write access | `fs:write:/workspace/output/**` |
| `net:http:<domain>` | HTTP access | `net:http:api.example.com` |
| `os:process` | Process execution | `os:process` |
| `memory:read` | Memory access | `memory:read` |

---

## Threat Model

### STRIDE Analysis

| Threat | Mitigation | Implementation |
|--------|------------|----------------|
| **Spoofing** | Token signing | Ed25519 signatures |
| **Tampering** | State hashing | SHA-256 verification |
| **Repudiation** | Audit logging | Immutable audit trail |
| **Information Disclosure** | Scope restrictions | Path-based ACLs |
| **Denial of Service** | Resource limits | Quota enforcement |
| **Elevation of Privilege** | Capability checks | Runtime enforcement |

---

## Security Invariants

1. **Zero Implicit Permissions**: No action allowed without explicit capability
2. **Least Privilege**: Capabilities grant minimum required access
3. **Defense in Depth**: Multiple security layers
4. **Audit Completeness**: All actions logged with cryptographic proof
5. **Token Expiration**: All capabilities have time limits

---

## Enforcement Points

```python
async def execute_with_security(action, context):
    # 1. Capability check
    if not await capability_manager.has_capability(context.agent_id, action.required_capability):
        raise CapabilityError("Missing required capability")
    
    # 2. Policy validation
    if not await policy_engine.validate(action, context):
        raise PolicyViolationError("Action violates policy")
    
    # 3. Audit logging
    await audit_mechanism.log_action(action, context)
    
    # 4. Execute in isolation
    result = await execute_in_sandbox(action, context)
    
    return result
```

---

## Isolation Policy

| Trust Level | Isolation Type | Use Case |
|-------------|----------------|----------|
| **Trusted** | Subprocess | Built-in skills |
| **Verified** | Container | Tested skills |
| **Unverified** | Strict Sandbox | Generated skills |

---

## Audit Trail

Every action produces an audit entry:

```python
@dataclass
class AuditEntry:
    entry_id: str
    timestamp: datetime
    agent_id: str
    action: str
    capability_used: str
    result: str
    state_hash: str
    protocol_version: str = "1.0"
```

---

## Security Checklist

- [x] Capability-based access control
- [x] Cryptographic token signing
- [x] Policy validation engine
- [x] Execution isolation
- [x] Resource quota enforcement
- [x] Complete audit trail
- [x] Zero implicit permissions
- [x] Token expiration
