# Monitoring Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## Overview

This guide covers monitoring, alerting, and observability for Synapse production deployments.

---

## Monitoring Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Grafana Dashboards                       │
│  System | Application | LLM | Security | Business          │
├─────────────────────────────────────────────────────────────┤
│                    Prometheus                               │
│  Metrics Collection | Alerting | Service Discovery          │
├─────────────────────────────────────────────────────────────┤
│                    Synapse Core                             │
│  /metrics endpoint | Custom metrics | Protocol versioning   │
└─────────────────────────────────────────────────────────────┘
```

---

## Prometheus Setup

### Configuration

```yaml
# docker/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'synapse'
    protocol_version: '1.0'

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

rule_files:
  - /etc/prometheus/alerting.yml

scrape_configs:
  # Synapse Core
  - job_name: 'synapse'
    static_configs:
      - targets: ['synapse-core:9090']
    metrics_path: /metrics
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance

  # PostgreSQL
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Redis
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  # Qdrant
  - job_name: 'qdrant'
    static_configs:
      - targets: ['qdrant:6333']

  # Node Exporter (system metrics)
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Alert Rules

```yaml
# docker/alerting.yml
groups:
  - name: synapse_availability
    rules:
      - alert: SynapseDown
        expr: up{job="synapse"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Synapse is down"
          description: "Synapse has been down for more than 1 minute."

      - alert: SynapseHighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High request latency"
          description: "95th percentile latency is above 2 seconds."

  - name: synapse_errors
    rules:
      - alert: HighErrorRate
        expr: rate(synapse_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is above 10% for the last 5 minutes."

      - alert: CapabilityDeniedSpike
        expr: rate(synapse_capability_denied_total[5m]) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Spike in capability denials"
          description: "Unusual number of capability denials detected."

  - name: synapse_resources
    rules:
      - alert: HighMemoryUsage
        expr: synapse_memory_usage_bytes / synapse_memory_limit_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Memory usage above 90%"
          description: "Consider increasing memory limits."

      - alert: HighCPUUsage
        expr: rate(process_cpu_seconds_total{job="synapse"}[5m]) > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "CPU usage above 90%"
          description: "Consider scaling horizontally."

  - name: synapse_llm
    rules:
      - alert: LLMLatencyHigh
        expr: histogram_quantile(0.95, rate(synapse_llm_latency_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "LLM latency above 5 seconds"
          description: "LLM responses are slow."

      - alert: LLMTokenUsageHigh
        expr: rate(synapse_llm_token_usage_total[1h]) > 100000
        for: 1h
        labels:
          severity: info
        annotations:
          summary: "High token usage"
          description: "Token usage is above 100k per hour."

      - alert: LLMProviderDown
        expr: synapse_llm_provider_available == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "LLM provider unavailable"
          description: "Primary LLM provider is down."

  - name: synapse_skills
    rules:
      - alert: SkillExecutionFailures
        expr: rate(synapse_skill_executions_failed_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High skill failure rate"
          description: "More than 5% of skill executions are failing."

      - alert: SkillTimeouts
        expr: rate(synapse_skill_timeouts_total[5m]) > 0.01
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Skill timeouts detected"
          description: "Skills are timing out frequently."

  - name: synapse_security
    rules:
      - alert: MultipleFailedLogins
        expr: increase(synapse_auth_failures_total[5m]) > 5
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Multiple failed login attempts"
          description: "Possible brute force attack."

      - alert: UnusualSkillExecution
        expr: rate(synapse_skill_executions_total[5m]) > 10
        for: 5m
        labels:
          severity: info
        annotations:
          summary: "Unusual skill execution rate"
          description: "Higher than normal activity detected."
```

---

## Grafana Dashboards

### Dashboard Provisioning

```yaml
# docker/grafana/provisioning/dashboards/dashboards.yaml
apiVersion: 1
providers:
  - name: 'Synapse'
    orgId: 1
    folder: 'Synapse'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards/json
```

### Main Dashboard

```json
{
  "dashboard": {
    "title": "Synapse Overview",
    "tags": ["synapse", "overview"],
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{path}}"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(synapse_errors_total[5m])",
            "legendFormat": "{{error_type}}"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "gauge",
        "targets": [
          {
            "expr": "synapse_memory_usage_bytes / synapse_memory_limit_bytes * 100"
          }
        ]
      },
      {
        "title": "LLM Token Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(synapse_llm_token_usage_total[1h])",
            "legendFormat": "{{provider}} {{type}}"
          }
        ]
      },
      {
        "title": "Skill Executions",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(synapse_skill_executions_total[5m])",
            "legendFormat": "{{skill_name}}"
          }
        ]
      },
      {
        "title": "Capability Checks",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(synapse_capability_checks_total[5m])",
            "legendFormat": "{{result}}"
          }
        ]
      }
    ]
  }
}
```

### LLM Dashboard

```json
{
  "dashboard": {
    "title": "Synapse LLM",
    "panels": [
      {
        "title": "Provider Status",
        "type": "stat",
        "targets": [
          {
            "expr": "synapse_llm_provider_available",
            "legendFormat": "{{provider}}"
          }
        ]
      },
      {
        "title": "Latency Distribution",
        "type": "heatmap",
        "targets": [
          {
            "expr": "rate(synapse_llm_latency_seconds_bucket[5m])"
          }
        ]
      },
      {
        "title": "Token Cost",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(rate(synapse_llm_token_usage_total[24h])) * 0.00003"
          }
        ]
      },
      {
        "title": "Requests by Model",
        "type": "piechart",
        "targets": [
          {
            "expr": "sum by (model) (rate(synapse_llm_requests_total[1h]))"
          }
        ]
      }
    ]
  }
}
```

