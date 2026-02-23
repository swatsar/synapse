# Phase 6.1 Architecture Baseline

**Version:** 3.2.1  
**Date:** 2026-02-23  
**Protocol Version:** 1.0  
**Status:** FROZEN

---

## 1. ARCHITECTURAL OVERVIEW

Phase 6.1 establishes the **Deterministic Multi-Tenant Runtime** architecture baseline. This document serves as the authoritative reference for all Phase 7 development.

### Core Principles

1. **Deterministic Execution** - Identical inputs produce identical outputs across all nodes
2. **Multi-Tenant Isolation** - Cryptographic tenant boundaries enforced at all layers
3. **Capability Governance** - All actions require explicit capability tokens
4. **Audit Chain Integrity** - Merkle-root verified audit trails
5. **Protocol Versioning** - All messages include protocol_version="1.0"

---

## 2. DETERMINISTIC EXECUTION MODEL

### 2.1 Execution Seed

Every execution context includes an `execution_seed` that guarantees reproducibility:

```python
@dataclass
class ExecutionContext:
    session_id: str
    agent_id: str
    trace_id: str
    execution_seed: int  # Deterministic randomness source
    protocol_version: str = "1.0"
```

### 2.2 Canonical Serialization

All state must be serialized canonically:

```python
def canonical_serialize(data: dict) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True
    )
```

### 2.3 Hash Computation

All hashes use SHA-256 over canonical JSON:

```python
def compute_hash(data: dict) -> str:
    canonical = canonical_serialize(data)
    return hashlib.sha256(canonical.encode()).hexdigest()
```

### 2.4 Determinism Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| No system time | Use execution_seed for timestamps |
| No random() | Use seeded PRNG |
| No network entropy | Mock or deterministic responses |
| No process IDs | Use session_id instead |
| No hardware IDs | Use node_id from config |

---

## 3. MULTI-TENANT CONTROL PLANE

### 3.1 Tenant Scheduler

```python
class TenantScheduler:
    def schedule(self, tenant_id: str, tasks: List[Task]) -> ScheduleResult
    def compute_schedule_hash(self, schedule: Schedule) -> str
```

**Invariants:**
- Schedule hash is deterministic for identical task sets
- Tenant isolation enforced at schedule level
- Resource quotas checked before scheduling

### 3.2 Tenant Quota Registry

```python
@dataclass
class ExecutionQuota:
    max_cpu_seconds: int
    max_memory_mb: int
    max_disk_mb: int
    max_network_kb: int
    max_concurrent_tasks: int

class TenantQuotaRegistry:
    def register_tenant_quota(self, tenant_id: str, quota: ExecutionQuota) -> None
    def get_quota(self, tenant_id: str) -> ExecutionQuota
    def enforce_quota(self, tenant_id: str, usage: ResourceUsage) -> None
```

**Invariants:**
- Quota enforcement is mandatory
- Quota bypass attempts are blocked and logged
- Quota updates require admin capability

### 3.3 Tenant State Partition

```python
class TenantStatePartition:
    def get_state(self, tenant_id: str, key: str) -> Optional[Any]
    def set_state(self, tenant_id: str, key: str, value: Any) -> None
```

**Invariants:**
- Cross-tenant state access is blocked
- State keys are tenant-scoped
- State operations are audited

---

## 4. RUNTIME CONTRACT SYSTEM

### 4.1 Contract Definition

```python
@dataclass
class RuntimeContract:
    contract_id: str
    execution_seed: int
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    capability_requirements: List[str]
    resource_limits: ResourceLimits
    protocol_version: str = "1.0"
```

### 4.2 Contract Validation

```python
class DeterministicRuntimeAPI:
    def register_contract(self, contract: RuntimeContract) -> str
    def validate_contract(self, contract_id: str) -> ContractValidationResult
    def execute_with_contract(self, contract_id: str, input: Any) -> ExecutionResult
    def get_contract_hash(self, contract_id: str) -> str
```

**Invariants:**
- Contract hash is deterministic
- Contract validation is mandatory before execution
- Contract forgery is blocked

---

## 5. CAPABILITY GOVERNANCE BOUNDARIES

### 5.1 Capability Domains

