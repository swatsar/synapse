# Synapse Security Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## 🛡️ Security Architecture

Synapse implements a **capability-based security model** with automatic isolation enforcement.

---

## 🔐 Capability-Based Security

### Overview

Every action in Synapse requires specific capabilities. Capabilities are granted through tokens and validated before execution.

### Capability Format

```
<domain>:<action>:<resource>
```

### Standard Capabilities

| Capability | Description |
|------------|-------------|
| `fs:read:/workspace/**` | Read files in workspace |
| `fs:write:/workspace/**` | Write files in workspace |
| `network:http` | Make HTTP requests |
| `network:websocket` | WebSocket connections |
| `os:process` | Execute subprocesses |
| `memory:read` | Read from memory store |
| `memory:write` | Write to memory store |
| `llm:generate` | Use LLM providers |
| `llm:embed` | Generate embeddings |

### Capability Validation

```python
from synapse.security import CapabilityManager

# Initialize manager
cap_manager = CapabilityManager()

# Check capabilities
result = await cap_manager.check_capabilities(
    required=["fs:read:/workspace/**", "network:http"],
    context=execution_context
)

if result.approved:
    # Proceed with execution
    pass
else:
    # Access denied
    raise CapabilityError(f"Missing: {result.blocked_capabilities}")
```

---

## 🔒 Isolation Enforcement

### Automatic Sandboxing

Synapse automatically determines isolation level based on:

1. **Trust Level** of the skill
2. **Risk Level** of the operation

### Isolation Types

| Type | Description | Use Case |
|------|-------------|----------|
| `subprocess` | Light isolation in separate process | Trusted skills, low risk |
| `container` | Full Docker container isolation | Untrusted skills, high risk |

### Isolation Policy

```python
from synapse.core.isolation_policy import IsolationEnforcementPolicy
from synapse.skills.base import SkillTrustLevel

# Get required isolation
isolation = IsolationEnforcementPolicy.get_required_isolation(
    trust_level=SkillTrustLevel.UNVERIFIED,
    risk_level=4
)

# Result: RuntimeIsolationType.CONTAINER
```

### Policy Rules

| Trust Level | Risk Level | Isolation |
|-------------|------------|-----------|
| Trusted | 1-2 | subprocess |
| Trusted | 3+ | container |
| Verified | 1-2 | subprocess |
| Verified | 3+ | container |
| Unverified | Any | container |

---

## ⚠️ Risk Levels

### Risk Assessment

| Level | Description | Examples |
|-------|-------------|----------|
| 1 | Minimal risk | Read file, simple computation |
| 2 | Low risk | Write file, memory operations |
| 3 | Medium risk | Network requests, API calls |
| 4 | High risk | Process execution, system changes |
| 5 | Critical risk | Destructive operations, security changes |

### Human Approval

Operations with **risk_level >= 3** require human approval:

```python
# Automatic approval request
if skill.manifest.risk_level >= 3:
    approval = await security.request_human_approval(
        skill_name=skill.manifest.name,
        risk_level=skill.manifest.risk_level,
        trace_id=context.trace_id
    )
    
    if not approval.approved:
        raise ApprovalDeniedError("Human denied execution")
```

---

## 📝 Audit Logging

### Audit Events

All security-relevant events are logged:

- Capability checks
- Isolation decisions
- Human approvals
- Execution results
- Security violations

### Audit Log Format

```json
{
  "timestamp": "2026-02-20T12:00:00Z",
  "event_type": "capability_check",
  "agent_id": "agent-001",
  "session_id": "session-123",
  "trace_id": "trace-456",
  "action": "execute_skill",
  "result": "approved",
  "capabilities": ["fs:read:/workspace/**"],
  "protocol_version": "1.0"
}
```

### Accessing Audit Logs

```bash
# View audit logs
tail -f /var/log/synapse/audit.log

# Search for specific events
grep "capability_check" /var/log/synapse/audit.log
```

---

## 🔑 API Key Management

### Best Practices

1. **Never hardcode API keys** - Use environment variables
2. **Rotate keys regularly** - Every 90 days recommended
3. **Use separate keys** - Different keys for dev/staging/prod
4. **Monitor usage** - Track API calls per key

### Configuration

```bash
# .env file
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Never commit .env files
echo ".env" >> .gitignore
```

---

## 🚨 Security Best Practices

### 1. Principle of Least Privilege

```python
# Good: Request only needed capabilities
result = await client.execute(
    task="Read file",
    capabilities=["fs:read:/workspace/file.txt"]  # Specific
)

# Bad: Request broad capabilities
result = await client.execute(
    task="Read file",
    capabilities=["fs:read:/**"]  # Too broad
)
```

### 2. Validate All Inputs

```python
# Always validate user input
import re

def validate_path(path: str) -> bool:
    # Only allow workspace paths
    return path.startswith("/workspace/") and ".." not in path
```

### 3. Use Human Approval for High-Risk

```python
# Configure approval threshold
security_config = {
    "require_approval_for_risk": 3,  # Risk >= 3 requires approval
    "trusted_users": ["admin@company.com"]
}
```

### 4. Monitor and Alert

```yaml
# prometheus_alerts.yml
groups:
  - name: synapse_security
    rules:
      - alert: HighRiskExecution
        expr: synapse_risk_level >= 4
        for: 1m
        labels:
          severity: critical
```

---

## 🔍 Security Checklist

- [ ] All skills have proper capability requirements
- [ ] Risk levels are correctly assigned
- [ ] Human approval configured for risk >= 3
- [ ] Audit logging enabled
- [ ] API keys stored securely
- [ ] Container isolation for untrusted code
- [ ] Rate limiting configured
- [ ] Input validation implemented

---

## 📚 Related Documentation

- [Installation Guide](INSTALLATION_GUIDE.md)
- [Quick Start](QUICKSTART.md)
- [Troubleshooting](TROUBLESHOOTING.md)

---

**Protocol Version:** 1.0  
**Spec Version:** 3.1
