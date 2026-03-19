# 📎 PROJECT SYNAPSE: OPENCLAW INTEGRATION GUIDE

**Версия:** 1.0  
**Статус:** Supplementary Document  
**Основная спецификация:** `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`  
**Дата:** 2026

---

## 🎯 НАЗНАЧЕНИЕ ДОКУМЕНТА

Этот документ является **дополнением** к основной технической спецификации `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`. Он описывает стратегию интеграции полезных паттернов и компонентов из проекта [OpenClaw](https://github.com/openclaw/openclaw) в платформу Synapse.

**Важно:** OpenClaw используется как **референс для implementation patterns**, а НЕ как архитектурная основа. Synapse имеет более строгую security model, self-evolution capability и production-ready reliability features.

---

## 📊 ОБЩАЯ ОЦЕНКА ПРИМЕНИМОСТИ

| Область | Ценность для Synapse | % Кода для Заимствования | Статус |
|---------|---------------------|-------------------------|--------|
| Коннекторы (мессенджеры) | ⭐⭐⭐⭐⭐ | ~60% | ✅ Рекомендовано |
| Конфигурация (YAML/ENV) | ⭐⭐⭐⭐⭐ | ~50% | ✅ Рекомендовано |
| Деплой (Docker/Compose) | ⭐⭐⭐⭐⭐ | ~70% | ✅ Рекомендовано |
| Память (Vector Store) | ⭐⭐⭐⭐ | ~40% | ⚠️ Адаптировать |
| LLM Abstraction | ⭐⭐⭐ | ~30% | ⚠️ Адаптировать |
| Навыки (Skill System) | ⭐⭐⭐ | ~25% | ⚠️ Адаптировать |
| Безопасность | ⭐ | ~0% | ❌ НЕ брать |
| Execution Model | ⭐ | ~0% | ❌ НЕ брать |

---

## 1️⃣ КОННЕКТОРЫ МЕССЕНДЖЕРОВ (HIGH PRIORITY)

### 1.1 Что Заимствовать

| Компонент | Файл OpenClaw | Файл Synapse | Действие |
|-----------|--------------|--------------|----------|
| Telegram Bot | `connectors/telegram.py` | `synapse/connectors/telegram.py` | Адаптировать с security layer |
| Discord Integration | `connectors/discord.py` | `synapse/connectors/discord.py` | Адаптировать с capability checks |
| Message Normalization | `connectors/base.py` | `synapse/connectors/base_connector.py` | Взять паттерн InputEvent |
| Rate Limiting | `connectors/rate_limiter.py` | `synapse/connectors/security.py` | Адаптировать алгоритмы |

### 1.2 Паттерн Обработки Сообщений

```python
# openclaw/connectors/telegram.py → synapse/connectors/telegram.py
from aiogram import Bot, Dispatcher, types
from core.models import InputEvent, PROTOCOL_VERSION

class TelegramConnector(BaseConnector):
    """
    Telegram мессенджер коннектор.
    Адаптировано из OpenClaw с добавлением security layer.
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self, config: dict, security_manager: ConnectorSecurityManager):
        super().__init__(config)
        self.bot = Bot(token=config['token'])
        self.dp = Dispatcher()
        self.security = security_manager  # 🔹 Наше дополнение
    
    async def handle_message(self, message: types.Message):
        # 1. Проверка безопасности (наше дополнение)
        is_allowed = await self.security.verify_user(
            user_id=str(message.from_user.id),
            connector_type="telegram"
        )
        if not is_allowed:
            await self.security.log_security_event(
                event_type="unauthorized_access",
                user_id=str(message.from_user.id),
                details={"connector": "telegram"}
            )
            return
        
        # 2. Rate limiting (адаптировано из OpenClaw)
        rate_ok = await self.security.check_rate_limit(
            user_id=str(message.from_user.id),
            connector_type="telegram"
        )
        if not rate_ok:
            await message.answer("Rate limit exceeded. Please wait.")
            return
        
        # 3. Нормализация в InputEvent (паттерн из OpenClaw)
        event = InputEvent(
            type="message",
            source="telegram",
            user_id=str(message.from_user.id),
            content=message.text,
            timestamp=datetime.utcnow(),
            protocol_version=self.PROTOCOL_VERSION
        )
        
        # 4. Отправка в оркестратор
        await self.orchestrator.handle_event(event)
```

### 1.3 Требования к Адаптации

```
□ Добавить protocol_version="1.0" во все сообщения
□ Интегрировать ConnectorSecurityManager
□ Добавить capability checks перед выполнением команд
□ Добавить audit logging для всех действий
□ Добавить signature verification для API команд
□ Интегрировать с IsolationEnforcementPolicy
```

---

## 2️⃣ КОНФИГУРАЦИЯ И ДЕПЛОЙ (HIGH PRIORITY)

### 2.1 Структура Конфигурации

```yaml
# openclaw/config/config.yaml → synapse/config/default.yaml
system:
  name: "Synapse"
  version: "3.1"
  mode: "autonomous"  # autonomous, supervised, safe

llm:
  default_provider: "openai"
  models:
    - name: "gpt-4o"
      provider: "openai"
      priority: 1  # 🔹 IntEnum priority из spec v3.1
      timeout_seconds: 30
    - name: "claude-3.5"
      provider: "anthropic"
      priority: 2
      timeout_seconds: 30
    - name: "llama3"
      provider: "ollama"
      priority: 3
      timeout_seconds: 60

memory:
  vector_db: "chromadb"
  url: "http://localhost:8000"
  sql_db: "postgresql://user:pass@localhost:5432/synapse"

# 🔹 Наше дополнение: Isolation Policy
isolation_policy:
  unverified_skills: "container"
  risk_level_3_plus: "container"
  trusted_skills: "subprocess"

# 🔹 Наше дополнение: Resource Limits
resources:
  default_limits:
    cpu_seconds: 60
    memory_mb: 512
    disk_mb: 100
    network_kb: 1024

# 🔹 Наше дополнение: Time Sync
time_sync:
  enabled: true
  core_authority: true
  sync_interval_seconds: 30
  max_offset_ms: 1000

security:
  require_approval_for_risk: 3
  trusted_users: ["admin@company.com"]
  rate_limit_per_minute: 60
  require_command_signing: true
  audit_log_path: "/var/log/synapse/audit.log"
```

### 2.2 Docker Compose

```yaml
# openclaw/docker-compose.yml → synapse/docker/docker-compose.yml
version: '3.8'

services:
  synapse-core:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    image: synapse/core:3.1
    ports:
      - "8000:8000"  # API
      - "9090:9090"  # Prometheus
    volumes:
      - ../config:/app/config
      - ../skills:/app/skills
      - synapse_data:/app/data
    environment:
      - MODE=${MODE:-docker}
      - DATABASE_URL=postgresql://user:pass@db:5432/synapse
      - VECTOR_DB_URL=http://qdrant:6333
      - PROTOCOL_VERSION=1.0
      - SPEC_VERSION=3.1
    depends_on:
      db:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=synapse
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d synapse"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    depends_on:
      - synapse-core

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

volumes:
  synapse_data:
  postgres_data:
  qdrant_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

### 2.3 Health Check Endpoints

```python
# synapse/observability/health.py
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class HealthStatus(BaseModel):
    status: str
    version: str
    protocol_version: str
    timestamp: str
    services: dict

@router.get("/health")
async def health_check():
    """Health check endpoint для Docker и CI/CD"""
    return HealthStatus(
        status="healthy",
        version="3.1",
        protocol_version="1.0",
        timestamp=datetime.utcnow().isoformat(),
        services={
            "database": "connected",
            "vector_db": "connected",
            "llm": "available"
        }
    )

@router.get("/ready")
async def readiness_check():
    """Readiness check для Kubernetes"""
    # Проверка всех зависимостей
    return {"status": "ready"}

@router.get("/live")
async def liveness_check():
    """Liveness check для Kubernetes"""
    return {"status": "alive"}
```

---

## 3️⃣ ПАМЯТЬ И ВЕКТОРНОЕ ХРАНИЛИЩЕ (MEDIUM PRIORITY)

### 3.1 Vector Store Integration

```python
# openclaw/memory/vector.py → synapse/memory/vector_store.py
import chromadb
from chromadb.config import Settings
from core.models import MemoryQuery, MemoryEntry, PROTOCOL_VERSION

class VectorStore:
    """
    Векторное хранилище для семантической памяти.
    Адаптировано из OpenClaw с добавлением protocol versioning.
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self, config: dict):
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=config.get('path', './data/memory')
        ))
        self.collection = self.client.get_or_create_collection(
            name="synapse_memory",
            metadata={
                "hnsw:space": "cosine",
                "protocol_version": self.PROTOCOL_VERSION
            }
        )
    
    async def add(self, entry: MemoryEntry):
        """Добавление записи в память"""
        embedding = await self._generate_embedding(entry.content)
        self.collection.add(
            documents=[entry.content],
            embeddings=[embedding],
            metadatas=[{
                **entry.metadata,
                "type": entry.type,
                "protocol_version": self.PROTOCOL_VERSION
            }],
            ids=[entry.id]
        )
    
    async def recall(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Извлечение релевантных записей"""
        embedding = await self._generate_embedding(query.query_text)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=query.limit,
            where={"type": {"$in": query.memory_types}}
        )
        
        return [
            MemoryEntry(
                id=results['ids'][0][i],
                type=results['metadatas'][0][i]['type'],
                content=results['documents'][0][i],
                metadata=results['metadatas'][0][i],
                relevance_score=results['distances'][0][i] if 'distances' in results else 1.0,
                protocol_version=self.PROTOCOL_VERSION
            )
            for i in range(len(results['ids'][0]))
        ]
    
    async def _generate_embedding(self, text: str) -> list[float]:
        """Генерация эмбеддинга"""
        # Интеграция с LLM provider
        pass
