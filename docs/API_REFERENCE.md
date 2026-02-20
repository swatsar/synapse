# Synapse API Reference

**Version:** 3.1.0  
**Protocol Version:** 1.0

---

## Overview

Synapse provides a comprehensive REST API for interacting with the agent platform. All endpoints return JSON responses with a `protocol_version` field.

**Base URL:** `http://localhost:8000`

---

## Authentication

Currently, the API uses no authentication for local development. For production deployments, configure authentication via the `security.yaml` file.

---

## Endpoints

### Health Check

```
GET /health
```

Returns the health status of the platform.

**Response:**
```json
{
  "status": "healthy",
  "version": "3.1.0",
  "protocol_version": "1.0"
}
```

---

### Metrics

```
GET /metrics
```

Returns Prometheus-compatible metrics.

**Response:**
```json
{
  "metrics": {
    "synapse_tasks_total": 100,
    "synapse_tasks_successful": 95,
    "synapse_llm_tokens_used": 50000
  },
  "protocol_version": "1.0"
}
```

---

### Execute Task

```
POST /task
```

Execute a task on the agent platform.

**Request Body:**
```json
{
  "task": "string",
  "payload": {},
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "status": "completed",
  "result": {},
  "protocol_version": "1.0"
}
```

---

### List Agents

```
GET /agents
```

List all registered agents.

**Response:**
```json
{
  "agents": [
    {
      "id": "planner",
      "type": "planner",
      "status": "active"
    }
  ],
  "protocol_version": "1.0"
}
```

---

### Create Checkpoint

```
POST /checkpoint
```

Create a checkpoint for rollback.

**Request Body:**
```json
{
  "agent_id": "string",
  "session_id": "string"
}
```

**Response:**
```json
{
  "checkpoint_id": "cp_123456",
  "protocol_version": "1.0"
}
```

---

### Execute Rollback

```
POST /rollback
```

Rollback to a previous checkpoint.

**Request Body:**
```json
{
  "checkpoint_id": "cp_123456"
}
```

**Response:**
```json
{
  "status": "rolled_back",
  "protocol_version": "1.0"
}
```

---

### Cluster Status

```
GET /cluster/status
```

Get the status of the distributed cluster.

**Response:**
```json
{
  "status": "operational",
  "nodes": 3,
  "protocol_version": "1.0"
}
```

---

## Error Handling

All errors follow this format:

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "protocol_version": "1.0"
}
```

---

## Protocol Versioning

All API responses include a `protocol_version` field. The current protocol version is `1.0`.

Clients should check this field to ensure compatibility.

---

## Rate Limiting

Default rate limit: 60 requests per minute.

Headers:
- `X-RateLimit-Limit`: Maximum requests per minute
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## WebSocket Support

WebSocket endpoint available at `ws://localhost:8000/ws` for real-time updates.

---

## OpenAPI Specification

Full OpenAPI specification available at:
- JSON: `http://localhost:8000/openapi.json`
- YAML: `http://localhost:8000/openapi.yaml`

---

**Last Updated:** 2026-02-20
