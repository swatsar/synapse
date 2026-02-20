# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.1.x   | :white_check_mark: |
| 3.0.x   | :x:                |
| < 3.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via:

1. **Email:** security@synapse.dev
2. **GitHub Security Advisory:** [Create a security advisory](https://github.com/synapse/synapse/security/advisories/new)

### What to Include

Please include the following information:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Affected versions
- Possible fixes (if known)

### Response Timeline

- **Initial Response:** Within 48 hours
- **Triage:** Within 7 days
- **Fix Development:** Depends on severity
- **Disclosure:** After fix is released

## Security Features

Synapse implements multiple security layers:

1. **Capability-Based Access Control**
   - Non-executable tokens with scoped permissions
   - Fine-grained access control

2. **Isolation Enforcement**
   - Container isolation for untrusted code
   - Subprocess isolation for verified skills

3. **Human-in-the-Loop Approval**
   - Required for high-risk actions (risk_level ≥ 3)
   - Configurable approval policies

4. **Audit Trail**
   - Immutable logging of all actions
   - PostgreSQL-backed audit storage

5. **AST Security Analysis**
   - Static analysis of generated code
   - Dangerous pattern detection

## Security Best Practices

When using Synapse:

1. Never commit secrets to the repository
2. Use environment variables for sensitive configuration
3. Review generated code before approval
4. Keep dependencies updated
5. Run security scans regularly

## Security Updates

Security updates are released as patch versions and announced via:

- GitHub Security Advisories
- Release notes
- Security mailing list

## Contact

For security-related questions, contact: security@synapse.dev
