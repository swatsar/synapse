# Synapse API Reference

**Version:** 3.2.5
**Protocol Version:** 1.0
**Base URL:** `http://localhost:8000`

---

## Аутентификация

Все эндпоинты, кроме `/health` и `/`, требуют заголовок:

```
X-API-Key: <your-api-key>
```

Или query-параметр `?api_key=<key>`.

API-ключ задаётся переменной окружения `SYNAPSE_API_KEY`.

WebSocket (`/ws`) принимает токен через query-параметр `?token=<key>`.

> В режиме локальной разработки (без `SYNAPSE_API_KEY`) аутентификация пропускается.

---

## Эндпоинты

### Здоровье системы

#### `GET /health`

Проверка доступности сервиса.

**Ответ 200:**
```json
{
  "status": "healthy",
  "version": "3.2.5",
  "protocol_version": "1.0",
  "timestamp": "2026-03-18T10:00:00+00:00"
}
```

---

#### `GET /api/v1/status`

Расширенный статус платформы.

**Ответ 200:**
```json
{
  "status": "operational",
  "version": "3.2.5",
  "protocol_version": "1.0",
  "agents": 4,
  "uptime_seconds": 3600,
  "timestamp": "2026-03-18T10:00:00+00:00"
}
```

---

### Задачи

#### `POST /api/v1/tasks`

Создать новую задачу для выполнения агентом.

**Тело запроса:**
```json
{
  "description": "Найди и суммируй последние новости об ИИ",
  "priority": "normal",
  "agent_id": "planner",
  "context": {}
}
```

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `description` | string | ✅ | Описание задачи |
| `priority` | string | ❌ | `low` / `normal` / `high` (по умолчанию `normal`) |
| `agent_id` | string | ❌ | ID агента (по умолчанию `planner`) |
| `context` | object | ❌ | Дополнительный контекст |

**Ответ 200:**
```json
{
  "task_id": "task_abc123",
  "status": "queued",
  "description": "Найди и суммируй последние новости об ИИ",
  "created_at": "2026-03-18T10:00:00+00:00",
  "protocol_version": "1.0"
}
```

---

#### `GET /api/v1/tasks`

Получить список всех задач.

**Query-параметры:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `limit` | int | 50 | Максимум задач в ответе |
| `status` | string | — | Фильтр по статусу (`queued`, `running`, `done`, `failed`) |

**Ответ 200:**
```json
{
  "tasks": [...],
  "total": 10,
  "protocol_version": "1.0"
}
```

---

### Агенты

#### `GET /api/v1/agents`

Список всех зарегистрированных агентов.

**Ответ 200:**
```json
{
  "agents": [
    {
      "id": "planner",
      "name": "Planner Agent",
      "status": "idle",
      "type": "planner",
      "protocol_version": "1.0"
    }
  ],
  "protocol_version": "1.0"
}
```

---

#### `GET /api/v1/agents/{agent_id}`

Получить агента по ID.

**Path параметры:** `agent_id` — ID агента (`planner`, `critic`, `developer`, `guardian`)

**Ответ 200:** объект агента.

**Ответ 404:**
```json
{
  "error": "NOT_FOUND",
  "message": "Agent 'unknown' not found",
  "status_code": 404,
  "protocol_version": "1.0"
}
```

---

#### `GET /api/v1/agents/{agent_id}/logs`

Логи конкретного агента.

**Query-параметры:**
| Параметр | По умолчанию |
|----------|--------------|
| `limit` | 100 |

---

#### `POST /api/v1/agents/{agent_id}/start`

Запустить агента.

**Ответ 200:**
```json
{"status": "started", "agent_id": "planner", "protocol_version": "1.0"}
```

---

#### `POST /api/v1/agents/{agent_id}/stop`

Остановить агента.

---

### Одобрения (Human-in-the-Loop)

#### `GET /api/v1/approvals`

Все запросы на одобрение.

---

#### `GET /api/v1/approvals/pending`

Только ожидающие одобрения.

**Ответ 200:**
```json
{
  "approvals": [
    {
      "id": "appr_xyz",
      "task_description": "Удалить файл /workspace/old.log",
      "risk_level": 4,
      "agent_id": "developer",
      "status": "pending",
      "created_at": "2026-03-18T10:00:00+00:00"
    }
  ],
  "protocol_version": "1.0"
}
```

---

#### `POST /api/v1/approvals/{approval_id}/approve`

Одобрить запрос.

**Ответ 200:** объект одобрения со статусом `"approved"`.

---

#### `POST /api/v1/approvals/{approval_id}/reject`

Отклонить запрос.

---

### Логи

#### `GET /api/v1/logs`

Последние логи платформы.

**Query-параметры:** `limit` (по умолчанию 100).

---

#### `POST /api/v1/logs`

Добавить запись лога (для внутреннего использования).

---

### Провайдеры LLM

#### `GET /api/v1/providers`

Список всех зарегистрированных LLM-провайдеров.

---

#### `POST /api/v1/providers`

Добавить или обновить провайдера.

**Тело запроса:**
```json
{
  "name": "openai",
  "model": "gpt-4o",
  "api_key": "sk-...",
  "priority": 1
}
```

---

#### `DELETE /api/v1/providers/{provider_name}`

Удалить провайдера.

---

### Настройки

#### `GET /api/v1/settings`

Текущие настройки платформы.

---

#### `PUT /api/v1/settings`

Обновить настройки.

---

### WebSocket

#### `WS /ws?token=<api-key>`

Двусторонний канал в реальном времени.

**Отправка:**
```json
{"type": "ping", "data": {}}
```

**Получение:**
```json
{"type": "echo", "data": {"type": "ping", "data": {}}, "protocol_version": "1.0"}
```

---

## Коды ошибок

| HTTP | `error` | Описание |
|------|---------|----------|
| 400 | `BAD_REQUEST` | Некорректный запрос |
| 401 | `UNAUTHORIZED` | Неверный API-ключ |
| 403 | `CAPABILITY_DENIED` | Недостаточно прав |
| 403 | `SECURITY_VIOLATION` | Нарушение безопасности |
| 404 | `NOT_FOUND` | Ресурс не найден |
| 409 | `CONFLICT` | Конфликт ресурсов |
| 422 | `VALIDATION_ERROR` | Ошибка валидации |
| 429 | `RATE_LIMITED` | Превышен лимит запросов |
| 500 | `INTERNAL_ERROR` | Внутренняя ошибка сервера |
| 503 | `RESOURCE_EXHAUSTED` | Ресурсы исчерпаны |
| 504 | `TIMEOUT` | Таймаут операции |

**Формат всех ошибок:**
```json
{
  "error": "NOT_FOUND",
  "message": "Agent 'xyz' not found",
  "status_code": 404,
  "details": {"resource_type": "Agent", "resource_id": "xyz"},
  "protocol_version": "1.0"
}
```

---

## Лимиты

| Параметр | Значение |
|----------|----------|
| Rate limit | 60 запросов/минуту |
| Max task description | 10 000 символов |
| Max logs in response | 10 000 |
| Max approvals in response | 10 000 |
| WebSocket heartbeat | 30 сек |