```

### 3.2 Cache Layer (Redis)

```python
# synapse/memory/cache.py
import redis.asyncio as redis
from typing import Optional
from datetime import timedelta

class CacheLayer:
    """
    Кэш слой для кратковременной памяти.
    Паттерн из OpenClaw с добавлением TTL management.
    """
    
    def __init__(self, config: dict):
        self.redis = redis.Redis(
            host=config['host'],
            port=config['port'],
            db=config.get('db', 0),
            decode_responses=True
        )
    
    async def get(self, key: str) -> Optional[str]:
        return await self.redis.get(key)
    
    async def set(self, key: str, value: str, ttl_seconds: int = 3600):
        await self.redis.setex(key, timedelta(seconds=ttl_seconds), value)
    
    async def delete(self, key: str):
        await self.redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        return await self.redis.exists(key) > 0
```

---

## 4️⃣ LLM ABSTRACTION LAYER (MEDIUM PRIORITY)

### 4.1 Provider Configuration

```yaml
# openclaw/llm/config.yaml → synapse/config/llm_providers.yaml
providers:
  openai:
    base_url: "https://api.openai.com/v1"
    api_key_env: "OPENAI_API_KEY"
    models:
      - name: "gpt-4o"
        context_window: 128000
        max_tokens: 4096
        cost_per_1k_input: 0.005
        cost_per_1k_output: 0.015
        priority: 1  # 🔹 IntEnum из spec v3.1
    
  anthropic:
    base_url: "https://api.anthropic.com"
    api_key_env: "ANTHROPIC_API_KEY"
    models:
      - name: "claude-3.5-sonnet"
        context_window: 200000
        max_tokens: 4096
        cost_per_1k_input: 0.003
        cost_per_1k_output: 0.015
        priority: 2
    
  ollama:
    base_url: "http://localhost:11434"
    api_key_env: ""
    models:
      - name: "llama3"
        context_window: 8192
        max_tokens: 2048
        cost_per_1k_input: 0
        cost_per_1k_output: 0
        priority: 3
