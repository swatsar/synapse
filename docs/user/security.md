# Руководство по безопасности Synapse

**Protocol Version:** 1.0 | **Spec Version:** 3.1

---

## Модель безопасности

Synapse реализует **Capability-Based Security** — ни один агент или навык не имеет никаких прав по умолчанию. Каждое действие требует явного capability-токена.

### Уровни защиты

```
┌─────────────────────────────────────────────────────┐
│  1. API Authentication (X-API-Key / WebSocket token) │
├─────────────────────────────────────────────────────┤
│  2. Capability Tokens (wildcard scope + TTL)        │
├─────────────────────────────────────────────────────┤
│  3. ExecutionGuard (pre-execution capability check)  │
├─────────────────────────────────────────────────────┤
│  4. IsolationPolicy (subprocess/container/sandbox)  │
├─────────────────────────────────────────────────────┤
│  5. Human-in-the-Loop (risk_level ≥ 3)             │
├─────────────────────────────────────────────────────┤
│  6. AuditMechanism (full event log)                 │
├─────────────────────────────────────────────────────┤
│  7. Zero-Trust Fabric (cluster node verification)   │
└─────────────────────────────────────────────────────┘
```

---

## Capability токены

### Синтаксис

```
<namespace>:<action>:<scope>
```

Примеры:
```
fs:read:/workspace/**              # чтение всех файлов в /workspace
fs:write:/workspace/output/**      # запись только в /workspace/output
fs:read:/workspace/config.yaml     # только один файл
network:http:*                     # любые HTTP-запросы
network:http:api.openai.com        # только один хост
code:execute:python                # выполнение Python
code:execute:*                     # любой код
```

### Жизненный цикл токена

```python
from synapse.core.security import CapabilityManager

cm = CapabilityManager()

# Выдача
token = await cm.issue_token(
    capability="fs:read:/workspace/**",
    issued_to="developer_agent",
    issued_by="orchestrator",
    expires_in_hours=8        # TTL — 8 часов (None = бессрочно)
)

# Проверка
result = await cm.check_capabilities(
    required=["fs:read:/workspace/**"],
    agent_id="developer_agent"
)
# result.approved: bool
# result.blocked_capabilities: List[str]

# Отзыв
await cm.revoke_token(token.id, agent_id="developer_agent")
```

### Принцип минимальных привилегий

Всегда выдавайте минимально необходимый scope:
```python
# ❌ Слишком широко
await cm.issue_token("fs:read:/**", ...)

# ✅ Точный scope
await cm.issue_token("fs:read:/workspace/reports/**", ...)
```

---

## Уровни изоляции

| Trust Level | Механизм | Когда применяется |
|-------------|----------|-------------------|
| `trusted` | subprocess (без изоляции) | Встроенные навыки платформы |
| `verified` | Docker-контейнер | Навыки прошедшие security scan |
| `unverified` | strict_sandbox | LLM-генерированные навыки |

Настройка в `config/default.yaml`:
```yaml
isolation_policy:
  unverified_skills: "container"
  risk_level_3_plus: "container"
  trusted_skills: "subprocess"
```

---

## Human-in-the-Loop

Операции с `risk_level ≥ 3` требуют ручного одобрения:

```bash
# Получить ожидающие одобрения
curl -H "X-API-Key: $SYNAPSE_API_KEY" \
  http://localhost:8000/api/v1/approvals/pending

# Одобрить
curl -X POST -H "X-API-Key: $SYNAPSE_API_KEY" \
  http://localhost:8000/api/v1/approvals/appr_xyz/approve

# Отклонить
curl -X POST -H "X-API-Key: $SYNAPSE_API_KEY" \
  http://localhost:8000/api/v1/approvals/appr_xyz/reject
```

---

## Аудит

Каждое значимое действие записывается в `AuditMechanism`:

```python
from synapse.core.security import AuditMechanism

audit = AuditMechanism()

# Записать событие
await audit.emit_event(
    event_type="skill_executed",
    details={
        "agent_id": "developer",
        "capability": "fs:write:/workspace/**",
        "result": "success"
    }
)

# Получить события
events = await audit.get_events(
    event_type="capability_denied",
    agent_id="developer",
    limit=50
)
```

Типы событий аудита:
- `capability_token_issued` — выдача токена
- `capability_token_revoked` — отзыв токена
- `capability_check_denied` — отказ в доступе
- `capability_executed` — успешное выполнение
- `security_manager_initialized` — инициализация системы

---

## Production: чек-лист безопасности

- [ ] `SYNAPSE_API_KEY` установлен (≥32 hex-символа)
- [ ] `SYNAPSE_API_KEY` не совпадает с dev-значением из `.env.example`
- [ ] Все LLM-ключи в `.env`, не в коде
- [ ] `require_approval_for_risk: 3` в конфиге
- [ ] Audit log путь настроен и директория защищена
- [ ] HTTPS настроен (nginx/traefik перед Synapse)
- [ ] `CORS allow_origins` ограничен вашим доменом (в `app.py`)
- [ ] Docker запускается не от root
- [ ] PostgreSQL пароль ≥16 символов
- [ ] Redis защищён паролем или только localhost
- [ ] Qdrant не доступен из интернета (только localhost/VPC)
- [ ] Регулярная ротация `SYNAPSE_API_KEY`

---

## STRIDE Threat Model

| Угроза | Контрмера |
|--------|-----------|
| **Spoofing** | `X-API-Key` + WebSocket token |
| **Tampering** | Immutable AuditEvent, security_hash |
| **Repudiation** | Полный audit trail |
| **Information Disclosure** | Секреты не передаются в sandbox |
| **Denial of Service** | Rate limit (60 req/min), resource limits per skill |
| **Elevation of Privilege** | Строгая изоляция + capability scope |

---

## Сообщить об уязвимости

Email: [evgeniisav@gmail.com](mailto:evgeniisav@gmail.com)  
Или через [GitHub Security](https://github.com/swatsar/synapse/security/advisories/new)

Не публикуйте уязвимости в открытых Issues.
