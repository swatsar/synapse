# 🧠 Synapse — Distributed Cognitive Agent Platform

[![PyPI version](https://badge.fury.io/py/synapse-agent.svg)](https://badge.fury.io/py/synapse-agent)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-166%20files-brightgreen.svg)](tests/)
[![Pre-Production](https://img.shields.io/badge/Status-Pre--Production-blue.svg)](docs/)
[![Protocol](https://img.shields.io/badge/Protocol-v1.0-orange.svg)](SPECIFICATION.md)

**Pre-Production Distributed Cognitive Agent Platform с Capability-Based Security, Self-Evolution и Zero-Trust Execution.**

> **v3.4.1** — Полная синхронизация с архитектурной концепцией: 4-уровневая модель доверия, 8-шаговый когнитивный цикл, исправлены все структурные проблемы, импорты и безопасность.

---

## 📖 О проекте

**Synapse** — платформа автономных агентов с 8-шаговым когнитивным циклом, capability-based security, 4-уровневой моделью доверия к коду и поддержкой распределённого выполнения. Агенты умеют самостоятельно планировать, создавать новые навыки, откатываться на стабильные чекпоинты и работать в кластере.

Платформа построена на синтезе двух архитектурных парадигм: модульности OpenClaw и рекурсивного саморазвития Agent Zero.

### Ключевые возможности

| Возможность | Описание |
|-------------|----------|
| 🧬 **Саморазвитие** | Создание новых навыков через LLM + автотестирование + 6-статусный lifecycle |
| 🛡️ **4-Level Execution Trust Model** | Trusted → Verified → Unverified → Human-Approved с разной степенью изоляции |
| 🔐 **Capability-Based Security** | Токены доступа с wildcard scope, TTL и CapabilityScope enum |
| 🔄 **Checkpoint/Rollback** | Сохранение состояния перед каждым действием |
| 🌐 **Распределённое выполнение** | Кластер узлов с детерминированным планировщиком |
| 🔍 **Zero-Trust Fabric** | Верификация каждого узла (Phase 8) |
| 📊 **Полный аудит** | Каждое действие логируется с `protocol_version` |
| 🖥️ **Кроссплатформенность** | Адаптеры для Windows, Linux, macOS |

---

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.11+
- 4 GB RAM (8 GB рекомендуется)
- Docker (для production)

### Установка из исходников

```bash
git clone https://github.com/swatsar/synapse.git
cd synapse
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # заполните ключи LLM
```

### Запуск (локально)

```bash
# API-сервер + Web dashboard
synapse --web-ui --port 8000

# Только агент (без UI)
synapse --mode local

# Проверка здоровья
curl http://localhost:8000/health
```

### Запуск через Docker

```bash
cp .env.example .env
docker-compose -f docker/docker-compose.yml up -d
curl http://localhost:8000/health
```

---

## 🏗️ Архитектура

```
synapse/
├── core/                    # Оркестратор, security, checkpoint, determinism, audit
├── agents/                  # Planner, Critic, Developer, Forecaster, Guardian
│   ├── runtime/             # Базовый агент с когнитивным циклом
│   └── supervisor/          # Управляющий агент
├── skills/                  # Навыки: base, builtins, dynamic registry, lifecycle
│   ├── builtins/            # read_file, write_file, web_search
│   └── dynamic/             # 6-статусный реестр (GENERATED→ARCHIVED)
├── security/                # ExecutionGuard, CapabilityManager, MemorySeal
├── governance/              # CapabilityPolicyEngine, реестр capabilities
├── zero_trust/              # Identity, attestation, policy, enforcement (Phase 8)
├── llm/                     # LLMRouter с fallback, priority и timeout
├── memory/                  # MemoryStore (SQL) + VectorStore (ChromaDB)
├── environment/             # Кроссплатформенный слой: adapters/{windows,linux,macos}
├── transport/               # Channel, Message, Protocol
├── connectors/              # Telegram, Discord, REST
├── control_plane/           # ClusterManager, Scheduler, OrchestratorMesh
├── integrations/            # Human-in-the-loop, Code Generator, RAG, Browser
├── observability/           # Logger, Exporter (Prometheus), TraceClient
├── api/                     # FastAPI app, routes, middleware, storage
└── ui/                      # Web dashboard (HTML), Configurator
```

### Когнитивный цикл агента (8 шагов)

Реализация спецификации: Восприятие → Воспоминание → Планирование → Безопасность → Действие → Наблюдение → Оценка → Обучение

```
1. PERCEIVE   ← InputEvent от коннекторов (Telegram, Discord, REST)
2. RECALL     ← Memory retrieval (vector + SQL)
3. PLAN       ← ActionPlan через LLM + DeterministicPlanner
4. SECURITY   ← CapabilityManager.check_capabilities() + risk assessment
5. ACT        ← ExecutionGuard → Skill execution в sandbox/subprocess/container
6. OBSERVE    ← Результат + метрики
7. EVALUATE   ← CriticAgent оценивает качество
8. LEARN      ← Memory consolidation + self-improvement
```

---

## 🔒 Безопасность

### 4-уровневая модель доверия к коду (Execution Trust Model)

| Trust Level | Isolation | Описание | Права доступа |
|-------------|-----------|----------|---------------|
| `trusted` | subprocess | Встроенные навыки ядра | Полный доступ в рамках capability-токенов |
| `verified` | subprocess | Прошли автотесты + AST-анализ | Ограничен заявленными capabilities |
| `unverified` | sandbox | Только что сгенерированы LLM | Только вычисления, нет I/O |
| `human_approved` | subprocess | Одобрены пользователем после код-ревью | Расширенный доступ по запросу |

### Многоуровневая защита

1. **Sandbox Layer** — строгая изоляция для ненадёжного кода (нет сети, файлов, процессов)
2. **Capability Tokens** — wildcard-scope токены с TTL (`fs:read:/workspace/**`)
3. **CapabilityScope Enum** — `FILESYSTEM_READ`, `FILESYSTEM_WRITE`, `NETWORK_HTTP`, `PROCESS_SPAWN`, `DEVICE_IOT`, `SYSTEM_INFO`
4. **ExecutionGuard** — проверка capabilities перед каждым действием
5. **Policy Engine** — YAML-конфигурации политик безопасности
6. **Human-in-the-Loop** — одобрение для risk_level ≥ 3
7. **Zero-Trust Fabric** — верификация узлов кластера (Phase 8)
8. **AuditMechanism** — полное логирование с `event_type`, `agent_id`, `timestamp`

---

## 📦 Зависимости

| Пакет | Версия | Назначение |
|-------|--------|------------|
| `fastapi` | ≥0.100 | REST API |
| `pydantic` | ≥2.0 | Валидация данных |
| `litellm` | ≥1.0 | LLM abstraction (100+ провайдеров) |
| `uvicorn` | ≥0.23 | ASGI сервер |
| `sqlalchemy` | ≥2.0 | ORM |
| `aiosqlite` | ≥0.19 | SQLite async |
| `chromadb` | ≥0.4 | Vector memory (семантическая) |
| `redis` | ≥5.0 | Cache (краткосрочная память) |
| `asyncpg` | ≥0.29 | PostgreSQL async (долговременная) |
| `prometheus-client` | ≥0.19 | Метрики |
| `structlog` | ≥24.0 | Структурированные логи |

---

## 🧪 Тестирование

```bash
# Все тесты
pytest tests/ -v

# По маркеру
pytest -m unit -v
pytest -m security -v
pytest -m phase8 -v

# С coverage
pytest --cov=synapse --cov-report=term-missing
```

---

## 📊 Статус фаз

| Фаза | Статус | Описание |
|------|--------|----------|
| Phase 1 — Core Skeleton | ✅ Complete | Оркестратор, модели, базовые навыки |
| Phase 2 — Execution & Security | ✅ Complete | Capability security, ExecutionGuard, изоляция |
| Phase 3 — Perception & Memory | ✅ Complete | Коннекторы, MemoryStore, RAG |
| Phase 4 — Self-Evolution | ✅ Complete | Lifecycle навыков, Developer/Critic агенты |
| Phase 5 — Reliability & Observability | ✅ Complete | Checkpoint/Rollback, Prometheus, logging |
| Phase 6 — Deterministic Runtime | ✅ Complete | Детерминированное выполнение, Replay |
| Phase 7 — Control Plane | ✅ Complete | Cluster, Scheduler, OrchestratorMesh |
| Phase 7.1 — Orchestrator Control | ✅ Complete | OrchestratorControlAPI |
| Phase 7.2 — Ecosystem Layer | ✅ Complete | DomainPacks, Marketplace, API Gateway |
| Phase 8 — Zero-Trust Fabric | 🔄 In Progress | Identity, attestation, policy |

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [INSTALLATION](docs/user/installation.md) | Подробная установка |
| [QUICKSTART](docs/user/quickstart.md) | Старт за 5 минут |
| [CONFIGURATION](docs/user/configuration.md) | Все параметры конфигурации |
| [API Reference](docs/API_REFERENCE.md) | REST API эндпоинты |
| [SECURITY](docs/user/security.md) | Модель безопасности |
| [ARCHITECTURE](ARCHITECTURE.md) | Архитектура платформы |
| [TROUBLESHOOTING](docs/TROUBLESHOOTING.md) | Решение проблем |
| [TDD Guide](docs/TDD.md) | TDD-процесс разработки |
| [CHANGELOG](CHANGELOG.md) | История изменений |
| [ROADMAP](ROADMAP.md) | План развития |

### Интеграционные спецификации

| Документ | Описание |
|----------|----------|
| [LangChain](docs/integrations/LANGCHAIN_INTEGRATION.md) | LLM Router + Chains |
| [LangGraph](docs/integrations/LANGGRAPH_INTEGRATION.md) | State Graph |
| [LangSmith](docs/integrations/LANGSMITH_SDK_INTEGRATION.md) | Tracing + Observability |
| [Browser-Use](docs/integrations/BROWSER_USE_INTEGRATION.md) | Browser Automation |
| [Claude Code](docs/integrations/CLAUDE_CODE_INTEGRATION.md) | Code Generation |
| [OpenAI Codex](docs/integrations/CODEX_INTEGRATION.md) | Codex Integration |
| [AutoGPT](docs/integrations/AUTOGPT_INTEGRATION.md) | AutoGPT Patterns |
| [Anthropic Patterns](docs/integrations/ANTHROPIC_PATTERNS_INTEGRATION.md) | Anthropic Patterns |
| [Agent Zero](docs/integrations/AGENT_ZERO_INTEGRATION.md) | Agent Zero Patterns |
| [OpenClaw](docs/integrations/OPENCLAW_INTEGRATION.md) | OpenClaw Integration |

---

## 🤝 Вклад в проект

```bash
git clone https://github.com/swatsar/synapse.git
git checkout -b feature/my-feature
# ... изменения ...
pytest tests/ -v && flake8 synapse/
git commit -m "[Feature] Describe your change"
git push origin feature/my-feature
```

---

## 📄 Лицензия

MIT License — см. [LICENSE](LICENSE).

---

## 👤 Автор

**Евгений Савченко** — [evgeniisav@gmail.com](mailto:evgeniisav@gmail.com) · [@swatsar](https://github.com/swatsar)

---

**Версия:** 3.4.1 | **Protocol:** 1.0 | **Spec:** 3.1 | **Статус:** Pre-Production