```

### 4.2 Token Tracking

```python
# synapse/llm/token_tracker.py
from prometheus_client import Counter
from typing import Dict

# 🔹 Prometheus метрики из spec v3.1
llm_token_usage_total = Counter(
    'synapse_llm_token_usage_total',
    'Total LLM tokens used',
    ['provider', 'model', 'type']  # type: prompt/completion
)

class TokenTracker:
    """
    Трекинг использования токенов LLM.
    Адаптировано из OpenClaw с добавлением Prometheus metrics.
    """
    
    def __init__(self):
        self.usage: Dict[str, Dict] = {}
    
    def record_usage(self, provider: str, model: str, 
                     prompt_tokens: int, completion_tokens: int):
        # Запись в память
        key = f"{provider}:{model}"
        if key not in self.usage:
            self.usage[key] = {'prompt': 0, 'completion': 0}
        
        self.usage[key]['prompt'] += prompt_tokens
        self.usage[key]['completion'] += completion_tokens
        
        # 🔹 Prometheus метрики
        llm_token_usage_total.labels(
            provider=provider,
            model=model,
            type='prompt'
        ).inc(prompt_tokens)
        
        llm_token_usage_total.labels(
            provider=provider,
            model=model,
            type='completion'
        ).inc(completion_tokens)
    
    def get_usage(self, provider: str = None) -> Dict:
        if provider:
            return self.usage.get(provider, {})
        return self.usage
    
    def get_total_cost(self) -> float:
        # Расчёт стоимости на основе конфигурации
        pass
