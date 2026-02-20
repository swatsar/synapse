# Security Hardening Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## Overview

This guide provides comprehensive security hardening procedures for production deployments of Synapse.

---

## Security Architecture

### Defense in Depth

```
┌─────────────────────────────────────────────────────────────┐
│                     Network Layer                           │
│  Firewall | TLS | Rate Limiting | VPN                       │
├─────────────────────────────────────────────────────────────┤
│                     Application Layer                       │
│  Authentication | Authorization | Input Validation          │
├─────────────────────────────────────────────────────────────┤
│                     Capability Layer                        │
│  Capability Tokens | Isolation Policy | Audit Logging       │
├─────────────────────────────────────────────────────────────┤
│                     Data Layer                              │
│  Encryption | Access Control | Backup                      │
├─────────────────────────────────────────────────────────────┤
│                     Container Layer                         │
│  Non-root | Resource Limits | Network Policies             │
└─────────────────────────────────────────────────────────────┘
```

---

## Production Security Checklist

### Network Security

- [ ] **Enable TLS/SSL for all endpoints**
  ```yaml
  # nginx.conf
  server {
      listen 443 ssl http2;
      ssl_certificate /etc/ssl/certs/synapse.crt;
      ssl_certificate_key /etc/ssl/private/synapse.key;
      ssl_protocols TLSv1.2 TLSv1.3;
      ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
  }
  ```

- [ ] **Configure firewall rules**
  ```bash
  # UFW (Ubuntu)
  sudo ufw default deny incoming
  sudo ufw default allow outgoing
  sudo ufw allow 22/tcp    # SSH
  sudo ufw allow 443/tcp   # HTTPS
  sudo ufw allow 8000/tcp  # Synapse API (internal only)
  sudo ufw enable
  ```

- [ ] **Set up VPN for remote access**
  ```bash
  # WireGuard example
  sudo apt install wireguard
  # Configure /etc/wireguard/wg0.conf
  sudo systemctl enable wg-quick@wg0
  ```

- [ ] **Enable rate limiting**
  ```yaml
  # config.yaml
  security:
    rate_limiting:
      enabled: true
      requests_per_minute: 60
      burst: 100
  ```

- [ ] **Configure CORS properly**
  ```yaml
  # config.yaml
  api:
    cors:
      allowed_origins:
        - "https://synapse.example.com"
      allowed_methods:
        - GET
        - POST
        - PUT
        - DELETE
      allowed_headers:
        - Authorization
        - Content-Type
        - X-Protocol-Version
  ```

### Access Control

- [ ] **Enable MFA for admin accounts**
  ```yaml
  # config.yaml
  security:
    mfa:
      enabled: true
      methods:
        - totp
        - webauthn
      required_for_roles:
        - admin
        - operator
  ```

- [ ] **Review trusted users list**
  ```yaml
  # config.yaml
  security:
    trusted_users:
      - "admin@company.com"
      - "operator@company.com"
    approval_required_for_new_users: true
  ```

- [ ] **Audit capability grants**
  ```bash
  # Check capability grants
  synapse capabilities list --all-users
  
  # Revoke unused capabilities
  synapse capabilities revoke --user user@example.com --capability "fs:write"
  ```

- [ ] **Set up role-based access**
  ```yaml
  # config.yaml
  security:
    roles:
      admin:
        capabilities:
          - "*"
        approval_bypass: true
      operator:
        capabilities:
          - "fs:read:/workspace/**"
          - "fs:write:/workspace/**"
          - "network:http"
        approval_bypass: false
      viewer:
        capabilities:
          - "fs:read:/workspace/**"
        approval_bypass: false
  ```

- [ ] **Enable session timeout**
  ```yaml
  # config.yaml
  security:
    session:
      timeout_minutes: 30
      max_concurrent_sessions: 3
      idle_timeout_minutes: 15
  ```

### Data Protection

- [ ] **Encrypt database at rest**
  ```yaml
  # PostgreSQL
  # Enable transparent data encryption
  ALTER SYSTEM SET encrypt = on;
  
  # Or use LUKS for disk encryption
  sudo cryptsetup luksFormat /dev/sdb
  sudo cryptsetup luksOpen /dev/sdb encrypted_db
  ```

- [ ] **Enable audit logging**
  ```yaml
  # config.yaml
  security:
    audit:
      enabled: true
      log_path: "/var/log/synapse/audit.log"
      retention_days: 90
      log_level: "INFO"
      include:
        - authentication
        - capability_checks
        - skill_executions
        - configuration_changes
  ```

