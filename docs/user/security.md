# Security Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## Overview

Synapse implements a **Capability-Based Security Model** that provides fine-grained access control for all operations. This guide explains the security architecture and best practices.

---

## Security Architecture

### Core Principles

1. **Least Privilege:** Skills only receive minimum required capabilities
2. **Explicit Consent:** High-risk operations require human approval
3. **Audit Trail:** All actions are logged immutably
4. **Isolation:** Untrusted code runs in containers
5. **Defense in Depth:** Multiple security layers

### Security Layers

```
┌─────────────────────────────────────────────────────┐
│                   User Interface                     │
├─────────────────────────────────────────────────────┤
│              Authentication Layer                    │
│         (JWT tokens, trusted users list)            │
├─────────────────────────────────────────────────────┤
│            Capability Validation Layer               │
│         (Capability tokens, risk levels)            │
├─────────────────────────────────────────────────────┤
│              Isolation Layer                         │
│    (main_process, subprocess, container)            │
├─────────────────────────────────────────────────────┤
│            Resource Limiting Layer                   │
│       (CPU, memory, disk, network limits)           │
├─────────────────────────────────────────────────────┤
│               Audit Layer                            │
│          (Immutable audit logging)                   │
└─────────────────────────────────────────────────────┘
```

---

## Capability-Based Security

### Understanding Capabilities

Capabilities are **non-executable tokens** that grant specific permissions. Unlike traditional permissions, capabilities:

- Cannot be forged or transferred
- Are scoped to specific resources
- Have explicit expiration
- Require explicit grant

### Capability Format

```
<domain>:<action>:<scope>
```

### Standard Capabilities

| Capability | Description | Example Scope |
|------------|-------------|---------------|
| `fs:read` | Read files | `/workspace/**` |
| `fs:write` | Write files | `/workspace/project/*` |
| `fs:delete` | Delete files | `/workspace/temp/*` |
| `network:http` | HTTP requests | `*.example.com` |
| `network:websocket` | WebSocket connections | `ws://localhost/*` |
| `os:process` | Run processes | `python, node` |
| `browser:automation` | Browser control | `*` |
| `memory:read` | Read memory | `episodic, semantic` |
| `memory:write` | Write memory | `procedural` |
| `llm:generate` | LLM generation | `gpt-4o, claude-3.5` |

### Capability Examples

```yaml
# File system capabilities
- "fs:read:/workspace/**"           # Read all files in workspace
- "fs:write:/workspace/project/*"  # Write to project directory
- "fs:delete:/workspace/temp/*"    # Delete temp files only

# Network capabilities
- "network:http:api.example.com"   # HTTP to specific domain
- "network:http:*.github.com"      # HTTP to GitHub domains
- "network:websocket:ws://localhost:8080"  # WebSocket to local

# Process capabilities
- "os:process:python"              # Run Python only
- "os:process:node,npm"            # Run Node.js and npm
- "os:process:*"                   # Run any process (dangerous!)

# Browser capabilities
- "browser:automation"             # Full browser automation
- "browser:automation:example.com" # Browser automation for domain
```

### Granting Capabilities

```python
# Via API
POST /api/v1/capabilities/grant
{
  "user_id": "user@example.com",
  "capabilities": [
    "fs:read:/workspace/**",
    "fs:write:/workspace/project/*"
  ],
  "expires_at": "2026-03-20T00:00:00Z",
  "protocol_version": "1.0"
}
```

### Revoking Capabilities

```python
# Via API
POST /api/v1/capabilities/revoke
{
  "user_id": "user@example.com",
  "capabilities": [
    "fs:write:/workspace/project/*"
  ],
  "protocol_version": "1.0"
}
```

---

## Risk Levels

### Risk Level Classification

| Level | Description | Examples | Approval Required |
|-------|-------------|----------|-------------------|
| 1 | Safe | Read file, list directory | No |
| 2 | Low Risk | Write file, web search | No |
| 3 | Moderate Risk | Execute command, API call | Yes (Human) |
| 4 | High Risk | Install package, network access | Yes (Human + Audit) |
| 5 | Critical | System modification, credential access | Yes (Human + Audit + Checkpoint) |