```

---

## 5️⃣ НАВЫКИ (SKILL SYSTEM) (MEDIUM PRIORITY)

### 5.1 Skill Registry Pattern

```python
# openclaw/skills/registry.py → synapse/skills/registry.py
from typing import Dict, Type
from skills.base import BaseSkill, SkillManifest

class SkillRegistry:
    """
    Реестр навыков с versioning.
    Адаптировано из OpenClaw с добавлением lifecycle management.
    """
    
    def __init__(self):
        self._skills: Dict[str, Type[BaseSkill]] = {}
        self._versions: Dict[str, str] = {}
    
    def register(self, skill_class: Type[BaseSkill]):
        """Регистрация навыка"""
        manifest = skill_class.manifest
        key = f"{manifest.name}:{manifest.version}"
        
        # 🔹 Проверка lifecycle status из spec v3.1
        if manifest.trust_level == "unverified":
            raise ValueError("Unverified skills cannot be registered")
        
        self._skills[key] = skill_class
        self._versions[manifest.name] = manifest.version
    
    def get(self, name: str, version: str = None) -> Type[BaseSkill]:
        """Получение навыка по имени"""
        if version is None:
            version = self._versions.get(name)
        
        key = f"{name}:{version}"
        if key not in self._skills:
            raise KeyError(f"Skill {key} not found")
        
        return self._skills[key]
    
    def list(self) -> list[SkillManifest]:
        """Список всех зарегистрированных навыков"""
        return [skill.manifest for skill in self._skills.values()]
    
    def unregister(self, name: str, version: str):
        """Удаление навыка из реестра"""
        key = f"{name}:{version}"
        if key in self._skills:
            del self._skills[key]
```

### 5.2 Skill Configuration Schema

```yaml
# openclaw/skills/config.yaml → synapse/skills/manifest.yaml
skill:
  name: "web_search"
  version: "1.0.0"
  description: "Поиск информации в интернете"
  author: "synapse_core"

inputs:
  query:
    type: "string"
    description: "Поисковый запрос"
    required: true
  max_results:
    type: "integer"
    description: "Максимальное количество результатов"
    required: false
    default: 10

outputs:
  results:
    type: "array"
    items:
      type: "object"
      properties:
        title: "string"
        url: "string"
        snippet: "string"

# 🔹 Наше дополнение: Security
capabilities:
  - "network:http"

security:
  risk_level: 2
  requires_approval: false
  sandbox_required: true
  isolation_type: "container"  # 🔹 Из IsolationEnforcementPolicy

# 🔹 Наше дополнение: Resources
resources:
  timeout_seconds: 30
  max_memory_mb: 128
  cpu_quota: 0.5