---

## Metrics Reference

### System Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `synapse_memory_usage_bytes` | Gauge | Current memory usage |
| `synapse_memory_limit_bytes` | Gauge | Memory limit |
| `synapse_cpu_usage_seconds` | Counter | CPU time used |
| `synapse_goroutines` | Gauge | Number of goroutines |
| `synapse_uptime_seconds` | Gauge | System uptime |

### HTTP Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | Request latency |
| `http_requests_in_flight` | Gauge | Active requests |

### LLM Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `synapse_llm_requests_total` | Counter | Total LLM requests |
| `synapse_llm_latency_seconds` | Histogram | LLM response latency |
| `synapse_llm_token_usage_total` | Counter | Token usage |
| `synapse_llm_errors_total` | Counter | LLM errors |
| `synapse_llm_provider_available` | Gauge | Provider availability |

### Skill Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `synapse_skill_executions_total` | Counter | Total skill executions |
| `synapse_skill_executions_failed_total` | Counter | Failed executions |
| `synapse_skill_timeouts_total` | Counter | Skill timeouts |
| `synapse_skill_duration_seconds` | Histogram | Skill execution time |

### Security Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `synapse_auth_attempts_total` | Counter | Authentication attempts |
| `synapse_auth_failures_total` | Counter | Failed authentications |
| `synapse_capability_checks_total` | Counter | Capability validations |
| `synapse_capability_denied_total` | Counter | Capability denials |

---

## Logging

### Structured Logging

```yaml
# config.yaml
logging:
  format: json
  level: INFO
  output: /var/log/synapse/app.log
  
  fields:
    - timestamp
    - level
    - message
    - trace_id
    - session_id
    - user_id
    - protocol_version
```

### Log Format

```json
{
  "timestamp": "2026-02-20T12:00:00.000Z",
  "level": "INFO",
  "message": "Skill executed successfully",
  "trace_id": "trace_123",
  "session_id": "sess_456",
  "user_id": "user@example.com",
  "skill_name": "read_file",
  "execution_time_ms": 45,
  "protocol_version": "1.0"
}
```

### Log Aggregation

```yaml
# docker-compose.yml with Loki
services:
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - loki_data:/loki

  promtail:
    image: grafana/promtail:latest
    volumes:
      - ./logs:/var/log/synapse
      - ./docker/promtail.yml:/etc/promtail/config.yml
    command: -config.file=/etc/promtail/config.yml
```

---

## Distributed Tracing

### OpenTelemetry Setup

```yaml
# config.yaml
tracing:
  enabled: true
  provider: otlp
  endpoint: http://jaeger:4317
  sampling_rate: 0.1
  
  attributes:
    service.name: synapse
    service.version: "3.1"
    protocol_version: "1.0"
```

### Jaeger Deployment

```yaml
# docker-compose.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
```

---

## Health Checks

### Endpoints

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `/health` | Overall health | Status + services |
| `/ready` | Readiness | Ready state |
| `/live` | Liveness | Alive state |

### Health Check Response

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

---

## Alerting

### Alertmanager Configuration

```yaml
# docker/alertmanager.yml
global:
  resolve_timeout: 5m
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'alerts@synapse.example.com'

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical'
    - match:
        severity: warning
      receiver: 'warning'

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://synapse-core:8000/api/v1/alerts'

  - name: 'critical'
    email_configs:
      - to: 'ops-team@example.com'
    slack_configs:
      - channel: '#synapse-critical'
        send_resolved: true

  - name: 'warning'
    email_configs:
      - to: 'ops-team@example.com'
```

---

## Performance Monitoring

### Key Metrics to Monitor

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Request Latency (p95) | < 500ms | > 2s |
| Error Rate | < 1% | > 5% |
| Memory Usage | < 80% | > 90% |
| CPU Usage | < 70% | > 90% |
| LLM Latency (p95) | < 3s | > 5s |
| Skill Success Rate | > 95% | < 90% |

### Performance Dashboard

```json
{
  "dashboard": {
    "title": "Synapse Performance",
    "panels": [
      {
        "title": "Latency Percentiles",
        "type": "graph",
        "targets": [
          {"expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))"},
          {"expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"},
          {"expr": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))"}
        ]
      },
      {
        "title": "Throughput",
        "type": "graph",
        "targets": [
          {"expr": "rate(http_requests_total[5m])"}
        ]
      }
    ]
  }
}
```

---

## Troubleshooting

### Common Issues

**High Memory Usage**
```bash
# Check memory breakdown
curl http://localhost:9090/metrics | grep memory

# Restart if needed
docker-compose restart synapse-core
```

**High Latency**
```bash
# Check slow requests
curl http://localhost:9090/metrics | grep latency

# Check LLM provider status
curl http://localhost:8000/api/v1/llm/status
```

**Alert Storms**
```bash
# Silence alerts
curl -X POST http://localhost:9093/api/v1/silences \
  -d '{"matchers":[{"name":"alertname","value":"HighErrorRate"}],"duration":"1h"}'
```

---

**Protocol Version:** 1.0  
**Need Help?** Check [Troubleshooting](../user/troubleshooting.md) or open an issue on GitHub.
