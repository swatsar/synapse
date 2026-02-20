# Configuration Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## Overview

Synapse configuration is managed through YAML files and the GUI Configurator. This guide covers all configuration options and their effects.

---

## Configuration Files

### File Locations

| Platform | Config Path |
|----------|-------------|
| Windows | `%APPDATA%\Synapse\config\` |
| macOS | `~/.config/synapse/` |
| Linux | `~/.config/synapse/` |
| Docker | `/app/config/` (mounted volume) |

### Main Configuration Files

```
config/
├── config.yaml           # Main configuration
├── security.yaml         # Security settings
├── llm_providers.yaml    # LLM provider configuration
├── skills.yaml           # Skill settings
└── environments/
    ├── local.yaml        # Local environment
    ├── docker.yaml       # Docker environment
    └── distributed.yaml  # Distributed environment
```

---

## Main Configuration (config.yaml)

### Complete Example

```yaml
# config/config.yaml
# Synapse Main Configuration
# Protocol Version: 1.0

system:
  name: "Synapse"
  version: "3.1"
  mode: "autonomous"  # autonomous, supervised, safe
  protocol_version: "1.0"  # Required - DO NOT CHANGE

# LLM Configuration
llm:
  default_provider: "openai"
  models:
    - name: "gpt-4o"
      provider: "openai"
      priority: 1  # IntEnum: 1=PRIMARY, 2=FALLBACK, 3=SAFE
      timeout_seconds: 30
      max_tokens: 4096
    - name: "claude-3.5-sonnet"
      provider: "anthropic"
      priority: 2
      timeout_seconds: 30
    - name: "llama3"
      provider: "ollama"
      priority: 3
      timeout_seconds: 60

# Memory Configuration
memory:
  vector_db: "chromadb"
  url: "http://localhost:8000"
  sql_db: "postgresql://user:pass@localhost:5432/synapse"
  cache:
    enabled: true
    ttl_seconds: 3600
  consolidation:
    enabled: true
    interval_seconds: 300
    threshold: 100

# Security Configuration
security:
  require_approval_for_risk: 3
  trusted_users:
    - "admin@company.com"
  rate_limit_per_minute: 60
  require_command_signing: true
  audit_log_enabled: true
  audit_log_path: "/var/log/synapse/audit.log"

# Isolation Policy (v3.1)
isolation_policy:
  unverified_skills: "container"
  risk_level_3_plus: "container"
  trusted_skills: "subprocess"

# Resource Limits
resources:
  default_limits:
    cpu_seconds: 60
    memory_mb: 512
    disk_mb: 100
    network_kb: 1024
  max_concurrent_skills: 5

# Time Synchronization (v3.1)
time_sync:
  enabled: true
  core_authority: true
  sync_interval_seconds: 30
  max_offset_ms: 1000

# Observability
observability:
  metrics_enabled: true
  prometheus_port: 9090
  tracing_enabled: true
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR

# Connectors
connectors:
  telegram:
    enabled: false
    token: "${TELEGRAM_BOT_TOKEN}"
  discord:
    enabled: false
    token: "${DISCORD_BOT_TOKEN}"
```

---

## System Configuration

### System Section

```yaml
system:
  name: "Synapse"           # Instance name
  version: "3.1"            # Version (read-only)
  mode: "autonomous"        # Execution mode
  protocol_version: "1.0"   # Protocol version (REQUIRED)
```

### Execution Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `safe` | All actions require approval | Testing, first-time users |
| `supervised` | Risk ≥ 3 requires approval | Production |
| `autonomous` | Minimal restrictions | Advanced users, trusted environments |

---

## LLM Configuration

### Provider Configuration

```yaml
llm:
  default_provider: "openai"
  models:
    - name: "gpt-4o"
      provider: "openai"
      priority: 1
      timeout_seconds: 30
      max_tokens: 4096
      temperature: 0.7
```

### Priority System (IntEnum)

| Priority | Value | Description |
|----------|-------|-------------|
| PRIMARY | 1 | Primary model |
| FALLBACK | 2 | Fallback when primary fails |
| SAFE | 3 | Safe fallback for critical operations |

### Supported Providers

| Provider | Models | API Key Required |
|----------|--------|------------------|
| OpenAI | GPT-4o, GPT-4, GPT-3.5 | Yes |
| Anthropic | Claude 3.5 Sonnet, Claude 3 | Yes |
| Ollama | Llama3, Mistral, etc. | No (local) |
| Google | Gemini Pro | Yes |
| Azure OpenAI | GPT models | Yes |

### LLM Failure Strategy

```yaml
llm:
  failure_strategy:
    max_retries: 3
    retry_delay_seconds: 5
    fallback_enabled: true
    safe_fallback_enabled: true
```

---

## Memory Configuration

### Vector Database

```yaml
memory:
  vector_db: "chromadb"  # chromadb, qdrant, pinecone
  url: "http://localhost:8000"
  collection: "synapse_memory"
```

### SQL Database

```yaml
memory:
  sql_db: "postgresql://user:pass@localhost:5432/synapse"
  # Or SQLite for local:
  sql_db: "sqlite:///data/synapse.db"
```

### Cache Configuration

```yaml
memory:
  cache:
    enabled: true
    ttl_seconds: 3600
    max_size_mb: 256
```

### Consolidation Settings

```yaml
memory:
  consolidation:
    enabled: true
    interval_seconds: 300
    threshold: 100
    remove_duplicates: true
    reinforce_patterns: true