# 🔹 Наше дополнение: Lifecycle
lifecycle:
  status: "active"  # generated, tested, verified, active, deprecated, archived
  trust_level: "verified"
  created_at: "2026-01-01T00:00:00Z"
  last_updated: "2026-01-01T00:00:00Z"

metadata:
  license: "MIT"
  tags: ["search", "web", "utility"]
  protocol_version: "1.0"
```

---

## 6️⃣ БЕЗОПАСНОСТЬ (DO NOT COPY)

### 6.1 Что НЕ Брать из OpenClaw

| Компонент | Причина | Наша Альтернатива |
|-----------|---------|------------------|
| Простая аутентификация | Нет capability tokens | Capability-Based Security Model |
| Динамическая загрузка навыков | Нет sandbox | Container Isolation Mandatory |
| Базовый audit log | Нет immutable storage | PostgreSQL Audit Log с checksum |
| Простой rate limiting | Нет user tiers | ConnectorSecurityManager с trusted users |
| Нет protocol versioning | Нет совместимости | protocol_version="1.0" везде |
| Нет rollback system | Нет recovery | RollbackManager с checkpoint |
| Нет resource accounting | Нет лимитов | ResourceLimits schema |
| Нет time sync | Нет distributed clock | Core Time Authority |

### 6.2 Наша Security Model (Spec v3.1)

```python
# synapse/core/security.py — НЕ из OpenClaw
from core.isolation_policy import IsolationEnforcementPolicy
from core.models import CapabilityToken, ResourceLimits

class SecurityManager:
    """
    Менеджер безопасности Synapse.
    Полностью оригинальная реализация согласно spec v3.1.
    """
    
    async def check_capabilities(self, required: list, context) -> SecurityCheckResult:
        # Capability-based проверка
        pass
    
    async def enforce_isolation(self, skill: BaseSkill) -> RuntimeIsolationType:
        # IsolationEnforcementPolicy применение
        isolation = IsolationEnforcementPolicy.get_required_isolation(
            trust_level=skill.manifest.trust_level,
            risk_level=skill.manifest.risk_level
        )
        return isolation
    
    async def check_resource_limits(self, limits: ResourceLimits) -> bool:
        # Resource accounting проверка
        pass
    
    async def create_checkpoint(self, agent_id: str, session_id: str) -> str:
        # Checkpoint для rollback
        pass
    
    async def rollback(self, checkpoint_id: str) -> RollbackResult:
        # Rollback к контрольной точке
        pass
```

---

## 7️⃣ ПЛАН ИНТЕГРАЦИИ

### Фаза 1: Коннекторы (Неделя 3-4)

| Задача | Файл OpenClaw | Файл Synapse | Статус |
|--------|--------------|--------------|--------|
| Telegram Bot | `connectors/telegram.py` | `synapse/connectors/telegram.py` | ⏳ Ожидает |
| Discord | `connectors/discord.py` | `synapse/connectors/discord.py` | ⏳ Ожидает |
| Base Connector | `connectors/base.py` | `synapse/connectors/base_connector.py` | ⏳ Ожидает |
| Security Layer | — | `synapse/connectors/security.py` | ⏳ Ожидает |

### Фаза 2: Конфигурация (Неделя 1-2)

| Задача | Файл OpenClaw | Файл Synapse | Статус |
|--------|--------------|--------------|--------|
| Config Schema | `config/config.yaml` | `synapse/config/default.yaml` | ⏳ Ожидает |
| ENV Management | `.env.example` | `synapse/.env.example` | ⏳ Ожидает |
| Validation | `config/validator.py` | `synapse/config/loader.py` | ⏳ Ожидает |

### Фаза 3: Деплой (Неделя 12-13)

| Задача | Файл OpenClaw | Файл Synapse | Статус |
|--------|--------------|--------------|--------|
| Docker Compose | `docker-compose.yml` | `synapse/docker/docker-compose.yml` | ⏳ Ожидает |
| Dockerfile | `docker/Dockerfile` | `synapse/docker/Dockerfile` | ⏳ Ожидает |
| Health Checks | `health.py` | `synapse/observability/health.py` | ⏳ Ожидает |

### Фаза 4: Память (Неделя 5-6)

| Задача | Файл OpenClaw | Файл Synapse | Статус |
|--------|--------------|--------------|--------|
| Vector Store | `memory/vector.py` | `synapse/memory/vector_store.py` | ⏳ Ожидает |
| Cache Layer | `memory/cache.py` | `synapse/memory/cache.py` | ⏳ Ожидает |
| Consolidation | — | `synapse/memory/consolidator.py` | ⏳ Ожидает |

### Фаза 5: LLM Layer (Неделя 7-8)

| Задача | Файл OpenClaw | Файл Synapse | Статус |
|--------|--------------|--------------|--------|
| Provider Config | `llm/config.yaml` | `synapse/config/llm_providers.yaml` | ⏳ Ожидает |
| Token Tracker | `llm/tracker.py` | `synapse/llm/token_tracker.py` | ⏳ Ожидает |
| Failure Strategy | — | `synapse/llm/failure_strategy.py` | ⏳ Ожидает |

---

## 8️⃣ CHECKLIST ИНТЕГРАЦИИ

```
□ Изучить openclaw/connectors/ для паттернов мессенджеров
□ Изучить openclaw/config/ для YAML schema patterns
□ Изучить openclaw/docker/ для deployment конфигураций
□ Изучить openclaw/memory/ для vector store integration
□ Изучить openclaw/llm/ для provider abstraction
□ Изучить openclaw/skills/ для registry patterns

