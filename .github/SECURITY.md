# 🔐 Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.1.x   | ✅ Active support  |
| 3.0.x   | ✅ Security fixes  |
| < 3.0   | ❌ End of life     |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please follow these steps:

### 🔒 Private Disclosure

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security issues directly to:

**📧 Email:** [evgeniisav@gmail.com](mailto:evgeniisav@gmail.com)

### 📋 What to Include

Please include the following information in your report:

1. **Description** of the vulnerability
2. **Steps to reproduce** the issue
3. **Potential impact** and severity
4. **Affected versions**
5. **Suggested fix** (if available)

### ⏱️ Response Timeline

| Stage | Timeline |
|-------|----------|
| Initial Response | Within 24 hours |
| Vulnerability Confirmation | Within 72 hours |
| Fix Development | 7-14 days |
| Patch Release | Within 30 days |

### 🏆 Recognition

We appreciate security researchers who responsibly disclose vulnerabilities. With your permission, we will:

- Acknowledge your contribution in release notes
- Add you to our security acknowledgments list

## Security Features

### Built-in Security

Synapse includes comprehensive security features:

| Feature | Description |
|---------|-------------|
| **Capability-Based Access** | Every action requires explicit capability token |
| **Zero-Trust Execution** | No implicit trust, verify everything |
| **Isolation Enforcement** | Untrusted code runs in containers |
| **Immutable Audit Log** | All actions logged, cannot be modified |
| **Deterministic Replay** | Every execution reproducible |

### Security Best Practices

When using Synapse:

1. **Never run as root** - Agents should never have root privileges
2. **Use least privilege** - Grant only necessary capabilities
3. **Review generated code** - Always review before approving new skills
4. **Monitor audit logs** - Regularly check for suspicious activity
5. **Keep updated** - Always use the latest version

## Security Configuration

### Environment Variables

```bash
# Security settings
SYNAPSE_SECURITY_LEVEL=high
SYNAPSE_AUDIT_ENABLED=true
SYNAPSE_SANDBOX_ENABLED=true
```

### Capability Configuration

```yaml
security:
  require_approval_for_risk: 3
  trusted_users:
    - admin@example.com
  rate_limit_per_minute: 60
  require_command_signing: true
```

## Contact

**Project Maintainer:** Евгений Савченко

- 📧 Email: [evgeniisav@gmail.com](mailto:evgeniisav@gmail.com)
- 📍 Location: Россия, Саратов
- 🐙 GitHub: [@swatsar](https://github.com/swatsar)

---

**Last Updated:** 2026-02-21
