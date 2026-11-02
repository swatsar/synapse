# API Reference

**Protocol Version:** 1.0  
**Spec Version:** 3.1  
**Base URL:** `http://localhost:8000`

---

## Overview

Synapse provides a RESTful API for programmatic access to all platform features. All requests and responses use JSON format with protocol versioning.

---

## Authentication

### JWT Authentication

All API requests require a valid JWT token:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/skills
```

### Obtaining a Token

```bash
POST /api/v1/auth/token
```

**Request:**
```json
{
  "username": "user@example.com",
  "password": "your_password",
  "protocol_version": "1.0"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "protocol_version": "1.0"
}
```

---

## Common Headers

| Header | Value | Required |
|--------|-------|----------|
| `Authorization` | `Bearer <token>` | Yes |
| `Content-Type` | `application/json` | Yes (POST/PUT) |
| `X-Protocol-Version` | `1.0` | Recommended |
| `X-Trace-ID` | UUID | Optional (for tracing) |

---

## Response Format

### Success Response

```json
{
  "success": true,
  "data": { ... },
  "protocol_version": "1.0",
  "timestamp": "2026-02-20T12:00:00Z"
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "CAPABILITY_DENIED",
    "message": "Missing required capability: fs:read",
    "details": {
      "required_capabilities": ["fs:read:/workspace/**"]
    }
  },
  "protocol_version": "1.0",
  "timestamp": "2026-02-20T12:00:00Z"
}
```

---

## Health Endpoints

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "3.1",
  "protocol_version": "1.0",
  "timestamp": "2026-02-20T12:00:00Z",
  "services": {
    "database": "connected",
    "vector_db": "connected",
    "llm": "available",
    "cache": "connected"
  },
  "uptime_seconds": 86400
}
```

### Readiness Check

```http
GET /ready
```

**Response:**
```json
{
  "ready": true,
  "checks": {
    "database": true,
    "vector_db": true,
    "llm": true,
    "memory": true
  },
  "protocol_version": "1.0"
}
```

### Liveness Check

```http
GET /live
```

**Response:**
```json
{
  "alive": true,
  "protocol_version": "1.0"
}
```

---

## Skills API

### List Skills