```

---

## Security Configuration

### Capability-Based Security

```yaml
security:
  require_approval_for_risk: 3
  trusted_users:
    - "admin@company.com"
    - "operator@company.com"
```

### Rate Limiting

```yaml
security:
  rate_limit_per_minute: 60
  rate_limit_per_hour: 1000
```

### Audit Logging

```yaml
security:
  audit_log_enabled: true
  audit_log_path: "/var/log/synapse/audit.log"
  audit_retention_days: 90
```

### Command Signing

```yaml
security:
  require_command_signing: true
  signing_key_path: "/etc/synapse/signing_key.pem"
```

---

## Isolation Policy (v3.1)

### Policy Rules

```yaml
isolation_policy:
  unverified_skills: "container"      # Unverified → container
  risk_level_3_plus: "container"      # Risk ≥ 3 → container
  trusted_skills: "subprocess"        # Trusted → subprocess
  builtin_skills: "main_process"      # Built-in → main process
```

### Isolation Types

| Type | Security Level | Use Case |
|------|----------------|----------|
| `main_process` | Low | Built-in trusted skills |
| `subprocess` | Medium | Verified skills |
| `container` | High | Unverified or high-risk skills |

---

## Resource Limits

### Default Limits

```yaml
resources:
  default_limits:
    cpu_seconds: 60      # Maximum CPU time per skill
    memory_mb: 512       # Maximum memory per skill
    disk_mb: 100         # Maximum disk usage per skill
    network_kb: 1024     # Maximum network transfer per skill
```

### Global Limits

```yaml
resources:
  max_concurrent_skills: 5
  total_memory_mb: 4096
  total_cpu_percent: 80
```

---

## Time Synchronization (v3.1)

### Core Time Authority

```yaml
time_sync:
  enabled: true
  core_authority: true
  sync_interval_seconds: 30
  max_offset_ms: 1000
```

### Distributed Configuration

```yaml
time_sync:
  core_node: "node-1"
  node_id: "node-2"
  heartbeat_interval_seconds: 10
```

---

## Observability Configuration

### Metrics

```yaml
observability:
  metrics_enabled: true
  prometheus_port: 9090
  metrics_path: "/metrics"
```

### Tracing

```yaml
observability:
  tracing_enabled: true
  trace_sample_rate: 1.0
  jaeger_endpoint: "http://localhost:14268/api/traces"
```

### Logging

```yaml
observability:
  log_level: "INFO"
  log_format: "json"  # json, text
  log_path: "/var/log/synapse/"
```

---

## Connector Configuration

### Telegram

```yaml
connectors:
  telegram:
    enabled: true
    token: "${TELEGRAM_BOT_TOKEN}"
    allowed_users:
      - 123456789
    rate_limit_per_minute: 30
```

### Discord

```yaml
connectors:
  discord:
    enabled: true
    token: "${DISCORD_BOT_TOKEN}"
    guild_id: "123456789"
    allowed_channels:
      - "general"
```

---

## Environment-Specific Configuration

### Local Development

```yaml
# config/environments/local.yaml
system:
  mode: "safe"

llm:
  default_provider: "ollama"

memory:
  sql_db: "sqlite:///data/synapse.db"
  vector_db: "chromadb"

security:
  require_approval_for_risk: 1
```

### Docker

```yaml
# config/environments/docker.yaml
system:
  mode: "supervised"

llm:
  default_provider: "openai"

memory:
  sql_db: "postgresql://db:5432/synapse"
  vector_db: "qdrant"

security:
  require_approval_for_risk: 3
```

### Distributed

```yaml
# config/environments/distributed.yaml
system:
  mode: "autonomous"

time_sync:
  enabled: true
  core_authority: true

memory:
  distributed: true
  replication_factor: 3
```

---

## GUI Configuration

### Accessing Settings

1. Launch GUI Configurator
2. Navigate to **Settings** tab
3. Configure categories:
   - LLM Settings
   - Security Settings
   - Memory Settings
   - Resource Limits

### LLM Settings

- Provider selection
- API key management (encrypted storage)
- Model priority configuration
- Fallback settings

### Security Settings

- Capability token management
- Trusted users list
- Risk level thresholds
- Audit log retention

---

## Environment Variables

### Supported Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SYNAPSE_ENV` | Environment name | `local` |
| `DATABASE_URL` | PostgreSQL connection | Required |
| `VECTOR_DB_URL` | Vector DB connection | Required |
| `PROTOCOL_VERSION` | Protocol version | `1.0` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |

### Example .env

```bash
# .env
SYNAPSE_ENV=production
DATABASE_URL=postgresql://user:pass@localhost:5432/synapse
VECTOR_DB_URL=http://localhost:6333
PROTOCOL_VERSION=1.0
LOG_LEVEL=INFO

# LLM Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Validation

### Configuration Validation

```bash
# Validate configuration
synapse --validate-config

# Output:
# ✅ config.yaml: Valid
# ✅ security.yaml: Valid
# ✅ llm_providers.yaml: Valid
```

### Common Validation Errors

| Error | Solution |
|-------|----------|
| Missing protocol_version | Add `protocol_version: "1.0"` |
| Invalid isolation_type | Use: main_process, subprocess, container |
| Invalid priority | Use: 1, 2, 3 (IntEnum) |
| Missing required field | Check spec for required fields |

---

## Next Steps

- [Security Guide](security.md) - Security best practices
- [API Reference](../developer/api.md) - API documentation
- [Troubleshooting](troubleshooting.md) - Common issues

---

**Protocol Version:** 1.0  
**Need Help?** Check [Troubleshooting](troubleshooting.md) or open an issue on GitHub.
