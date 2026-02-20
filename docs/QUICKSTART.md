# Synapse Quick Start Guide

**Get started with Synapse in 5 minutes**  
**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## ⚡ Prerequisites

- Python 3.11+
- OpenAI or Anthropic API key

---

## 🚀 5-Minute Setup

### Step 1: Install (1 minute)

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install Synapse
pip install synapse-platform
```

### Step 2: Configure (2 minutes)

Create `.env` file:

```bash
# Required
OPENAI_API_KEY=sk-your-key-here

# Optional
ANTHROPIC_API_KEY=sk-ant-your-key-here
DATABASE_URL=postgresql://localhost/synapse
```

### Step 3: Run (1 minute)

```bash
# Start Synapse
synapse start

# Or with Python
python -m synapse.main
```

### Step 4: Verify (1 minute)

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "3.1", "protocol_version": "1.0"}
```

---

## 🎯 Your First Task

### Using the API

```python
import requests

# Send a task to Synapse
response = requests.post(
    "http://localhost:8000/api/v1/task",
    json={
        "task": "Read the file /workspace/example.txt and summarize it",
        "session_id": "my-first-session",
        "protocol_version": "1.0"
    }
)

print(response.json())
```

### Using Python SDK

```python
from synapse import SynapseClient

# Initialize client
client = SynapseClient(api_key="your-api-key")

# Execute a task
result = await client.execute(
    task="Analyze the data in /workspace/data.csv",
    capabilities=["fs:read:/workspace/**"]
)

print(result)
```

---

## 📚 Core Concepts

### Capabilities

Synapse uses capability-based security:

```python
# File system access
"fs:read:/workspace/**"    # Read files in workspace
"fs:write:/workspace/**"   # Write files in workspace

# Network access
"network:http"             # HTTP requests

# Process execution
"os:process"               # Run subprocesses
```

### Risk Levels

| Level | Description | Approval Required |
|-------|-------------|-------------------|
| 1 | Low risk (read operations) | No |
| 2 | Medium risk (write operations) | No |
| 3 | High risk (network/process) | Yes |
| 4 | Critical risk (system changes) | Yes |
| 5 | Maximum risk (destructive) | Yes + Admin |

### Isolation Types

```python
# Automatic sandboxing based on risk
RuntimeIsolationType.SUBPROCESS  # Light isolation
RuntimeIsolationType.CONTAINER   # Full container isolation
```

---

## 🔧 Common Tasks

### Read a File

```python
result = await client.execute(
    task="Read /workspace/document.txt",
    capabilities=["fs:read:/workspace/**"]
)
```

### Write a File

```python
result = await client.execute(
    task="Write 'Hello World' to /workspace/output.txt",
    capabilities=["fs:write:/workspace/**"]
)
```

### Web Search

```python
result = await client.execute(
    task="Search for 'Python best practices'",
    capabilities=["network:http"]
)
```

---

## 🐳 Docker Quick Start

```bash
# Pull and run
docker run -d \
  --name synapse \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key \
  synapse/platform:3.1

# Check logs
docker logs -f synapse
```

---

## 📊 Monitoring

### Prometheus Metrics

```bash
# Access metrics
curl http://localhost:9090/metrics
```

### Key Metrics

- `synapse_tasks_total` - Total tasks executed
- `synapse_task_duration_seconds` - Task execution time
- `synapse_llm_token_usage_total` - LLM token usage
- `synapse_security_checks_total` - Security check results

---

## 🛡️ Security Best Practices

1. **Always specify capabilities** - Never grant more than needed
2. **Use human approval for high-risk tasks** - Required for risk_level >= 3
3. **Monitor audit logs** - Check `/var/log/synapse/audit.log`
4. **Keep API keys secure** - Use environment variables

---

## 📖 Next Steps

- [Full Installation Guide](INSTALLATION_GUIDE.md)
- [Security Guide](SECURITY_GUIDE.md)
- [API Reference](API_REFERENCE.md)
- [Troubleshooting](TROUBLESHOOTING.md)

---

## 💡 Tips

- Use `protocol_version="1.0"` in all API calls
- Check `/health` endpoint before deploying
- Monitor resource usage with Prometheus
- Review audit logs regularly

---

**Protocol Version:** 1.0  
**Spec Version:** 3.1