- [ ] **Configure log retention**
  ```yaml
  # config.yaml
  logging:
    retention:
      audit_logs: 90d
      application_logs: 30d
      debug_logs: 7d
    rotation:
      max_size_mb: 100
      max_files: 10
  ```

- [ ] **Set up backup procedures**
  ```bash
  #!/bin/bash
  # backup.sh
  BACKUP_DIR="/backup/synapse"
  DATE=$(date +%Y%m%d_%H%M%S)
  
  # Database
  pg_dump -U synapse synapse | gzip > $BACKUP_DIR/db_$DATE.sql.gz
  
  # Vector DB
  curl -X POST http://localhost:6333/collections/synapse/snapshots
  
  # Config
  tar -czf $BACKUP_DIR/config_$DATE.tar.gz /opt/synapse/config
  
  # Encrypt backup
  gpg --encrypt --recipient admin@company.com $BACKUP_DIR/db_$DATE.sql.gz
  
  # Upload to secure storage
  aws s3 cp $BACKUP_DIR/ s3://synapse-backups/ --recursive
  ```

- [ ] **Test recovery procedures**
  ```bash
  # Test restore
  gunzip -c /backup/synapse/db_20260220.sql.gz | psql -U synapse synapse
  
  # Verify
  synapse health check
  ```

### Container Security

- [ ] **Run as non-root user**
  ```dockerfile
  # Dockerfile
  FROM python:3.11-slim
  
  RUN useradd -r -s /bin/false synapse
  
  COPY --chown=synapse:synapse . /app
  
  USER synapse
  WORKDIR /app
  
  CMD ["python", "-m", "synapse.main"]
  ```

- [ ] **Enable resource limits**
  ```yaml
  # docker-compose.yml
  services:
    synapse:
      deploy:
        resources:
          limits:
            cpus: '2.0'
            memory: 4G
          reservations:
            cpus: '1.0'
            memory: 2G
  ```

- [ ] **Scan images for vulnerabilities**
  ```bash
  # Trivy scan
  trivy image synapse/core:3.1.0
  
  # Docker scan
  docker scan synapse/core:3.1.0
  ```

- [ ] **Use read-only filesystem where possible**
  ```yaml
  # docker-compose.yml
  services:
    synapse:
      read_only: true
      tmpfs:
        - /tmp
        - /var/run
  ```

- [ ] **Enable network policies**
  ```yaml
  # Kubernetes NetworkPolicy
  apiVersion: networking.k8s.io/v1
  kind: NetworkPolicy
  metadata:
    name: synapse-network-policy
  spec:
    podSelector:
      matchLabels:
        app: synapse
    policyTypes:
    - Ingress
    - Egress
    ingress:
    - from:
      - podSelector:
          matchLabels:
            role: frontend
      ports:
      - port: 8000
    egress:
    - to:
      - podSelector:
          matchLabels:
            role: database
      ports:
      - port: 5432
  ```

---

## Security Audit Commands

### Code Security

```bash
# Bandit - Python security linter
pip install bandit
bandit -r synapse/ -ll -f json -o security_report.json

# Safety - Check dependencies for vulnerabilities
pip install safety
safety check --json

# Semgrep - Advanced security analysis
pip install semgrep
semgrep --config=auto synapse/
```

### Container Security

```bash
# Trivy - Container vulnerability scanner
trivy image synapse/core:3.1.0

# Grype - Another vulnerability scanner
grype synapse/core:3.1.0

# Docker Bench Security
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  docker/docker-bench-security
```

### Infrastructure Security

```bash
# Check open ports
sudo netstat -tulpn | grep LISTEN

# Check running services
sudo systemctl list-units --type=service --state=running

# Check firewall status
sudo ufw status verbose

# Check SSL certificate
openssl s_client -connect synapse.example.com:443 -servername synapse.example.com
```

---

## Capability Security Model

### Understanding Capabilities

| Capability | Risk Level | Description |
|------------|------------|-------------|
| `fs:read` | Low | Read file system |
| `fs:write` | Medium | Write to file system |
| `network:http` | Medium | HTTP requests |
| `os:process` | High | Execute processes |
| `browser:automation` | High | Browser control |
| `database:admin` | Critical | Database administration |

### Capability Patterns

```yaml
# Specific path
capabilities:
  - "fs:read:/workspace/project/**"

# Specific domain
capabilities:
  - "network:http:api.example.com/*"

# Specific command
capabilities:
  - "os:process:python"

# Wildcard (admin only)
capabilities:
  - "*"
```

### Capability Validation

