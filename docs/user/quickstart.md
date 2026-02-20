# Quick Start Guide

**Protocol Version:** 1.0  
**Time to Complete:** 5 minutes  

---

## Overview

This guide will help you get Synapse up and running in 5 minutes. By the end, you'll be able to execute your first autonomous task.

---

## Step 1: Launch Configurator (30 seconds)

### Windows
- Open **Start Menu**
- Click **Synapse Configurator**

### macOS
- Open **Applications** folder
- Double-click **Synapse**

### Linux
- Open terminal and run:
```bash
synapse-gui
```

Or find **Synapse** in your applications menu.

---

## Step 2: LLM Configuration (2 minutes)

### Select Provider

1. Click **"LLM Settings"** tab
2. Select your preferred provider:

| Provider | Models | API Key Required |
|----------|--------|------------------|
| OpenAI | GPT-4o, GPT-4 | Yes |
| Anthropic | Claude 3.5 Sonnet | Yes |
| Ollama | Llama3, Mistral | No (local) |
| Google | Gemini Pro | Yes |

### Enter API Key

```yaml
# Example configuration
provider: openai
api_key: sk-...  # Stored securely
model: gpt-4o
priority: 1
```

### Test Connection

1. Click **"Test Connection"** button
2. Wait for confirmation:
```
✅ Connection successful
Model: gpt-4o
Latency: 245ms
```

---

## Step 3: Security Mode (1 minute)

### Choose Your Mode

| Mode | Description | Best For |
|------|-------------|----------|
| **Safe** | All actions require approval | First-time users |
| **Supervised** | Risk ≥ 3 requires approval | Regular users |
| **Autonomous** | Minimal restrictions | Advanced users |

### Recommended for First Time

```yaml
security:
  mode: "supervised"
  require_approval_for_risk: 3
  audit_log_enabled: true
```

---

## Step 4: First Task (1 minute)

### Via GUI

1. Click **"Tasks"** tab
2. Enter your task:
```
Read the file /workspace/test.txt and summarize it
```
3. Click **"Execute"**

### Via Command Line

```bash
synapse execute "Read the file /workspace/test.txt and summarize it"
```

### Via API

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Read the file /workspace/test.txt and summarize it",
    "protocol_version": "1.0"
  }'
```

---

## Step 5: Monitor Execution (30 seconds)

### Open Dashboard

1. Click **"Dashboard"** tab
2. Watch real-time metrics:

```
┌─────────────────────────────────────┐
│  CPU Usage:    23%                  │
│  Memory:       512 MB               │
│  Tokens Used:  1,234                │
│  Latency:      245ms                │
└─────────────────────────────────────┘
```

### Review Audit Log

1. Click **"Security"** tab
2. View **"Audit Log"**

```
[2026-02-20 12:00:00] Task started
[2026-02-20 12:00:01] Capability check: fs:read ✓
[2026-02-20 12:00:02] Skill executed: read_file
[2026-02-20 12:00:03] Task completed
```

---

## Common First Tasks

### File Operations
```
"Read all Python files in /workspace and list their imports"
```

### Web Research
```
"Search for the latest Python 3.12 features and summarize them"
```

### Code Generation
```
"Create a Python script that reads a CSV file and generates a bar chart"
```

### Data Analysis
```
"Analyze the sales data in /workspace/sales.csv and find trends"
```

### Email Drafting
```
"Draft a professional email to schedule a meeting with the team"
```

---

## Understanding the Workflow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Input      │────▶│   Planner    │────▶│   Executor   │
│   (Task)     │     │   (Plan)     │     │   (Action)   │
└──────────────┘     └──────────────┘     └──────────────┘
                            │                     │
                            ▼                     ▼
                     ┌──────────────┐     ┌──────────────┐
                     │   Critic     │◀────│   Result     │
                     │   (Review)   │     │   (Output)   │
                     └──────────────┘     └──────────────┘
```

### Step-by-Step

1. **Input:** You provide a task description
2. **Planner:** Creates a step-by-step plan
3. **Security Check:** Validates capabilities
4. **Executor:** Runs the plan
5. **Critic:** Reviews the results
6. **Learning:** Stores successful patterns

---

## Security Features

### Capability Checks

Every action requires appropriate capabilities:

```python
# Example: Reading a file
required_capabilities = ["fs:read:/workspace/**"]

# Security check
if not has_capabilities(required_capabilities):
    raise CapabilityError("Missing fs:read capability")
```

### Risk Levels

| Level | Example Actions | Approval |
|-------|-----------------|----------|
| 1 | Read file | Auto |
| 2 | Write file | Auto |
| 3 | Execute command | Human |
| 4 | Network access | Human + Audit |
| 5 | System modification | Human + Audit + Checkpoint |

### Audit Trail

All actions are logged:

```json
{
  "timestamp": "2026-02-20T12:00:00Z",
  "action": "file_read",
  "user": "user@example.com",
  "resource": "/workspace/test.txt",
  "result": "success",
  "protocol_version": "1.0"
}
```

---

## Next Steps

### Learn More
- [Configuration Guide](configuration.md) - Detailed settings
- [Security Guide](security.md) - Security best practices
- [API Reference](../developer/api.md) - API documentation

### Try Advanced Tasks
- Create custom skills
- Configure multiple LLM providers
- Set up distributed execution
- Integrate with external services

### Join the Community
- GitHub Discussions
- Telegram Channel
- Discord Server

---

## Troubleshooting

### "LLM connection failed"
```bash
# Check API key
echo $OPENAI_API_KEY

# Test connection
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### "Capability check failed"
1. Open **Security Settings**
2. Review required capabilities
3. Grant necessary permissions

### "Task timeout"
1. Check resource limits in config
2. Increase timeout if needed
3. Simplify the task

---

**Protocol Version:** 1.0  
**Need Help?** Check [Troubleshooting](troubleshooting.md) or open an issue on GitHub.