□ НЕ брать security model (у нас capability-based)
□ НЕ брать skill loading (у нас sandbox mandatory)
□ НЕ брать fallback logic (у нас failure strategy)
□ НЕ брать execution model (у нас isolation policy)
□ НЕ брать checkpoint/rollback (у нас оригинальная реализация)

□ Адаптировать audit logging pattern
□ Адаптировать rate limiting algorithms
□ Адаптировать health check endpoints
□ Адаптировать token tracking
□ Адаптировать vector store integration

□ Добавить protocol_version="1.0" во все заимствованные модули
□ Добавить tests для всех заимствованных компонентов
□ Добавить документацию для всех заимствованных компонентов
□ Проверить совместимость с SYSTEM_SPEC_v3.1_FINAL_RELEASE.md
```

---

## 9️⃣ ЛИЦЕНЗИРОВАНИЕ И АТРИБУЦИЯ

### 9.1 OpenClaw License

```
OpenClaw License: MIT
Repository: https://github.com/openclaw/openclaw

При заимствовании кода необходимо:
1. Сохранить оригинальный copyright notice
2. Указать ссылку на оригинальный репозиторий
3. Добавить заметку об адаптации в docstring
```

### 9.2 Формат Атрибуции

```python
# synapse/connectors/telegram.py
"""
Telegram Connector для Synapse.

Адаптировано из OpenClaw:
https://github.com/openclaw/openclaw/tree/main/connectors/telegram.py

Оригинальная лицензия: MIT
Адаптация: Добавлен security layer, capability checks, protocol versioning

Copyright (c) 2024 OpenClaw Contributors
Copyright (c) 2026 Synapse Contributors
"""
```

---

## 🔟 ВЕРСИОНИРОВАНИЕ ДОКУМЕНТА

| Версия | Дата | Изменения |
|--------|------|-----------|
| 1.0 | 2026-01-03 | Initial release |

---

## 📞 КОНТАКТЫ И ПОДДЕРЖКА

**Основная спецификация:** `SYSTEM_SPEC_v3.1_FINAL_RELEASE.md`  
**TDD Инструкция:** `TDD_INSTRUCTION_v1.2_FINAL.md`  
**OpenClaw Repository:** https://github.com/openclaw/openclaw

Для вопросов по интеграции обращайтесь к документации проекта.

---

**Версия документа:** 1.0  
**Статус:** 🟢 READY FOR INTEGRATION  
**Совместимость:** SYSTEM_SPEC_v3.1_FINAL_RELEASE.md