### Risk Level Examples

```yaml
# Risk Level 1 - Safe
skills:
  - name: "read_file"
    risk_level: 1
    capabilities: ["fs:read"]

# Risk Level 2 - Low Risk
skills:
  - name: "write_file"
    risk_level: 2
    capabilities: ["fs:write"]

# Risk Level 3 - Moderate Risk
skills:
  - name: "execute_command"
    risk_level: 3
    capabilities: ["os:process"]
    requires_approval: true

# Risk Level 4 - High Risk
skills:
  - name: "install_package"
    risk_level: 4
    capabilities: ["os:process", "network:http"]
    requires_approval: true
    audit_enabled: true

# Risk Level 5 - Critical
skills:
  - name: "modify_system"
    risk_level: 5
    capabilities: ["os:process", "fs:write:/etc/*"]
    requires_approval: true
    audit_enabled: true
    checkpoint_required: true
```

---

## Isolation Types

### Isolation Enforcement Policy (v3.1)

```yaml
isolation_policy:
  unverified_skills: "container"      # Unverified → container
  risk_level_3_plus: "container"      # Risk ≥ 3 → container
  trusted_skills: "subprocess"        # Trusted → subprocess
  builtin_skills: "main_process"      # Built-in → main process
```

### Isolation Types

| Type | Security Level | Use Case | Overhead |
|------|----------------|----------|----------|
| `main_process` | Low | Built-in trusted skills | None |
| `subprocess` | Medium | Verified skills | Low |
| `container` | High | Unverified or high-risk skills | Medium |

### When Each Type is Used

```python
from core.isolation_policy import IsolationEnforcementPolicy
from skills.base import SkillTrustLevel

# Determine required isolation
isolation = IsolationEnforcementPolicy.get_required_isolation(
    trust_level=SkillTrustLevel.UNVERIFIED,  # unverified, verified, trusted
    risk_level=4
)
# Result: RuntimeIsolationType.CONTAINER
```

---

## Human Approval System

### Approval Workflow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Skill       │────▶│  Risk Check  │────▶│  Approval    │
│  Request     │     │  (Level ≥ 3) │     │  Required?   │
└──────────────┘     └──────────────┘     └──────────────┘
                            │                     │
                            │ Yes                 │ Yes
                            ▼                     ▼
                     ┌──────────────┐     ┌──────────────┐
                     │  Execute     │     │  Wait for    │
                     │  Immediately │     │  Approval    │
                     └──────────────┘     └──────────────┘
```

### Approval Request

```json
{
  "request_id": "apr_123456",
  "skill_name": "execute_command",
  "risk_level": 3,
  "required_capabilities": ["os:process:python"],
  "context": {
    "command": "pip install requests",
    "working_dir": "/workspace"
  },
  "created_at": "2026-02-20T12:00:00Z",
  "expires_at": "2026-02-20T12:30:00Z",
  "protocol_version": "1.0"
}
```

### Approval Response

```json
{
  "request_id": "apr_123456",
  "approved": true,
  "approved_by": "admin@example.com",
  "approved_at": "2026-02-20T12:05:00Z",
  "reason": "Package installation approved for project",
  "protocol_version": "1.0"
}
```

---

## Audit Logging

### Audit Log Format

```json
{
  "timestamp": "2026-02-20T12:00:00.000Z",
  "event_id": "evt_123456",
  "event_type": "skill_execution",
  "user_id": "user@example.com",
  "session_id": "sess_789",
  "trace_id": "trace_abc",
  "action": {
    "type": "file_read",
    "resource": "/workspace/test.txt",
    "skill": "read_file"
  },
  "result": {
    "status": "success",
    "duration_ms": 45
  },
  "security": {
    "capabilities_used": ["fs:read:/workspace/**"],
    "risk_level": 1,
    "isolation_type": "subprocess"
  },
  "protocol_version": "1.0"
}
```

### Audit Log Locations

| Platform | Log Path |
|----------|----------|
| Windows | `%APPDATA%\Synapse\logs\audit.log` |
| macOS | `~/Library/Logs/Synapse/audit.log` |
| Linux | `~/.local/share/synapse/logs/audit.log` |
| Docker | `/var/log/synapse/audit.log` |

### Querying Audit Logs

```bash
# Via API
GET /api/v1/audit?start_date=2026-02-01&end_date=2026-02-20

