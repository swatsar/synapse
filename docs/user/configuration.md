# Конфигурация Synapse

**Protocol Version:** 1.0 | **Spec Version:** 3.1

---

## Файлы конфигурации

```
config/
└── default.yaml          # Основная конфигурация
.env                       # Секреты и переменные окружения
```

---

## Переменные окружения (`.env`)

```env
# === Аутентификация ===
SYNAPSE_API_KEY=<hex-32-символа>       # Обязателен для production

# === LLM провайдеры (хотя бы один) ===
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# === База данных ===
DATABASE_URL=postgresql://user:pass@localhost:5432/synapse
# Без DATABASE_URL используется SQLite: data/synapse.db

# === Vector store ===
VECTOR_DB_URL=http://localhost:6333    # Qdrant

# === Кэш ===
REDIS_URL=redis://localhost:6379

# === Кластер ===
CLUSTER_MODE=false
NODE_ID=node-1
CLUSTER_SECRET=<hex-64-символа>

# === Логирование ===
LOG_LEVEL=INFO                         # DEBUG / INFO / WARNING / ERROR
AUDIT_LOG_PATH=/var/log/synapse/audit.log

# === Мониторинг ===
PROMETHEUS_PORT=9090
```

---

## `config/default.yaml`

```yaml
system:
  name: "Synapse"
  version: "3.2.5"
  mode: "local"             # local | docker | distributed
  protocol_version: "1.0"

llm:
  default_provider: "openai"
  timeout_seconds: 30
  models:
    - name: "gpt-4o"
      provider: "openai"
      priority: 1           # 1 = высший приоритет
    - name: "claude-3-5-sonnet-20241022"
      provider: "anthropic"
      priority: 2           # fallback

memory:
  vector_db: "chromadb"     # chromadb | qdrant
  sql_db: "${DATABASE_URL}" # переменная из .env

security:
  require_approval_for_risk: 3    # уровень риска для Human-in-the-Loop
  rate_limit_per_minute: 60
  audit_log_path: "/var/log/synapse/audit.log"
  api_key_header: "X-API-Key"

isolation_policy:
  unverified_skills: "container"   # container | subprocess | strict_sandbox
  risk_level_3_plus: "container"
  trusted_skills: "subprocess"

resources:
  default_limits:
    cpu_seconds: 60
    memory_mb: 512
    disk_mb: 100
    network_kb: 1024
```

---

## LLM провайдеры

Synapse использует `litellm` — поддерживаются любые совместимые провайдеры:

| Провайдер | Переменная | Примеры моделей |
|-----------|------------|-----------------|
| OpenAI | `OPENAI_API_KEY` | `gpt-4o`, `gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-20241022` |
| Google | `GOOGLE_API_KEY` | `gemini-1.5-pro` |
| Ollama (local) | — | `ollama/llama3.2` |
| Azure OpenAI | `AZURE_API_KEY` + `AZURE_API_BASE` | `azure/gpt-4o` |

Добавить провайдер через API:
```bash
curl -X POST http://localhost:8000/api/v1/providers \
  -H "X-API-Key: $SYNAPSE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"openai","model":"gpt-4o","api_key":"sk-...","priority":1}'
```

---

## Уровни риска и изоляция

| Уровень | Требует одобрения | Изоляция | Примеры операций |
|---------|-------------------|----------|------------------|
| 1 | ❌ | subprocess | чтение файлов, web-запросы |
| 2 | ❌ | subprocess | запись файлов |
| 3 | ✅ | container | выполнение команд |
| 4 | ✅ | container | сетевые операции |
| 5 | ✅ | strict_sandbox | системные операции |

---

## Capability токены

Синтаксис capability: `<namespace>:<action>:<scope>`

Примеры:
```
fs:read:/workspace/**          # чтение любых файлов в /workspace
fs:write:/workspace/output/**  # запись в /workspace/output
network:http:*                 # любые HTTP запросы
code:execute:python            # выполнение Python кода
```

Выдача токена:
```python
from synapse.core.security import CapabilityManager

cm = CapabilityManager()
token = await cm.issue_token(
    capability="fs:read:/workspace/**",
    issued_to="developer_agent",
    issued_by="orchestrator",
    expires_in_hours=24
)
```

---

## Логирование

```env
LOG_LEVEL=INFO    # Уровень консольного лога
```

Форматы логов:
- **Консоль:** структурированный JSON через `structlog`
- **Аудит:** `AUDIT_LOG_PATH` — все операции с агентами и навыками
- **Prometheus:** `/metrics` эндпоинт

---

## Режимы запуска

```bash
# Локальный (SQLite, без Docker)
synapse --mode local --web-ui

# Docker (PostgreSQL, Qdrant, Redis)
docker-compose -f docker/docker-compose.yml up -d

# Распределённый кластер
synapse --mode distributed --node-id node-1 \
  --cluster-coordinator http://coordinator:8001
```