```http
GET /api/v1/skills
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (active, pending, deprecated) |
| `trust_level` | string | Filter by trust level |
| `limit` | int | Max results (default: 50) |
| `offset` | int | Pagination offset |

**Response:**
```json
{
  "success": true,
  "data": {
    "skills": [
      {
        "id": "skill_123",
        "name": "read_file",
        "version": "1.0.0",
        "description": "Read file contents",
        "trust_level": "trusted",
        "risk_level": 1,
        "status": "active",
        "required_capabilities": ["fs:read"],
        "protocol_version": "1.0"
      }
    ],
    "total": 25,
    "limit": 50,
    "offset": 0
  },
  "protocol_version": "1.0"
}
```

### Get Skill

```http
GET /api/v1/skills/{skill_id}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "skill_123",
    "name": "read_file",
    "version": "1.0.0",
    "description": "Read file contents",
    "author": "synapse_core",
    "trust_level": "trusted",
    "risk_level": 1,
    "status": "active",
    "required_capabilities": ["fs:read:/workspace/**"],
    "inputs": {
      "path": {
        "type": "string",
        "required": true,
        "description": "File path to read"
      }
    },
    "outputs": {
      "content": {
        "type": "string",
        "description": "File contents"
      }
    },
    "isolation_type": "subprocess",
    "timeout_seconds": 30,
    "protocol_version": "1.0"
  },
  "protocol_version": "1.0"
}
```

### Execute Skill

```http
POST /api/v1/skills/{skill_id}/execute
```

**Request:**
```json
{
  "inputs": {
    "path": "/workspace/test.txt"
  },
  "context": {
    "session_id": "sess_123",
    "trace_id": "trace_456"
  },
  "protocol_version": "1.0"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "execution_id": "exec_789",
    "skill_id": "skill_123",
    "status": "completed",
    "outputs": {
      "content": "Hello, World!"
    },
    "metrics": {
      "execution_time_ms": 45,
      "memory_used_mb": 12
    },
    "protocol_version": "1.0"
  },
  "protocol_version": "1.0"
}
```

### Create Skill (Dynamic)

```http
POST /api/v1/skills
```

**Request:**
```json
{
  "name": "my_custom_skill",
  "description": "Custom skill description",
  "code": "class MyCustomSkill(BaseSkill): ...",
  "manifest": {
    "required_capabilities": ["fs:read"],
    "risk_level": 2,
    "inputs": {"param1": {"type": "string"}},
    "outputs": {"result": {"type": "string"}}
  },
  "protocol_version": "1.0"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "skill_id": "skill_new",
    "status": "pending_approval",
    "message": "Skill submitted for approval",
    "protocol_version": "1.0"
  },
  "protocol_version": "1.0"
}
```

---

## Capabilities API

### List Capabilities

```http
GET /api/v1/capabilities
```

**Response:**
```json
{
  "success": true,
  "data": {
    "capabilities": [
      {
        "id": "cap_123",
        "user_id": "user@example.com",
        "capability": "fs:read:/workspace/**",
        "granted_at": "2026-02-20T12:00:00Z",
        "expires_at": "2026-03-20T12:00:00Z",
        "protocol_version": "1.0"
      }
    ],
    "protocol_version": "1.0"
  }
}
```

### Grant Capability

```http
POST /api/v1/capabilities/grant
```

**Request:**
```json
{
  "user_id": "user@example.com",
  "capabilities": [
    "fs:read:/workspace/**",
    "fs:write:/workspace/project/*"
  ],
  "expires_at": "2026-03-20T00:00:00Z",
  "reason": "Project access",
  "protocol_version": "1.0"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "granted": [
      {
        "capability": "fs:read:/workspace/**",
        "user_id": "user@example.com",
        "granted_at": "2026-02-20T12:00:00Z"
      }
    ],
    "protocol_version": "1.0"
  }
}
```

### Revoke Capability

```http
POST /api/v1/capabilities/revoke
```

**Request:**
```json
{
  "user_id": "user@example.com",
  "capabilities": ["fs:write:/workspace/project/*"],
  "reason": "Access no longer required",
  "protocol_version": "1.0"
}
```

---

## Tasks API

### Create Task

```http
POST /api/v1/tasks
```

**Request:**
```json
{
  "description": "Read the file /workspace/test.txt and summarize it",
  "mode": "supervised",
  "context": {
    "session_id": "sess_123"
  },
  "protocol_version": "1.0"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "task_id": "task_456",
    "status": "pending",
    "created_at": "2026-02-20T12:00:00Z",
    "protocol_version": "1.0"
  }
}
```

### Get Task Status

```http
GET /api/v1/tasks/{task_id}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "task_id": "task_456",
    "status": "completed",
    "description": "Read the file /workspace/test.txt and summarize it",
    "result": {
      "summary": "The file contains..."
    },
    "steps": [
      {
        "step": 1,
        "skill": "read_file",
        "status": "completed"
      },
      {
        "step": 2,
        "skill": "text_analysis",
        "status": "completed"
      }
    ],
    "metrics": {
      "total_time_ms": 1234,
      "tokens_used": 500
    },
    "protocol_version": "1.0"
  }
}
```

---

## Audit API

### Query Audit Log

```http
GET /api/v1/audit
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | string | Start date (ISO 8601) |
| `end_date` | string | End date (ISO 8601) |
| `user_id` | string | Filter by user |
| `event_type` | string | Filter by event type |
| `limit` | int | Max results |

**Response:**
```json
{
  "success": true,
  "data": {
    "events": [
      {
        "event_id": "evt_123",
        "timestamp": "2026-02-20T12:00:00Z",
        "event_type": "skill_execution",
        "user_id": "user@example.com",
        "action": "read_file",
        "resource": "/workspace/test.txt",
        "result": "success",
        "protocol_version": "1.0"
      }
    ],
    "total": 100,
    "protocol_version": "1.0"
  }
}
```

### Get Audit Event

```http
GET /api/v1/audit/{event_id}
```

---

## Memory API

### Store Memory

```http
POST /api/v1/memory
```