```python
@dataclass
class CapabilityDomain:
    domain_id: str
    domain_name: str
    capabilities: List[CapabilityDescriptor]
    dependencies: List[str]
    protocol_version: str = "1.0"
```

### 5.2 Domain Registry

```python
class DomainRegistry:
    def register_domain(self, domain: CapabilityDomain) -> str
    def get_domain(self, domain_id: str) -> Optional[CapabilityDomain]
    def check_capability(self, domain_id: str, capability: str) -> bool
    def validate_descriptor(self, descriptor: CapabilityDescriptor) -> bool
```

### 5.3 Capability Boundaries

| Boundary | Enforcement |
|----------|-------------|
| Domain isolation | Capabilities scoped to domain |
| Dependency resolution | Missing dependencies block execution |
| Revocation | Revoked capabilities are rejected |
| Escalation | Capability escalation attempts blocked |

---

## 6. AUDIT CHAIN TRUST MODEL

### 6.1 Audit Chain Structure

```python
class TenantAuditChain:
    def append_event(self, tenant_id: str, event: AuditEvent) -> str
    def get_merkle_root(self, tenant_id: str) -> str
    def verify_chain(self, tenant_id: str) -> bool
    def replay(self, tenant_id: str) -> ReplayResult
```

### 6.2 Merkle Root Verification

```
Root Hash = H(H(H(event_1) + H(event_2)) + H(H(event_3) + H(event_4)))
```

### 6.3 Trust Invariants

| Invariant | Implementation |
|-----------|----------------|
| Immutability | Events cannot be modified |
| Integrity | Merkle root detects tampering |
| Replay safety | Replay produces identical root |
| Tenant isolation | Each tenant has separate chain |

---

## 7. SANDBOX INTERFACE

### 7.1 Sandbox Abstraction

```python
class SandboxInterface(ABC):
    @abstractmethod
    async def execute(self, code: str, context: SandboxContext) -> SandboxResult
    
    @abstractmethod
    async def validate_output(self, result: Any) -> bool
    
    def get_resource_usage(self) -> ResourceUsage
    def is_isolated(self) -> bool
```

### 7.2 Isolation Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| Process isolation | Separate process/container |
| Resource limits | CPU, memory, disk, network |
| Syscall filtering | Blocked dangerous syscalls |
| Network isolation | Whitelist-only access |

---

## 8. PROTOCOL VERSIONING

### 8.1 Version Format

```
protocol_version: "MAJOR.MINOR"

Current: "1.0"
```

### 8.2 Version Requirements

- All messages MUST include protocol_version
- All models MUST include protocol_version field
- All API responses MUST include protocol_version
- Version changes require architecture review

---

## 9. ARCHITECTURAL CONSTRAINTS

### 9.1 Frozen Interfaces

The following interfaces are frozen and cannot be modified in Phase 7:

- `TenantScheduler.schedule()`
- `TenantScheduler.compute_schedule_hash()`
- `TenantQuotaRegistry.register_tenant_quota()`
- `TenantQuotaRegistry.get_quota()`
- `TenantQuotaRegistry.enforce_quota()`
- `TenantAuditChain.append_event()`
- `TenantAuditChain.get_merkle_root()`
- `DeterministicRuntimeAPI.register_contract()`
- `DeterministicRuntimeAPI.execute_with_contract()`
- `DomainRegistry.check_capability()`

### 9.2 Extension Points

Phase 7 may extend:

- New capability domains
- New sandbox implementations
- New audit chain backends
- New scheduler strategies

---

## 10. VERIFICATION STATUS

```
╔══════════════════════════════════════════════════════════════╗
║  PHASE 6.1 BASELINE: FROZEN                                  ║
║                                                              ║
║  Determinism: ✅ Verified                                    ║
║  Multi-tenant: ✅ Verified                                   ║
║  Capability: ✅ Verified                                     ║
║  Audit: ✅ Verified                                          ║
║  Coverage: 98%                                               ║
║  Tests: 118 passed                                           ║
╚══════════════════════════════════════════════════════════════╝
```

---

**Document Status:** FROZEN  
**Next Review:** Phase 7 Planning  
**Protocol Version:** 1.0
