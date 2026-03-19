# Устранение неполадок Synapse

**Protocol Version:** 1.0 | **Версия:** 3.4.1

---

## Установка и запуск

### `ModuleNotFoundError: No module named 'synapse'`

```bash
# Убедитесь что venv активирован
source .venv/bin/activate

# Переустановите
pip install -e ".[dev]"

# Проверка
python -c "import synapse; print(synapse.__version__)"
```

---

### `ImportError: No module named 'litellm'` или другой зависимости

```bash
pip install -r requirements.txt
# или
pip install -e ".[dev]"
```

---

### Сервер не запускается: `Address already in use`

```bash
# Найти процесс на порту 8000
lsof -i :8000        # Linux/macOS
netstat -ano | findstr 8000  # Windows

# Убить
kill -9 <PID>
# или использовать другой порт:
synapse --port 8001 --web-ui
```

---

### `SYNAPSE_API_KEY is not set` — предупреждение при старте

В dev-режиме без ключа API открыто. Для production обязательно задайте:
```bash
export SYNAPSE_API_KEY="$(openssl rand -hex 32)"
# или добавьте в .env:
SYNAPSE_API_KEY=my-secure-key
```

---

## API и аутентификация

### `401 Unauthorized` при запросах

```bash
# Проверьте заголовок
curl -H "X-API-Key: $SYNAPSE_API_KEY" http://localhost:8000/api/v1/agents

# Проверьте что ключ совпадает с .env
cat .env | grep SYNAPSE_API_KEY
```

---

### `404 Not Found` для `/api/v1/...`

Убедитесь что роутер подключён. Все API-маршруты доступны по префиксу `/api/v1/`.
```bash
# Список доступных маршрутов
curl http://localhost:8000/openapi.json | python -m json.tool | grep '"path"'
```

---

### WebSocket: `1008 Unauthorized`

WebSocket требует токен в query-параметре:
```
ws://localhost:8000/ws?token=<SYNAPSE_API_KEY>
```

---

## LLM провайдеры

### `litellm.AuthenticationError` / `Invalid API key`

```bash
# Проверьте ключ
echo $OPENAI_API_KEY
# или
cat .env | grep API_KEY

# Тест напрямую
python -c "import litellm; r = litellm.completion(model='gpt-4o-mini', messages=[{'role':'user','content':'hi'}]); print(r)"
```

---

### `RuntimeError: No available provider`

LLM Router не нашёл активного провайдера. Добавьте провайдер:
```bash
curl -X POST http://localhost:8000/api/v1/providers \
  -H "X-API-Key: $SYNAPSE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"openai","model":"gpt-4o","api_key":"sk-...","priority":1}'
```

Или укажите ключ в `.env` и перезапустите.

---

## База данных

### `asyncpg.exceptions.ConnectionDoesNotExistError`

PostgreSQL недоступен. Проверьте:
```bash
pg_isready -h localhost -p 5432 -U synapse_user
# или запустите через Docker:
docker-compose -f docker/docker-compose.yml up -d db
```

Если PostgreSQL не нужен — уберите `DATABASE_URL` из `.env`, будет использоваться SQLite.

---

### ChromaDB / Qdrant недоступен

```bash
# ChromaDB (встроенный, не требует отдельного сервера)
# Qdrant — запустите:
docker run -d -p 6333:6333 qdrant/qdrant:latest

# Или уберите VECTOR_DB_URL из .env — memory будет in-memory
```

---

## Безопасность

### `CapabilityError: Missing required capabilities`

Агенту не выдан токен для операции. Выдайте токен:
```python
from synapse.core.security import CapabilityManager

cm = CapabilityManager()
await cm.issue_token(
    capability="fs:read:/workspace/**",
    issued_to="developer_agent",
    issued_by="orchestrator",
    expires_in_hours=24
)
```

---

### `SecurityViolationError` при выполнении навыка

Навык пытается выполнить операцию вне разрешённого scope. Проверьте:
1. Лог аудита: `cat /var/log/synapse/audit.log | grep DENIED`
2. Capability token scope — возможно, слишком ограничен

---

## Docker

### Контейнер не стартует: `unhealthy`

```bash
# Логи конкретного контейнера
docker logs synapse-core --tail 50

# Статус healthcheck
docker inspect synapse-core | grep -A 10 Health
```

---

### `db` сервис не готов при старте `synapse-core`

```bash
# Подождите готовности DB
docker-compose -f docker/docker-compose.yml up -d db
sleep 10
docker-compose -f docker/docker-compose.yml up -d synapse-core
```

---

## Тесты

### Тесты падают: `ImportError`

```bash
pip install -e ".[dev]"
pytest tests/ -v --tb=short
```

### Определённые тесты зависают

```bash
# Запустите с таймаутом
pytest tests/ -v --timeout=30

# Отдельный файл
pytest tests/api/test_exceptions.py -v
```

---

## Сбор диагностики

```bash
# Версия и здоровье
curl http://localhost:8000/health
synapse --version

# Зависимости
pip list | grep -E "fastapi|pydantic|litellm|uvicorn"

# Логи сервиса
journalctl -u synapse -n 100 --no-pager   # systemd
docker logs synapse-core --tail 100        # Docker

# Открыть issue с этой информацией
python --version && pip show synapse-agent
```

Если проблема не решена — откройте [GitHub Issue](https://github.com/swatsar/synapse/issues) с логами и описанием.