# Via CLI
synapse audit query --start 2026-02-01 --end 2026-02-20

# Via GUI
# Open Security → Audit Log tab
```

---

## Security Best Practices

### For Users

1. **Start with Supervised Mode**
   ```yaml
   security:
     mode: "supervised"
     require_approval_for_risk: 3
   ```

2. **Review Skill Approvals Carefully**
   - Check required capabilities
   - Verify risk level
   - Review execution context

3. **Regularly Audit Capability Usage**
   ```bash
   synapse audit report --type capabilities
   ```

4. **Keep Audit Logs for Compliance**
   ```yaml
   security:
     audit_log_enabled: true
     audit_retention_days: 90
   ```

5. **Update Trusted Users List Periodically**
   ```yaml
   security:
     trusted_users:
       - "admin@company.com"
   ```

### For Administrators

1. **Enable Audit Logging in Production**
   ```yaml
   security:
     audit_log_enabled: true
     audit_log_path: "/var/log/synapse/audit.log"
   ```

2. **Configure Resource Limits Per User**
   ```yaml
   resources:
     user_limits:
       "user@example.com":
         cpu_seconds: 120
         memory_mb: 1024
   ```

3. **Set Up Alerting for High-Risk Actions**
   ```yaml
   observability:
     alerts:
       - name: "high_risk_action"
         condition: "risk_level >= 4"
         notification: "email"
   ```

4. **Regular Security Reviews**
   ```bash
   # Run security audit
   synapse security audit
   
   # Check for vulnerabilities
   pip install bandit
   bandit -r synapse/ -ll
   ```

5. **Backup Checkpoint Data**
   ```yaml
   reliability:
     checkpoint_enabled: true
     checkpoint_backup_path: "/backup/synapse/checkpoints"
   ```

---

## Security Checklist

### Pre-Production Checklist

- [ ] Enable audit logging
- [ ] Configure trusted users
- [ ] Set risk level thresholds
- [ ] Enable resource limits
- [ ] Configure isolation policy
- [ ] Set up monitoring alerts
- [ ] Test human approval workflow
- [ ] Verify capability grants
- [ ] Review security configuration
- [ ] Document security policies

### Production Checklist

- [ ] Enable TLS/SSL for all endpoints
- [ ] Configure firewall rules
- [ ] Set up VPN for remote access
- [ ] Enable rate limiting
- [ ] Configure CORS properly
- [ ] Enable MFA for admin accounts
- [ ] Encrypt database at rest
- [ ] Set up backup procedures
- [ ] Test recovery procedures
- [ ] Schedule regular security audits

---

## Security Commands

### CLI Commands

```bash
# Check security status
synapse security status

# List capabilities
synapse capabilities list

# Grant capability
synapse capabilities grant --user user@example.com --cap "fs:read:/workspace/**"

# Revoke capability
synapse capabilities revoke --user user@example.com --cap "fs:read:/workspace/**"

# View audit log
synapse audit view --tail 100

# Export audit log
synapse audit export --format json --output audit.json

# Run security audit
synapse security audit
```

---

## Troubleshooting Security Issues

### "Capability check failed"

**Cause:** Missing required capability

**Solution:**
1. Check required capabilities in skill manifest
2. Grant missing capabilities
3. Restart Synapse

### "Human approval timeout"

**Cause:** No response to approval request

**Solution:**
1. Check notification settings
2. Verify approver availability
3. Extend timeout if needed

### "Audit log not writing"

**Cause:** Permission or path issue

**Solution:**
1. Check log path permissions
2. Verify disk space
3. Check log rotation settings

---

## Next Steps

- [Configuration Guide](configuration.md) - Detailed configuration
- [Troubleshooting](troubleshooting.md) - Common issues
- [API Reference](../developer/api.md) - API documentation

---

**Protocol Version:** 1.0  
**Need Help?** Check [Troubleshooting](troubleshooting.md) or open an issue on GitHub.