**Request:**
```json
{
  "type": "episodic",
  "content": "Successfully completed file analysis task",
  "metadata": {
    "task_id": "task_456",
    "success": true
  },
  "protocol_version": "1.0"
}
```

### Recall Memory

```http
POST /api/v1/memory/recall
```

**Request:**
```json
{
  "query": "file analysis",
  "memory_types": ["episodic", "semantic"],
  "limit": 10,
  "protocol_version": "1.0"
}
```

---

## LLM API

### Get LLM Status

```http
GET /api/v1/llm/status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "providers": [
      {
        "name": "openai",
        "model": "gpt-4o",
        "status": "available",
        "priority": 1,
        "latency_ms": 245
      }
    ],
    "active_provider": "openai",
    "protocol_version": "1.0"
  }
}
```

### Get Token Usage

```http
GET /api/v1/llm/tokens
```

**Response:**
```json
{
  "success": true,
  "data": {
    "total_tokens": 50000,
    "by_provider": {
      "openai": {
        "prompt_tokens": 30000,
        "completion_tokens": 20000
      }
    },
    "cost_usd": 1.25,
    "protocol_version": "1.0"
  }
}
```

---

## Approval API

### List Pending Approvals

```http
GET /api/v1/approvals/pending
```

**Response:**
```json
{
  "success": true,
  "data": {
    "approvals": [
      {
        "request_id": "apr_123",
        "skill_name": "execute_command",
        "risk_level": 3,
        "context": {
          "command": "pip install requests"
        },
        "created_at": "2026-02-20T12:00:00Z",
        "expires_at": "2026-02-20T12:30:00Z",
        "protocol_version": "1.0"
      }
    ],
    "protocol_version": "1.0"
  }
}
```

### Submit Approval

```http
POST /api/v1/approvals/{request_id}/approve
```

**Request:**
```json
{
  "approved": true,
  "reason": "Package installation approved",
  "protocol_version": "1.0"
}
```

### Deny Approval

```http
POST /api/v1/approvals/{request_id}/deny
```

**Request:**
```json
{
  "reason": "Unauthorized package installation",
  "protocol_version": "1.0"
}
```

---

## Metrics API

### Get Metrics

```http
GET /api/v1/metrics
```

**Response:**
```json
{
  "success": true,
  "data": {
    "cpu_percent": 23.5,
    "memory_mb": 512,
    "disk_mb": 1024,
    "network_kb": 2048,
    "active_skills": 2,
    "pending_tasks": 5,
    "protocol_version": "1.0"
  }
}
```

### Prometheus Metrics

```http
GET /metrics
```

Returns Prometheus-compatible metrics.

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Invalid request format |
| `UNAUTHORIZED` | 401 | Missing or invalid token |
| `FORBIDDEN` | 403 | Capability denied |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource conflict |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

---

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| `/api/v1/*` | 60 requests/minute |
| `/api/v1/skills/*/execute` | 30 requests/minute |
| `/api/v1/tasks` | 20 requests/minute |

Headers returned:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1708444800
```

---

## WebSocket API

### Connect

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    channels: ['tasks', 'metrics'],
    protocol_version: '1.0'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

### Channels

| Channel | Events |
|---------|--------|
| `tasks` | Task created, updated, completed |
| `metrics` | Real-time metrics updates |
| `approvals` | Approval requests |
| `audit` | Audit events |

---

## SDK Examples

### Python

```python
from synapse import SynapseClient

client = SynapseClient(
    base_url="http://localhost:8000",
    token="your_token"
)

# Execute skill
result = await client.skills.execute(
    skill_id="read_file",
    inputs={"path": "/workspace/test.txt"}
)

print(result.outputs)
```

### JavaScript

```javascript
const { SynapseClient } = require('synapse-sdk');

const client = new SynapseClient({
  baseUrl: 'http://localhost:8000',
  token: 'your_token'
});

// Execute skill
const result = await client.skills.execute('read_file', {
  path: '/workspace/test.txt'
});

console.log(result.outputs);
```

---

**Protocol Version:** 1.0  
**Need Help?** Check [Troubleshooting](../user/troubleshooting.md) or open an issue on GitHub.