```python
# Always validate capabilities
async def execute_skill(skill, context):
    # Check capabilities
    for required in skill.required_capabilities:
        if not matches_capability(required, context.capabilities):
            raise CapabilityError(f"Missing: {required}")
    
    # Log capability check
    await audit_log(
        event="capability_check",
        required=skill.required_capabilities,
        granted=context.capabilities,
        protocol_version="1.0"
    )
```

---

## Isolation Policy Enforcement

### Risk Level Mapping

| Risk Level | Isolation Type | Use Case |
|------------|----------------|----------|
| 1 | subprocess | Safe operations |
| 2 | subprocess | Moderate risk |
| 3 | container | High risk |
| 4 | container | Very high risk |
| 5 | container + approval | Critical operations |

### Enforcement Rules

```yaml
# config.yaml
isolation_policy:
  # Unverified skills always in container
  unverified_skills: container
  
  # Risk level 3+ always in container
  risk_level_3_plus: container
  
  # Trusted skills can use subprocess
  trusted_skills: subprocess
  
  # Built-in skills can run in main process
  builtin_skills: main_process
```

---

## Audit Logging

### Log Format

```json
{
  "timestamp": "2026-02-20T12:00:00Z",
  "event_type": "skill_execution",
  "event_id": "evt_123",
  "user_id": "user@example.com",
  "session_id": "sess_456",
  "trace_id": "trace_789",
  "action": "read_file",
  "resource": "/workspace/test.txt",
  "result": "success",
  "risk_level": 1,
  "isolation_type": "subprocess",
  "capabilities_used": ["fs:read:/workspace/**"],
  "execution_time_ms": 45,
  "protocol_version": "1.0"
}
```

### Audit Events

| Event Type | Description | Retention |
|------------|-------------|-----------|
| `authentication` | Login/logout | 1 year |
| `capability_check` | Capability validation | 90 days |
| `skill_execution` | Skill runs | 90 days |
| `approval_request` | Human approval | 1 year |
| `configuration_change` | Config updates | 1 year |
| `security_event` | Security alerts | 1 year |

---

## Incident Response

### Security Incident Checklist

1. **Identify**
   - Check audit logs
   - Review security alerts
   - Identify affected systems

2. **Contain**
   - Isolate affected containers
   - Revoke compromised capabilities
   - Block suspicious IPs

3. **Eradicate**
   - Remove malicious code
   - Patch vulnerabilities
   - Update security rules

4. **Recover**
   - Restore from backup
   - Verify system integrity
   - Resume operations

5. **Post-Incident**
   - Document incident
   - Update security procedures
   - Conduct security review

### Emergency Commands

```bash
# Revoke all capabilities for user
synapse capabilities revoke --user compromised@user.com --all

# Disable skill
synapse skills disable malicious_skill

# Rollback to checkpoint
synapse rollback --checkpoint-id cp_123

# Lockdown mode
synapse security lockdown --enable
```

---

## Compliance

### SOC 2 Requirements

- [ ] Access controls implemented
- [ ] Audit logging enabled
- [ ] Encryption at rest and in transit
- [ ] Incident response procedures
- [ ] Regular security assessments

### GDPR Requirements

- [ ] Data encryption
- [ ] Access controls
- [ ] Audit trails
- [ ] Data retention policies
- [ ] Right to erasure

---

## Security Monitoring

### Prometheus Alerts

```yaml
# alerting.yml
groups:
  - name: security
    rules:
      - alert: MultipleFailedLogins
        expr: increase(synapse_auth_failures_total[5m]) > 5
        labels:
          severity: warning
        annotations:
          summary: "Multiple failed login attempts"

      - alert: CapabilityDenied
        expr: increase(synapse_capability_denied_total[5m]) > 10
        labels:
          severity: warning
        annotations:
          summary: "High rate of capability denials"

      - alert: UnusualSkillExecution
        expr: rate(synapse_skill_executions_total[5m]) > 10
        labels:
          severity: info
        annotations:
          summary: "Unusual skill execution rate"
```

### Grafana Dashboard

Import dashboard from `grafana/dashboards/security.json`

---

## Regular Security Tasks

### Daily
- [ ] Review security alerts
- [ ] Check audit logs for anomalies
- [ ] Verify backup completion

### Weekly
- [ ] Review capability grants
- [ ] Check for security updates
- [ ] Verify SSL certificates

### Monthly
- [ ] Run vulnerability scans
- [ ] Review access controls
- [ ] Test recovery procedures

### Quarterly
- [ ] Security assessment
- [ ] Penetration testing
- [ ] Compliance audit

---

**Protocol Version:** 1.0  
**Need Help?** Check [Troubleshooting](../user/troubleshooting.md) or contact security team.
