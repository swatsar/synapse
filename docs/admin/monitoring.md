# Мониторинг Synapse

**Protocol Version:** 1.0

---

## Prometheus метрики

Метрики доступны на `http://localhost:9090/metrics` (или порт из `PROMETHEUS_PORT`).

### Ключевые метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `synapse_tasks_total` | Counter | Всего задач |
| `synapse_tasks_success_total` | Counter | Успешных задач |
| `synapse_tasks_failed_total` | Counter | Провалившихся задач |
| `synapse_capability_checks_total` | Counter | Проверок capability |
| `synapse_capability_denied_total` | Counter | Отказов capability |
| `synapse_agent_cycle_duration_seconds` | Histogram | Длительность цикла агента |
| `synapse_skill_executions_total` | Counter | Запусков навыков |
| `synapse_llm_requests_total` | Counter | Запросов к LLM |
| `synapse_llm_latency_seconds` | Histogram | Задержка LLM |
| `http_requests_total` | Counter | HTTP запросов к API |
| `http_request_duration_seconds` | Histogram | Длительность HTTP |

---

## Grafana Dashboard

Grafana доступна на `http://localhost:3000`.

**Логин по умолчанию:** admin / `$GRAFANA_PASSWORD` (из `.env`)

### Рекомендуемые панели

1. **Platform Overview**
   - Задачи за последний час (tasks_total rate)
   - Success rate (tasks_success / tasks_total)
   - Активные агенты

2. **Security**
   - Capability denials rate
   - Pending approvals count
   - Audit events rate

3. **Performance**
   - API latency (p50, p95, p99)
   - LLM latency по провайдерам
   - Cognitive cycle duration

4. **Infrastructure**
   - CPU/Memory контейнеров
   - DB connections
   - Redis memory

---

## Healthcheck эндпоинт

```bash
GET /health
```

```json
{
  "status": "healthy",
  "version": "3.2.5",
  "protocol_version": "1.0",
  "timestamp": "2026-03-18T10:00:00+00:00"
}
```

Используйте для:
- Docker healthcheck (`HEALTHCHECK CMD curl -f http://localhost:8000/health`)
- Kubernetes liveness/readiness probe
- Load balancer health check
- Uptime monitoring (UptimeRobot, Pingdom)

---

## Структурированные логи

Synapse использует `structlog` для JSON-логов:

```json
{
  "event": "capability_check_denied",
  "agent_id": "developer_agent",
  "blocked_capabilities": ["fs:write:/etc/**"],
  "timestamp": "2026-03-18T10:00:00+00:00",
  "level": "warning"
}
```

### Поиск в логах

```bash
# Все отказы capability
journalctl -u synapse | grep "capability_check_denied"

# Ошибки за последний час
journalctl -u synapse --since "1 hour ago" -p err

# Docker
docker logs synapse-core | python -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        if d.get('level') in ('error','critical'):
            print(json.dumps(d, indent=2))
    except:
        pass
"
```

---

## Алерты (Prometheus Alertmanager)

```yaml
# prometheus_alerts.yml
groups:
  - name: synapse
    rules:
      - alert: HighCapabilityDenials
        expr: rate(synapse_capability_denied_total[5m]) > 10
        for: 2m
        annotations:
          summary: "Высокое количество отказов capability"

      - alert: SynapseDown
        expr: up{job="synapse"} == 0
        for: 1m
        annotations:
          summary: "Synapse недоступен"

      - alert: HighAPILatency
        expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 2
        for: 5m
        annotations:
          summary: "Высокая задержка API (p95 > 2s)"

      - alert: PendingApprovalsBacklog
        expr: synapse_pending_approvals > 20
        for: 10m
        annotations:
          summary: "Большое количество ожидающих одобрений"
```
