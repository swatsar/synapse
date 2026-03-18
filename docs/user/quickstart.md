# Быстрый старт Synapse

**Время:** ~5 минут | **Protocol Version:** 1.0

---

## Шаг 1. Установка (1 минута)

```bash
git clone https://github.com/swatsar/synapse.git
cd synapse
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Откройте `.env` и задайте хотя бы один LLM-ключ:
```env
SYNAPSE_API_KEY=my-dev-key-change-in-production
OPENAI_API_KEY=sk-...
```

---

## Шаг 2. Запуск (30 секунд)

```bash
synapse --web-ui --port 8000
```

Откройте браузер: **http://localhost:8000**

Должен появиться Web Dashboard с 4 агентами: Planner, Critic, Developer, Guardian.

---

## Шаг 3. Первая задача через API (1 минута)

```bash
# Создать задачу
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my-dev-key-change-in-production" \
  -d '{"description": "Напиши Python функцию для сортировки списка"}'

# Проверить статус
curl -H "X-API-Key: my-dev-key-change-in-production" \
  http://localhost:8000/api/v1/tasks
```

---

## Шаг 4. Первая задача через Python SDK (2 минуты)

```python
import asyncio
from synapse.core.orchestrator import Orchestrator
from synapse.core.determinism import DeterministicSeedManager, DeterministicIDGenerator
from synapse.core.security import SecurityManager
from synapse.memory.store import MemoryStore

async def main():
    # Инициализация
    seed_manager = DeterministicSeedManager()
    id_generator = DeterministicIDGenerator()
    security = SecurityManager()
    memory = MemoryStore()
    
    orchestrator = Orchestrator(seed_manager, id_generator, memory, security)
    print("✅ Synapse Agent готов к работе")

asyncio.run(main())
```

---

## Шаг 5. Проверка здоровья

```bash
curl http://localhost:8000/health
# {"status":"healthy","version":"3.2.5","protocol_version":"1.0",...}
```

---

## Что дальше?

| Задача | Документ |
|--------|----------|
| Настройка LLM-провайдеров | [configuration.md](configuration.md) |
| Написание собственного навыка | [developer/skills.md](../developer/skills.md) |
| Настройка безопасности | [security.md](security.md) |
| Развёртывание в production | [admin/deployment.md](../admin/deployment.md) |
| API для интеграций | [API_REFERENCE.md](../API_REFERENCE.md) |
| Решение проблем | [troubleshooting.md](../TROUBLESHOOTING.md) |
